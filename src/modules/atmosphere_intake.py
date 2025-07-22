import math
from typing import Dict, Any, Optional
import logging

from core import BaseModule, PlantState, ModuleStatus

logger = logging.getLogger(__name__)

class AtmosphereIntakeModule(BaseModule):
    """
    Atmosphere intake module for Mars ISRU plant.
    Compresses and filters Mars atmospheric CO₂ for use in Sabatier reactor.
    Based on MOXIE technology scaled up for Starship refueling requirements.
    """
    
    def __init__(self, 
                 name: str = "AtmosphereIntake",
                 target_flow_rate_kg_hr: float = 1000.0,
                 compression_ratio: float = 20.0,
                 filter_efficiency: float = 0.95,
                 ignore_temp_overage: bool = False):
        
        super().__init__(name, priority=2, ignore_temp_overage=ignore_temp_overage)  # Important for ISRU process
        
        # Design parameters
        self.target_flow_rate_kg_hr = target_flow_rate_kg_hr  # Target CO₂ intake rate
        self.compression_ratio = compression_ratio  # Final pressure / atmospheric pressure
        self.filter_efficiency = filter_efficiency  # Fraction of CO₂ that passes through filters
        
        # Power scaling (based on MOXIE: ~120W for 83 g/hr CO₂ → ~1.45 kW per kg/hr)
        self.power_per_kg_hr = 1.45  # kW per kg/hr CO₂ throughput
        self.min_power_fraction = 0.2  # Minimum 20% power to keep running
        
        # Current operating state
        self.current_flow_rate_kg_hr = 0.0
        self.current_compression_ratio = 1.0
        self.actual_co2_output_kg_hr = 0.0
        self.current_pressure_in_kpa = 0.61  # Mars atmospheric pressure
        self.current_pressure_out_kpa = 12.2  # Compressed output pressure
        
        # Filter and mechanical state
        self.filter_contamination = 0.0  # 0 = clean, 1 = completely clogged
        self.compressor_wear = 0.0  # 0 = new, 1 = worn out
        self.vibration_level = 0.0  # Mechanical health indicator
        
        # Operating limits
        self.limits.max_temperature_k = 400.0  # Max compressor temperature
        self.limits.max_pressure_kpa = 2000.0  # Max output pressure (safety)
        self.limits.max_flow_rate_kg_hr = target_flow_rate_kg_hr * 1.2  # 120% of nominal
        self.limits.min_flow_rate_kg_hr = target_flow_rate_kg_hr * 0.1  # 10% minimum
        
        # Performance coefficients
        self.nominal_efficiency = 0.85  # Thermodynamic efficiency at design point
        self.current_efficiency = self.nominal_efficiency
        
        # Statistics
        self.total_co2_processed_kg = 0.0
        self.filter_replacement_count = 0
        self.operating_hours = 0.0
        
        # Maintenance scheduling
        self.filter_replacement_interval_hrs = 720.0  # 30 days continuous operation
        self.last_filter_replacement = 0.0
        self.compressor_maintenance_interval_hrs = 2160.0  # 90 days
        self.last_compressor_maintenance = 0.0
        
    def simulate(self, plant_state: PlantState, dt_seconds: float) -> Dict[str, Any]:
        """Simulate atmosphere intake operation."""
        
        # Calculate required power
        target_power_kw = self.target_flow_rate_kg_hr * self.power_per_kg_hr
        min_power_kw = target_power_kw * self.min_power_fraction
        
        # Set power requirements
        self.min_power_kw = min_power_kw
        self.max_power_kw = target_power_kw * 1.1  # Allow 10% margin
        
        # Request power
        self.request_power(plant_state, target_power_kw)
        
        # Update inlet conditions from environment
        self._update_inlet_conditions(plant_state)
        
        # Check filter and compressor condition
        self._update_component_health(dt_seconds)
        
        # Calculate actual operating point based on available power
        self._calculate_operating_point(plant_state)
        
        # Process CO₂ and update material stores
        co2_produced = self._process_atmosphere(plant_state, dt_seconds)
        
        # Update thermal state
        self._update_thermal_state(plant_state)
        
        # Update statistics
        self._update_statistics(dt_seconds)
        
        # Check for maintenance needs
        self._check_maintenance_schedule(plant_state)
        
        return {
            "co2_flow_rate_kg_hr": self.current_flow_rate_kg_hr,
            "co2_output_kg_hr": self.actual_co2_output_kg_hr,
            "co2_produced_kg": co2_produced,
            "compression_ratio": self.current_compression_ratio,
            "inlet_pressure_kpa": self.current_pressure_in_kpa,
            "outlet_pressure_kpa": self.current_pressure_out_kpa,
            "efficiency": self.current_efficiency,
            "filter_contamination": self.filter_contamination,
            "compressor_wear": self.compressor_wear,
            "power_consumption_kw": self.power_allocated_kw,
            "total_co2_processed_kg": self.total_co2_processed_kg
        }
    
    def _update_inlet_conditions(self, plant_state: PlantState):
        """Update inlet conditions based on Mars environment."""
        env = plant_state.environment
        
        # Atmospheric pressure varies with altitude and weather
        self.current_pressure_in_kpa = env.atmospheric_pressure_pa / 1000.0  # Convert Pa to kPa
        
        # Temperature affects density and compressor work
        self.current_temperature_k = env.ambient_temperature_k
    
    def _update_component_health(self, dt_seconds: float):
        """Update filter contamination and compressor wear."""
        
        # Filter contamination increases with operation
        if self.current_flow_rate_kg_hr > 0:
            # Contamination rate depends on flow rate and atmospheric conditions
            contamination_rate = 0.001 / 3600.0  # 0.1% per hour baseline
            dust_factor = 1.0  # Could link to environment dust conditions
            
            contamination_increase = contamination_rate * dust_factor * (dt_seconds / 3600.0)
            self.filter_contamination = min(1.0, self.filter_contamination + contamination_increase)
        
        # Compressor wear increases with operating time and load
        if self.power_allocated_kw > 0:
            # Wear rate depends on load factor and operating conditions
            load_factor = self.power_allocated_kw / (self.target_flow_rate_kg_hr * self.power_per_kg_hr)
            wear_rate = 0.0005 / 3600.0 * load_factor  # Base wear rate per hour
            
            wear_increase = wear_rate * (dt_seconds / 3600.0)
            self.compressor_wear = min(1.0, self.compressor_wear + wear_increase)
        
        # Update efficiency based on component health
        filter_efficiency_factor = 1.0 - self.filter_contamination * 0.5  # Max 50% loss
        wear_efficiency_factor = 1.0 - self.compressor_wear * 0.3  # Max 30% loss
        
        self.current_efficiency = (self.nominal_efficiency * 
                                 filter_efficiency_factor * 
                                 wear_efficiency_factor)
    
    def _calculate_operating_point(self, plant_state: PlantState):
        """Calculate actual operating point based on available power and conditions."""
        
        # Available power determines maximum flow rate
        if self.power_allocated_kw < self.min_power_kw:
            # Insufficient power - shut down
            self.current_flow_rate_kg_hr = 0.0
            self.current_compression_ratio = 1.0
            self.actual_co2_output_kg_hr = 0.0
            return
        
        # Calculate achievable flow rate based on power
        max_flow_from_power = self.power_allocated_kw / self.power_per_kg_hr
        
        # Limit by component health and design limits
        max_flow_from_health = self.target_flow_rate_kg_hr * self.current_efficiency
        max_flow_from_limits = self.limits.max_flow_rate_kg_hr
        
        # Actual flow rate is minimum of all constraints
        self.current_flow_rate_kg_hr = min(
            max_flow_from_power,
            max_flow_from_health,
            max_flow_from_limits
        )
        
        # Ensure minimum flow rate if operating
        if self.current_flow_rate_kg_hr > 0:
            self.current_flow_rate_kg_hr = max(
                self.current_flow_rate_kg_hr,
                self.limits.min_flow_rate_kg_hr
            )
        
        # Calculate compression ratio and output pressure
        if self.current_flow_rate_kg_hr > 0:
            # Compression ratio might vary with load
            load_factor = self.current_flow_rate_kg_hr / self.target_flow_rate_kg_hr
            self.current_compression_ratio = self.compression_ratio * load_factor
            self.current_pressure_out_kpa = (self.current_pressure_in_kpa * 
                                           self.current_compression_ratio)
        else:
            self.current_compression_ratio = 1.0
            self.current_pressure_out_kpa = self.current_pressure_in_kpa
        
        # Calculate actual CO₂ output after filtering losses
        filter_loss_factor = 1.0 - self.filter_contamination * 0.2  # Up to 20% loss from clogging
        self.actual_co2_output_kg_hr = (self.current_flow_rate_kg_hr * 
                                       self.filter_efficiency * 
                                       filter_loss_factor)
    
    def _process_atmosphere(self, plant_state: PlantState, dt_seconds: float) -> float:
        """Process atmospheric CO₂ and store in plant materials."""
        
        # Calculate CO₂ produced this timestep
        co2_produced_kg = self.actual_co2_output_kg_hr * (dt_seconds / 3600.0)
        
        if co2_produced_kg > 0:
            # Store CO₂ in plant material stores
            co2_store = plant_state.get_material("CO2")
            actual_stored = co2_store.store(co2_produced_kg)
            
            if actual_stored < co2_produced_kg:
                logger.warning(f"CO₂ storage full: only stored {actual_stored:.2f} kg of {co2_produced_kg:.2f} kg produced")
            
            # Set pressure and temperature properties
            co2_store.set_physical_properties(
                pressure_kpa=self.current_pressure_out_kpa,
                temperature_k=self.current_temperature_k + 50  # Compressed gas is hotter
            )
            
            return actual_stored
        
        return 0.0
    
    def _update_thermal_state(self, plant_state: PlantState):
        """Update thermal state of compressor."""
        env = plant_state.environment
        
        # Compressor temperature rise from compression work
        if self.current_flow_rate_kg_hr > 0:
            # Simplified thermal model: temperature rise proportional to compression work
            compression_work_factor = math.log(max(1.1, self.current_compression_ratio))
            temp_rise_k = compression_work_factor * 80.0  # Up to 80K rise for high compression
            
            # Heat rejection depends on available cooling
            cooling_effectiveness = 0.7  # 70% heat rejection to environment
            net_temp_rise = temp_rise_k * (1.0 - cooling_effectiveness)
            
            self.current_temperature_k = env.ambient_temperature_k + net_temp_rise
        else:
            # Cool down to ambient when not operating
            self.current_temperature_k = env.ambient_temperature_k
    
    def _update_statistics(self, dt_seconds: float):
        """Update operating statistics."""
        
        # Operating hours
        if self.current_flow_rate_kg_hr > 0:
            self.operating_hours += dt_seconds / 3600.0
        
        # Total CO₂ processed
        co2_processed = self.current_flow_rate_kg_hr * (dt_seconds / 3600.0)
        self.total_co2_processed_kg += co2_processed
    
    def _check_maintenance_schedule(self, plant_state: PlantState):
        """Check if maintenance is due."""
        current_time_hrs = plant_state.current_time / 3600.0
        
        # Filter replacement check
        if (current_time_hrs - self.last_filter_replacement >= self.filter_replacement_interval_hrs or
            self.filter_contamination >= 0.8):
            
            if self.status != ModuleStatus.SHUTDOWN:
                logger.info(f"Filter replacement due: contamination {self.filter_contamination:.1%}")
                self._perform_filter_replacement(current_time_hrs)
        
        # Compressor maintenance check
        if (current_time_hrs - self.last_compressor_maintenance >= self.compressor_maintenance_interval_hrs or
            self.compressor_wear >= 0.7):
            
            if self.status != ModuleStatus.SHUTDOWN:
                logger.warning(f"Compressor maintenance due: wear {self.compressor_wear:.1%}")
                # In reality, this would require shutdown for maintenance
    
    def _perform_filter_replacement(self, current_time_hrs: float):
        """Perform filter replacement maintenance."""
        self.filter_contamination = 0.0
        self.last_filter_replacement = current_time_hrs
        self.filter_replacement_count += 1
        logger.info(f"Filter replacement completed (#{self.filter_replacement_count})")
    
    def force_filter_replacement(self):
        """Manually trigger filter replacement."""
        self.filter_contamination = 0.0
        self.filter_replacement_count += 1
        logger.info(f"Manual filter replacement completed")
    
    def force_compressor_maintenance(self):
        """Manually trigger compressor maintenance."""
        self.compressor_wear = 0.0
        self.vibration_level = 0.0
        logger.info(f"Manual compressor maintenance completed")
    
    def get_maintenance_status(self) -> Dict[str, Any]:
        """Get maintenance status and scheduling."""
        return {
            "filter": {
                "contamination": self.filter_contamination,
                "replacement_count": self.filter_replacement_count,
                "hours_since_replacement": self.operating_hours - self.last_filter_replacement,
                "next_replacement_hours": self.filter_replacement_interval_hrs - (self.operating_hours - self.last_filter_replacement)
            },
            "compressor": {
                "wear": self.compressor_wear,
                "vibration": self.vibration_level,
                "hours_since_maintenance": self.operating_hours - self.last_compressor_maintenance,
                "next_maintenance_hours": self.compressor_maintenance_interval_hrs - (self.operating_hours - self.last_compressor_maintenance)
            },
            "performance": {
                "efficiency": self.current_efficiency,
                "target_efficiency": self.nominal_efficiency,
                "efficiency_loss": self.nominal_efficiency - self.current_efficiency
            }
        }
    
    def set_target_flow_rate(self, target_kg_hr: float):
        """Adjust target flow rate (for different production scenarios)."""
        if target_kg_hr < 0:
            raise ValueError("Target flow rate cannot be negative")
        
        old_target = self.target_flow_rate_kg_hr
        self.target_flow_rate_kg_hr = target_kg_hr
        
        # Update operating limits
        self.limits.max_flow_rate_kg_hr = target_kg_hr * 1.2
        self.limits.min_flow_rate_kg_hr = target_kg_hr * 0.1
        
        logger.info(f"Target flow rate changed from {old_target:.0f} to {target_kg_hr:.0f} kg/hr")
    
    def __repr__(self) -> str:
        return (f"AtmosphereIntakeModule(target: {self.target_flow_rate_kg_hr:.0f} kg/hr, "
                f"actual: {self.actual_co2_output_kg_hr:.0f} kg/hr, "
                f"efficiency: {self.current_efficiency:.1%}, "
                f"status: {self.status.value})") 