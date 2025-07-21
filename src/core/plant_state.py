from typing import Dict, Any, Optional
from dataclasses import dataclass, field
import time
import logging

from core.material_store import MaterialStore
from core.power_budget import PowerBudget

logger = logging.getLogger(__name__)

@dataclass
class EnvironmentState:
    """Current environmental conditions on Mars."""
    sol: int = 0  # Mars solar day
    time_of_sol: float = 0.0  # Fraction of sol (0-1)
    solar_irradiance_w_m2: float = 0.0
    ambient_temperature_k: float = 220.0  # ~-53°C typical Mars temp
    atmospheric_pressure_pa: float = 610.0  # ~0.6% of Earth
    dust_opacity: float = 0.0  # 0=clear, 1=major storm
    latitude_deg: float = 0.0
    longitude_deg: float = 0.0
    altitude_m: float = 0.0

class PlantState:
    """
    Central state container for the entire ISRU plant.
    Contains material stores, power budget, and environmental state.
    """
    
    def __init__(self):
        # Initialize material stores for ISRU process
        self.materials: Dict[str, MaterialStore] = {
            "H2O": MaterialStore("Water", capacity_kg=50000),  # 50 tonnes capacity
            "H2": MaterialStore("Hydrogen", capacity_kg=10000),  # 10 tonnes capacity  
            "O2": MaterialStore("Oxygen", capacity_kg=1000000),  # 1000 tonnes capacity
            "CO2": MaterialStore("Carbon Dioxide", capacity_kg=20000),  # 20 tonnes capacity
            "CH4": MaterialStore("Methane", capacity_kg=400000),  # 400 tonnes capacity
        }
        
        # Power management
        self.power_budget = PowerBudget()
        
        # Environmental conditions
        self.environment = EnvironmentState()
        
        # Simulation state
        self.current_time: float = 0.0  # Simulation time in seconds
        self.timestep_s: float = 60.0   # Default 1-minute timesteps
        self.is_paused: bool = False
        
        # Plant-wide status tracking
        self.total_ch4_produced_kg: float = 0.0
        self.total_o2_produced_kg: float = 0.0
        self.total_energy_consumed_kwh: float = 0.0
        
        # Module state storage (for persistence)
        self.module_states: Dict[str, Dict[str, Any]] = {}
    
    def advance_time(self, dt_seconds: float):
        """Advance simulation time."""
        if dt_seconds < 0:
            raise ValueError("Time step cannot be negative")
        
        self.current_time += dt_seconds
        
        # Update sol and time of sol
        sols_per_second = 1.0 / 88775.0  # Mars sol = ~24.65 Earth hours
        total_sols = self.current_time * sols_per_second
        
        self.environment.sol = int(total_sols)
        self.environment.time_of_sol = total_sols - self.environment.sol
    
    def get_material(self, material_name: str) -> MaterialStore:
        """Get material store by name."""
        if material_name not in self.materials:
            raise KeyError(f"Unknown material: {material_name}")
        return self.materials[material_name]
    
    def add_material_store(self, name: str, capacity_kg: Optional[float] = None):
        """Add a new material store."""
        if name in self.materials:
            logger.warning(f"Material store '{name}' already exists")
            return
        
        self.materials[name] = MaterialStore(name, capacity_kg=capacity_kg)
        logger.info(f"Added material store: {name}")
    
    def set_location(self, latitude_deg: float, longitude_deg: float, altitude_m: float = 0.0):
        """Set the plant location on Mars."""
        self.environment.latitude_deg = latitude_deg
        self.environment.longitude_deg = longitude_deg  
        self.environment.altitude_m = altitude_m
        logger.info(f"Plant location set to: {latitude_deg:.2f}°, {longitude_deg:.2f}°, {altitude_m:.0f}m")
    
    def update_production_totals(self, ch4_produced_kg: float = 0.0, o2_produced_kg: float = 0.0,
                               energy_consumed_kwh: float = 0.0):
        """Update cumulative production statistics."""
        self.total_ch4_produced_kg += ch4_produced_kg
        self.total_o2_produced_kg += o2_produced_kg
        self.total_energy_consumed_kwh += energy_consumed_kwh
    
    def get_material_inventory(self) -> Dict[str, float]:
        """Get current material inventory in kg."""
        return {name: store.mass_kg for name, store in self.materials.items()}
    
    def get_storage_utilization(self) -> Dict[str, float]:
        """Get storage utilization fractions (0-1) for materials with capacity limits."""
        utilization = {}
        for name, store in self.materials.items():
            if store.capacity_kg is not None:
                utilization[name] = store.fill_fraction
        return utilization
    
    def save_state(self) -> Dict[str, Any]:
        """Save complete plant state for persistence."""
        material_data = {}
        for name, store in self.materials.items():
            material_data[name] = {
                "mass_kg": store.mass_kg,
                "pressure_kpa": store.pressure_kpa,
                "temperature_k": store.temperature_k,
                "capacity_kg": store.capacity_kg
            }
        
        return {
            "current_time": self.current_time,
            "timestep_s": self.timestep_s,
            "materials": material_data,
            "environment": {
                "sol": self.environment.sol,
                "time_of_sol": self.environment.time_of_sol,
                "solar_irradiance_w_m2": self.environment.solar_irradiance_w_m2,
                "ambient_temperature_k": self.environment.ambient_temperature_k,
                "atmospheric_pressure_pa": self.environment.atmospheric_pressure_pa,
                "dust_opacity": self.environment.dust_opacity,
                "latitude_deg": self.environment.latitude_deg,
                "longitude_deg": self.environment.longitude_deg,
                "altitude_m": self.environment.altitude_m
            },
            "totals": {
                "total_ch4_produced_kg": self.total_ch4_produced_kg,
                "total_o2_produced_kg": self.total_o2_produced_kg,
                "total_energy_consumed_kwh": self.total_energy_consumed_kwh
            },
            "module_states": self.module_states
        }
    
    def load_state(self, state_data: Dict[str, Any]):
        """Load plant state from saved data."""
        self.current_time = state_data.get("current_time", 0.0)
        self.timestep_s = state_data.get("timestep_s", 60.0)
        
        # Restore materials
        if "materials" in state_data:
            for name, data in state_data["materials"].items():
                if name in self.materials:
                    store = self.materials[name]
                    store.mass_kg = data.get("mass_kg", 0.0)
                    store.pressure_kpa = data.get("pressure_kpa")
                    store.temperature_k = data.get("temperature_k")
                    if "capacity_kg" in data:
                        store.capacity_kg = data["capacity_kg"]
        
        # Restore environment
        if "environment" in state_data:
            env_data = state_data["environment"]
            for attr, value in env_data.items():
                if hasattr(self.environment, attr):
                    setattr(self.environment, attr, value)
        
        # Restore totals
        if "totals" in state_data:
            totals = state_data["totals"]
            self.total_ch4_produced_kg = totals.get("total_ch4_produced_kg", 0.0)
            self.total_o2_produced_kg = totals.get("total_o2_produced_kg", 0.0)
            self.total_energy_consumed_kwh = totals.get("total_energy_consumed_kwh", 0.0)
        
        # Restore module states
        self.module_states = state_data.get("module_states", {})
        
        logger.info(f"Loaded plant state from sol {self.environment.sol}")
    
    def __repr__(self) -> str:
        materials_summary = ", ".join([f"{name}: {store.mass_kg:.1f}kg" 
                                     for name, store in self.materials.items() 
                                     if store.mass_kg > 0])
        
        return (f"PlantState(Sol {self.environment.sol}, "
                f"Time: {self.environment.time_of_sol:.2f}, "
                f"Materials: [{materials_summary}], "
                f"Power: {self.power_budget.generation_kw:.1f}kW)") 