import math
from typing import Dict, Any, Optional
import logging

from core import BaseModule, PlantState, ModuleStatus

logger = logging.getLogger(__name__)

class PowerModule(BaseModule):
    """
    Power generation and storage module for Mars ISRU plant.
    Handles solar panels, battery storage, and power management.
    """
    
    def __init__(self, 
                 name: str = "Power",
                 solar_array_area_m2: float = 10000.0,
                 panel_efficiency: float = 0.20,
                 battery_capacity_kwh: float = 2000.0,
                 battery_min_soc: float = 0.20,
                 ignore_temp_overage: bool = False):
        
        super().__init__(name, priority=1, ignore_temp_overage=ignore_temp_overage)  # Critical infrastructure
        
        # Solar panel configuration
        self.solar_array_area_m2 = solar_array_area_m2
        self.panel_efficiency = panel_efficiency
        self.panel_degradation_factor = 1.0  # Dust accumulation, aging
        
        # Battery configuration
        self.battery_capacity_kwh = battery_capacity_kwh
        self.battery_min_soc = battery_min_soc  # 20% minimum (safety margin)
        self.battery_max_soc = 0.95  # 95% maximum (safety margin)
        self.charge_efficiency = 0.90  # 90% charge efficiency
        self.discharge_efficiency = 0.90  # 90% discharge efficiency
        self.battery_max_charge_rate_kw = battery_capacity_kwh * 0.5  # 0.5C max charge rate
        self.battery_max_discharge_rate_kw = battery_capacity_kwh * 1.0  # 1C max discharge rate
        
        # Current state
        self.battery_soc = 0.80  # Start at 80% charge
        self.solar_power_kw = 0.0
        self.battery_power_kw = 0.0  # Positive = discharging, negative = charging
        self.total_power_available_kw = 0.0
        
        # Statistics
        self.total_solar_energy_kwh = 0.0
        self.total_battery_cycles = 0.0
        self.dust_accumulation_factor = 1.0  # 1.0 = clean, 0.0 = completely dusty
        
        # Operating limits
        self.limits.max_temperature_k = 350.0  # Max operating temperature for electronics
        self.limits.min_power_kw = 10.0  # Minimum power for control systems
        self.limits.max_power_kw = None  # No max power limit
        
        # Dust cleaning system
        self.dust_cleaning_interval_s = 86400.0  # Clean panels daily
        self.last_dust_cleaning = 0.0
        self.dust_cleaning_power_kw = 5.0  # Power consumption for cleaning
        
    def simulate(self, plant_state: PlantState, dt_seconds: float) -> Dict[str, Any]:
        """Simulate power generation and battery management."""
        
        # Request minimum power for control systems
        self.request_power(plant_state, self.limits.min_power_kw)
        
        # Calculate solar power generation
        self._calculate_solar_generation(plant_state)
        
        # Update dust accumulation
        self._update_dust_accumulation(plant_state, dt_seconds)
        
        # Handle dust cleaning
        self._handle_dust_cleaning(plant_state, dt_seconds)
        
        # Calculate total available power (solar + battery)
        self._calculate_available_power(plant_state, dt_seconds)
        
        # Set power generation in plant budget
        plant_state.power_budget.set_generation(self.total_power_available_kw)
        
        # Update battery state
        self._update_battery_state(plant_state, dt_seconds)
        
        # Update statistics
        self._update_power_statistics(dt_seconds)
        
        # Temperature modeling (simplified)
        self._update_thermal_state(plant_state)
        
        return {
            "solar_power_kw": self.solar_power_kw,
            "battery_power_kw": self.battery_power_kw,
            "battery_soc": self.battery_soc,
            "battery_kwh": self.battery_soc * self.battery_capacity_kwh,
            "total_power_kw": self.total_power_available_kw,
            "dust_factor": self.dust_accumulation_factor,
            "panel_efficiency": self.panel_efficiency * self.panel_degradation_factor,
            "battery_cycles": self.total_battery_cycles,
            "solar_energy_kwh": self.total_solar_energy_kwh
        }
    
    def _calculate_solar_generation(self, plant_state: PlantState):
        """Calculate solar power generation based on environmental conditions."""
        env = plant_state.environment
        
        # Base solar power calculation
        # Power = Area × Irradiance × Efficiency × Degradation × Dust
        base_power_kw = (self.solar_array_area_m2 * 
                        env.solar_irradiance_w_m2 * 
                        self.panel_efficiency * 
                        self.panel_degradation_factor * 
                        self.dust_accumulation_factor) / 1000.0  # Convert W to kW
        
        # Temperature derating (panels lose efficiency when hot)
        # Simplified model: 0.4% loss per °C above 25°C
        panel_temp_c = env.ambient_temperature_k - 273.15 + 30  # Panels run ~30°C above ambient
        temp_derating = 1.0 - 0.004 * max(0, panel_temp_c - 25)
        
        self.solar_power_kw = max(0, base_power_kw * temp_derating)
    
    def _update_dust_accumulation(self, plant_state: PlantState, dt_seconds: float):
        """Update dust accumulation on solar panels."""
        env = plant_state.environment
        
        # Dust accumulation rate depends on dust storm activity and wind
        base_dust_rate = 0.01 / 86400.0  # 1% efficiency loss per day baseline
        
        if env.dust_opacity > 0:
            # During dust storms, accumulation is much faster
            storm_factor = 1.0 + env.dust_opacity * 10.0  # Up to 11x faster during storms
            dust_rate = base_dust_rate * storm_factor
        else:
            dust_rate = base_dust_rate
        
        # Apply dust accumulation
        dust_loss = dust_rate * dt_seconds
        self.dust_accumulation_factor = max(0.1, self.dust_accumulation_factor - dust_loss)
    
    def _handle_dust_cleaning(self, plant_state: PlantState, dt_seconds: float):
        """Handle automatic dust cleaning system."""
        current_time = plant_state.current_time
        
        # Check if it's time for cleaning
        if (current_time - self.last_dust_cleaning >= self.dust_cleaning_interval_s and
            self.dust_accumulation_factor < 0.9):  # Only clean if dusty
            
            # Check if we have enough power for cleaning
            if self.total_power_available_kw >= self.dust_cleaning_power_kw:
                # Perform cleaning
                self.dust_accumulation_factor = min(1.0, self.dust_accumulation_factor + 0.15)
                self.last_dust_cleaning = current_time
                
                # Consume power for cleaning (this will be handled in next iteration)
                logger.info(f"Solar panel cleaning performed, efficiency restored to {self.dust_accumulation_factor:.1%}")
    
    def _calculate_available_power(self, plant_state: PlantState, dt_seconds: float):
        """Calculate total available power from solar + battery."""
        
        # Solar power is always available when generated
        available_solar = self.solar_power_kw
        
        # Battery power availability depends on state of charge and discharge limits
        battery_available_kwh = (self.battery_soc - self.battery_min_soc) * self.battery_capacity_kwh
        max_battery_power_from_energy = battery_available_kwh / (dt_seconds / 3600.0)  # kW for this timestep
        
        # Limit by maximum discharge rate
        available_battery = min(
            max_battery_power_from_energy,
            self.battery_max_discharge_rate_kw
        )
        
        # Total available power
        self.total_power_available_kw = available_solar + max(0, available_battery)
        
        # Store for battery state update
        self.max_available_battery_kw = available_battery
    
    def _update_battery_state(self, plant_state: PlantState, dt_seconds: float):
        """Update battery state based on power generation and consumption."""
        
        # Get actual power consumption from budget
        power_budget = plant_state.power_budget
        actual_consumption_kw = power_budget.total_allocated_kw
        
        # Calculate power balance
        solar_available = self.solar_power_kw
        power_deficit = actual_consumption_kw - solar_available
        
        if power_deficit > 0:
            # Need to discharge battery
            battery_discharge_needed = power_deficit
            
            # Limit discharge by available capacity and rate limits
            actual_discharge = min(
                battery_discharge_needed,
                self.max_available_battery_kw,
                self.battery_max_discharge_rate_kw
            )
            
            # Update battery SOC (account for discharge efficiency)
            energy_discharged_kwh = actual_discharge * (dt_seconds / 3600.0)
            soc_decrease = energy_discharged_kwh / (self.battery_capacity_kwh * self.discharge_efficiency)
            self.battery_soc = max(self.battery_min_soc, self.battery_soc - soc_decrease)
            
            self.battery_power_kw = actual_discharge  # Positive = discharging
            
        elif power_deficit < 0:
            # Excess solar power - charge battery
            excess_power = -power_deficit
            
            # Calculate how much we can charge
            available_battery_capacity = (self.battery_max_soc - self.battery_soc) * self.battery_capacity_kwh
            max_charge_from_capacity = available_battery_capacity / (dt_seconds / 3600.0)  # kW for this timestep
            
            actual_charge = min(
                excess_power,
                max_charge_from_capacity,
                self.battery_max_charge_rate_kw
            )
            
            # Update battery SOC (account for charge efficiency)
            energy_charged_kwh = actual_charge * (dt_seconds / 3600.0)
            soc_increase = energy_charged_kwh * self.charge_efficiency / self.battery_capacity_kwh
            self.battery_soc = min(self.battery_max_soc, self.battery_soc + soc_increase)
            
            self.battery_power_kw = -actual_charge  # Negative = charging
            
        else:
            # Perfect balance
            self.battery_power_kw = 0.0
        
        # Check for battery safety limits
        if self.battery_soc <= self.battery_min_soc:
            logger.warning(f"Battery at minimum SOC ({self.battery_soc:.1%})")
        
        if self.battery_soc >= self.battery_max_soc:
            logger.debug(f"Battery fully charged ({self.battery_soc:.1%})")
    
    def _update_power_statistics(self, dt_seconds: float):
        """Update power generation statistics."""
        
        # Solar energy generated this timestep
        solar_energy_kwh = self.solar_power_kw * (dt_seconds / 3600.0)
        self.total_solar_energy_kwh += solar_energy_kwh
        
        # Battery cycle counting (simplified)
        # One full cycle = 100% discharge + 100% charge
        if self.battery_power_kw > 0:  # Discharging
            cycle_fraction = (self.battery_power_kw * dt_seconds / 3600.0) / self.battery_capacity_kwh
            self.total_battery_cycles += cycle_fraction
    
    def _update_thermal_state(self, plant_state: PlantState):
        """Update thermal state of power systems."""
        env = plant_state.environment
        
        # Simplified thermal model with scaling for large systems
        # Heat generation from power conversion (losses)
        power_losses_kw = (self.solar_power_kw * 0.05 +  # 5% inverter losses
                          abs(self.battery_power_kw) * 0.05)  # 5% battery conversion losses
        
        # Thermal coefficient decreases with system size (economies of scale in cooling)
        # Large systems have proportionally better heat dissipation
        size_factor = self.solar_array_area_m2 / 10000.0  # Normalize by 10,000 m²
        thermal_coeff = max(0.1, 2.0 / (1.0 + size_factor * 0.1))  # Scales down for large systems
        
        # Base temperature rise from losses
        thermal_rise_k = power_losses_kw * thermal_coeff
        
        # Heat dissipation proportional to temperature difference (basic cooling)
        temp_diff = max(0, self.current_temperature_k - env.ambient_temperature_k)
        cooling_factor = 0.02 * power_losses_kw / max(1.0, power_losses_kw / 1000.0)  # More cooling for larger systems
        heat_dissipation_k = temp_diff * cooling_factor
        
        # Net temperature = ambient + thermal rise - heat dissipation
        target_temp = env.ambient_temperature_k + thermal_rise_k - heat_dissipation_k
        self.current_temperature_k = max(env.ambient_temperature_k, target_temp)
    
    def get_power_summary(self) -> Dict[str, Any]:
        """Get comprehensive power system status."""
        return {
            "generation": {
                "solar_kw": self.solar_power_kw,
                "solar_capacity_kw": self.solar_array_area_m2 * 590 * self.panel_efficiency / 1000,
                "panel_efficiency": self.panel_efficiency * self.panel_degradation_factor,
                "dust_factor": self.dust_accumulation_factor
            },
            "battery": {
                "soc_percent": self.battery_soc * 100,
                "energy_kwh": self.battery_soc * self.battery_capacity_kwh,
                "capacity_kwh": self.battery_capacity_kwh,
                "power_kw": self.battery_power_kw,
                "cycles": self.total_battery_cycles,
                "max_discharge_kw": self.battery_max_discharge_rate_kw,
                "max_charge_kw": self.battery_max_charge_rate_kw
            },
            "totals": {
                "available_kw": self.total_power_available_kw,
                "solar_energy_total_kwh": self.total_solar_energy_kwh,
                "temperature_k": self.current_temperature_k
            },
            "status": {
                "module_status": self.status.value,
                "battery_healthy": self.battery_min_soc < self.battery_soc < self.battery_max_soc,
                "solar_healthy": self.dust_accumulation_factor > 0.5,
                "last_cleaning_hr": (self.last_dust_cleaning / 3600.0) if self.last_dust_cleaning > 0 else None
            }
        }
    
    def force_dust_cleaning(self):
        """Manually trigger dust cleaning (for emergencies)."""
        self.dust_accumulation_factor = min(1.0, self.dust_accumulation_factor + 0.20)
        logger.info(f"Manual dust cleaning performed, efficiency: {self.dust_accumulation_factor:.1%}")
    
    def set_battery_limits(self, min_soc: float = None, max_soc: float = None):
        """Adjust battery operating limits."""
        if min_soc is not None:
            if not 0.0 <= min_soc <= 1.0:
                raise ValueError("Battery min SOC must be between 0 and 1")
            self.battery_min_soc = min_soc
            logger.info(f"Battery minimum SOC set to {min_soc:.1%}")
        
        if max_soc is not None:
            if not 0.0 <= max_soc <= 1.0:
                raise ValueError("Battery max SOC must be between 0 and 1")
            self.battery_max_soc = max_soc
            logger.info(f"Battery maximum SOC set to {max_soc:.1%}")
    
    def inject_power_failure(self, duration_s: float):
        """Simulate power system failure for testing."""
        logger.warning(f"Simulating power failure for {duration_s/3600:.1f} hours")
        self._initiate_shutdown(0.0, f"Simulated failure ({duration_s/3600:.1f}h)")
        self.recovery_time_s = duration_s 