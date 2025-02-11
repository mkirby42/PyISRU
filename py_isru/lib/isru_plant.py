"""
Main ISRU plant class that orchestrates all components.
"""
from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, List, Optional
import numpy as np

from .reactor import ResourceType, OperationalStatus
from .sabatier_reactor import SabatierReactor, SabatierSpecification
from .electrolysis_reactor import ElectrolysisReactor, ElectrolysisSpecification
from .storage_tank import StorageTank, TankSpecification
from .power_system import (
    PowerSystem, PowerSystemStatus,
    SolarArray, SolarArraySpecification,
    Battery, BatterySpecification,
    KrustyReactor, KrustySpecification
)
from .thermodynamics import ThermodynamicState, ReactionKinetics

class PlantStatus(Enum):
    """Overall plant operational status"""
    STARTUP = auto()
    RUNNING = auto()
    SHUTDOWN = auto()
    STANDBY = auto()
    EMERGENCY = auto()
    MAINTENANCE = auto()

@dataclass
class PlantSpecification:
    """Complete specification for an ISRU plant"""
    sabatier_spec: SabatierSpecification
    electrolysis_spec: ElectrolysisSpecification
    tank_specs: Dict[ResourceType, TankSpecification]
    solar_spec: SolarArraySpecification
    battery_spec: BatterySpecification
    krusty_spec: KrustySpecification
    
    # Control parameters
    min_tank_levels: Dict[ResourceType, float]  # mol
    max_tank_levels: Dict[ResourceType, float]  # mol
    emergency_power_threshold: float  # W
    maintenance_interval: float  # seconds

class ISRUPlant:
    """
    Main ISRU plant class that coordinates all subsystems
    """
    
    def __init__(self, spec: PlantSpecification):
        self.spec = spec
        self.status = PlantStatus.STANDBY
        self.time = 0.0  # seconds
        self.fault_condition: Optional[str] = None
        
        # Initialize subsystems
        self._initialize_subsystems()
        
        # Performance metrics
        self.total_ch4_produced = 0.0  # mol
        self.total_o2_produced = 0.0  # mol
        self.total_energy_consumed = 0.0  # J
        self.uptime = 0.0  # seconds
        
    def _initialize_subsystems(self):
        """Initialize all subsystems with their specifications"""
        # Initialize reactors
        initial_state = ThermodynamicState.from_temperature_pressure(298.15, 101325)
        
        # Create kinetics objects
        sabatier_kinetics = ReactionKinetics(
            rate_constants={"forward": 1e-3},
            activation_energy=75e3,  # J/mol
            catalyst_surface_area=self.spec.sabatier_spec.catalyst_loading * 1000 * self.spec.sabatier_spec.catalyst_surface_area,
            reaction_order={"CO2": 1, "H2": 4}
        )
        
        electrolysis_kinetics = ReactionKinetics(
            rate_constants={"forward": 1.0},
            activation_energy=0.0,
            catalyst_surface_area=self.spec.electrolysis_spec.electrode_area,
            reaction_order={"H2O": 1}
        )
        
        self.sabatier = SabatierReactor(
            self.spec.sabatier_spec,
            initial_state,
            sabatier_kinetics  # Use the created kinetics object
        )
        
        self.electrolysis = ElectrolysisReactor(
            self.spec.electrolysis_spec,
            initial_state,
            electrolysis_kinetics  # Use the created kinetics object
        )
        
        # Initialize storage tanks
        self.tanks: Dict[ResourceType, StorageTank] = {}
        for resource_type, tank_spec in self.spec.tank_specs.items():
            self.tanks[resource_type] = StorageTank(
                tank_spec,
                resource_type,
                initial_state
            )
            
        # Initialize power systems
        self.solar_array = SolarArray(self.spec.solar_spec)
        self.battery = Battery(self.spec.battery_spec)
        self.krusty = KrustyReactor(self.spec.krusty_spec)
        
        # Set initial states
        self.solar_array.status = PowerSystemStatus.ONLINE
        self.battery.status = PowerSystemStatus.ONLINE
        self.krusty.status = PowerSystemStatus.OFFLINE
        
    def step(self, dt: float) -> None:
        """
        Advance plant state by one time step
        
        Args:
            dt: Time step in seconds
        """
        self.time += dt
        
        if self.status == PlantStatus.STANDBY:
            return
            
        # Update power systems
        self._update_power_systems(dt)
        
        # Check if we have enough power
        available_power = self._calculate_available_power()
        required_power = self._calculate_required_power()
        
        if available_power < required_power:
            if available_power < self.spec.emergency_power_threshold:
                self.status = PlantStatus.EMERGENCY
                self.fault_condition = "Insufficient power"
                return
            else:
                # Degrade gracefully
                self._adjust_production_rate(available_power / required_power)
                
        # Update reactors
        self._update_reactors(dt)
        
        # Update storage tanks
        self._update_storage(dt)
        
        # Update metrics
        if self.status == PlantStatus.RUNNING:
            self.uptime += dt
            self.total_energy_consumed += required_power * dt
            
        # Check for maintenance
        if self.time > self.spec.maintenance_interval:
            self.status = PlantStatus.MAINTENANCE
            
    def _update_power_systems(self, dt: float) -> None:
        """Update all power systems"""
        self.solar_array.step(dt)
        self.battery.step(dt)
        self.krusty.step(dt)
        
        # Charge battery with excess solar power
        solar_output = self.solar_array.calculate_output()
        required_power = self._calculate_required_power()
        
        if solar_output > required_power:
            excess_power = solar_output - required_power
            self.battery.charge(excess_power)
            
    def _calculate_available_power(self) -> float:
        """Calculate total available power"""
        return (self.solar_array.calculate_output() +
                self.battery.calculate_output() +
                self.krusty.calculate_output())
                
    def _calculate_required_power(self) -> float:
        """Calculate total power required by the plant"""
        return (self.sabatier.calculate_power_consumption() +
                self.electrolysis.calculate_power_consumption())
                
    def _adjust_production_rate(self, power_ratio: float) -> None:
        """Adjust production rates based on available power"""
        # TODO: Implement smart production adjustment
        pass
        
    def _update_reactors(self, dt: float) -> None:
        """Update reactor states and process reactions"""
        # Get available resources
        co2_available = self.tanks[ResourceType.CO2].moles
        h2o_available = self.tanks[ResourceType.H2O].moles
        h2_available = self.tanks[ResourceType.H2].moles
        
        # Initialize outputs
        sabatier_outputs = {resource: 0.0 for resource in ResourceType}
        electrolysis_outputs = {resource: 0.0 for resource in ResourceType}
        
        # Run electrolysis first to produce H₂
        if h2o_available > 0:
            electrolysis_inputs = {
                ResourceType.H2O: h2o_available
            }
            electrolysis_outputs = self.electrolysis.step(dt, electrolysis_inputs)
            
            # Update tank levels from electrolysis
            for resource, amount in electrolysis_outputs.items():
                if amount > 0:
                    self.tanks[resource].add_resource(amount, self.electrolysis.state.temperature)
                else:
                    self.tanks[resource].remove_resource(-amount)
            
            # Update H₂ available for Sabatier reaction
            h2_available = self.tanks[ResourceType.H2].moles
        
        # Then run Sabatier with available H₂
        if co2_available > 0 and h2_available >= 4 * co2_available:
            sabatier_inputs = {
                ResourceType.CO2: co2_available,
                ResourceType.H2: 4 * co2_available
            }
            sabatier_outputs = self.sabatier.step(dt, sabatier_inputs)
            
            # Update tank levels from Sabatier
            for resource, amount in sabatier_outputs.items():
                if amount > 0:
                    self.tanks[resource].add_resource(amount, self.sabatier.state.temperature)
                else:
                    self.tanks[resource].remove_resource(-amount)
                    
        # Update production metrics
        self.total_ch4_produced += sabatier_outputs.get(ResourceType.CH4, 0.0)
        self.total_o2_produced += electrolysis_outputs.get(ResourceType.O2, 0.0)
        
    def _update_storage(self, dt: float) -> None:
        """Update storage tank states"""
        for tank in self.tanks.values():
            tank.step(dt)
            
    def start(self) -> bool:
        """Start the plant"""
        if self.status != PlantStatus.STANDBY:
            return False
            
        self.status = PlantStatus.STARTUP
        
        # Start reactors
        self.sabatier.start()
        self.electrolysis.start()
        
        # Ensure power systems are online
        self.solar_array.status = PowerSystemStatus.ONLINE
        self.battery.status = PowerSystemStatus.ONLINE
        
        self.status = PlantStatus.RUNNING
        return True
        
    def shutdown(self) -> bool:
        """Shutdown the plant"""
        if self.status not in [PlantStatus.RUNNING, PlantStatus.EMERGENCY]:
            return False
            
        self.status = PlantStatus.SHUTDOWN
        
        # Shutdown reactors
        self.sabatier.shutdown()
        self.electrolysis.shutdown()
        
        # Keep power systems online for monitoring
        self.status = PlantStatus.STANDBY
        return True
        
    def get_status_report(self) -> Dict:
        """Get current status of all subsystems"""
        return {
            "plant_status": self.status,
            "fault_condition": self.fault_condition,
            "uptime": self.uptime,
            "total_ch4_produced": self.total_ch4_produced,
            "total_o2_produced": self.total_o2_produced,
            "total_energy_consumed": self.total_energy_consumed,
            "tank_levels": {
                resource: tank.moles
                for resource, tank in self.tanks.items()
            },
            "power_systems": {
                "solar": {
                    "status": self.solar_array.status,
                    "output": self.solar_array.calculate_output(),
                    "dust_coverage": self.solar_array.dust_coverage
                },
                "battery": {
                    "status": self.battery.status,
                    "charge_level": self.battery.charge_level,
                    "output": self.battery.calculate_output()
                },
                "krusty": {
                    "status": self.krusty.status,
                    "output": self.krusty.calculate_output(),
                    "operational_time": self.krusty.operational_time
                }
            },
            "reactors": {
                "sabatier": {
                    "status": self.sabatier.operational_status,
                    "temperature": self.sabatier.state.temperature,
                    "catalyst_degradation": self.sabatier.catalyst_degradation
                },
                "electrolysis": {
                    "status": self.electrolysis.operational_status,
                    "temperature": self.electrolysis.state.temperature,
                    "membrane_degradation": self.electrolysis.membrane_degradation
                }
            }
        } 