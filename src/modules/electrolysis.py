import math
from typing import Dict, Any, Optional
import logging

from core import BaseModule, PlantState, ModuleStatus

logger = logging.getLogger(__name__)

class ElectrolysisModule(BaseModule):
    """
    Electrolysis module for Mars ISRU plant.
    Performs water splitting: 2H₂O → 2H₂ + O₂
    
    Key design considerations:
    - High power consumption (38 kWh/kg H₂ from PRD)
    - Temperature and pressure optimization
    - Electrode degradation and maintenance
    - Gas separation and purification
    """
    
    def __init__(self, 
                 name: str = "Electrolysis",
                 target_h2_rate_kg_hr: float = 100.0,  # Target H₂ production rate
                 operating_temperature_k: float = 353.0,  # 80°C optimal for PEM
                 operating_pressure_kpa: float = 3000.0):  # 30 bar for efficiency
        
        super().__init__(name, priority=2)  # Important for H₂ supply
        
        # Design parameters
        self.target_h2_rate_kg_hr = target_h2_rate_kg_hr
        self.operating_temperature_k = operating_temperature_k
        self.operating_pressure_kpa = operating_pressure_kpa
        
        # Reaction stoichiometry: 2H₂O → 2H₂ + O₂
        # Molecular weights: H₂O=18, H₂=2, O₂=32
        self.mw_h2o = 18.0
        self.mw_h2 = 2.0
        self.mw_o2 = 32.0
        
        # Stoichiometric ratios (mass basis)
        self.h2o_to_h2_ratio = self.mw_h2o / self.mw_h2  # 9 kg H₂O per kg H₂
        self.o2_to_h2_ratio = (0.5 * self.mw_o2) / self.mw_h2  # 8 kg O₂ per kg H₂
        
        # Power requirements based on PRD: 38 kWh/kg H₂
        self.power_per_kg_h2 = 38.0  # kW per kg/hr H₂ throughput
        self.min_power_fraction = 0.10  # Minimum 10% power to keep electrodes active
        
        # Current operating state
        self.current_h2_rate_kg_hr = 0.0
        self.current_o2_rate_kg_hr = 0.0
        self.current_h2o_consumption_kg_hr = 0.0
        self.current_temperature_k = 298.0  # Room temperature startup
        self.current_pressure_kpa = 101.3
        self.current_efficiency = 0.0
        self.current_cell_voltage = 1.48  # Theoretical minimum 1.23V + overpotentials
        
        # Electrolyzer state
        self.electrode_degradation = 0.0  # 0 = new, 1 = completely degraded
        self.membrane_fouling = 0.0  # Affects efficiency
        self.stack_hours = 0.0  # Operating hours
        
        # Performance coefficients
        self.max_efficiency = 0.85  # 85% electrical efficiency (HHV basis)
        self.optimal_current_density = 1.0  # A/cm² for optimal efficiency
        self.current_density = 0.0  # Current operating point
        
        # Operating limits
        self.limits.max_temperature_k = 373.0  # 100°C (boiling water limit)
        self.limits.max_pressure_kpa = 7000.0  # 70 bar maximum safe pressure
        self.limits.max_flow_rate_kg_hr = target_h2_rate_kg_hr * 1.5
        self.limits.min_flow_rate_kg_hr = target_h2_rate_kg_hr * 0.02  # 2% minimum
        
        # Gas purity and separation
        self.h2_purity = 0.995  # 99.5% purity after separation
        self.o2_purity = 0.990  # 99.0% purity
        self.water_recovery_efficiency = 0.98  # 98% of unreacted water recovered
        
        # Statistics
        self.total_h2_produced_kg = 0.0
        self.total_o2_produced_kg = 0.0
        self.total_h2o_consumed_kg = 0.0
        self.total_energy_consumed_kwh = 0.0
        self.electrode_cycles = 0.0
        
        # Maintenance scheduling
        self.electrode_replacement_interval_hrs = 17520.0  # 2 years
        self.membrane_replacement_interval_hrs = 43800.0  # 5 years
        self.last_electrode_replacement = 0.0
        self.last_membrane_replacement = 0.0
        
    def simulate(self, plant_state: PlantState, dt_seconds: float) -> Dict[str, Any]:
        """Simulate electrolysis operation."""
        
        # Calculate required power
        target_power_kw = self.target_h2_rate_kg_hr * self.power_per_kg_h2
        min_power_kw = target_power_kw * self.min_power_fraction
        
        # Set power requirements
        self.min_power_kw = min_power_kw
        self.max_power_kw = target_power_kw * 1.1
        
        # Request power
        self.request_power(plant_state, target_power_kw)
        
        # Update electrode condition
        self._update_electrode_condition(dt_seconds)
        
        # Calculate production rates based on available water and power
        production_rates = self._calculate_production_rates(plant_state)
        
        # Execute the electrolysis (consume water, produce H₂ and O₂)
        products_produced = self._execute_electrolysis(plant_state, production_rates, dt_seconds)
        
        # Update thermal and pressure state
        self._update_thermal_state(plant_state, production_rates, dt_seconds)
        
        # Update statistics
        self._update_statistics(products_produced, dt_seconds)
        
        # Check maintenance needs
        self._check_maintenance_schedule(plant_state)
        
        return {
            "h2_production_kg_hr": self.current_h2_rate_kg_hr,
            "o2_production_kg_hr": self.current_o2_rate_kg_hr,
            "h2o_consumption_kg_hr": self.current_h2o_consumption_kg_hr,
            "h2_produced_kg": products_produced.get("H2", 0.0),
            "o2_produced_kg": products_produced.get("O2", 0.0),
            "efficiency": self.current_efficiency,
            "cell_voltage": self.current_cell_voltage,
            "electrode_degradation": self.electrode_degradation,
            "operating_temperature_k": self.current_temperature_k,
            "operating_pressure_kpa": self.current_pressure_kpa,
            "power_consumption_kw": self.power_allocated_kw,
            "total_h2_produced_kg": self.total_h2_produced_kg
        }
    
    def _update_electrode_condition(self, dt_seconds: float):
        """Update electrode degradation based on operating conditions."""
        
        # Degradation rate depends on current density and temperature
        if self.current_h2_rate_kg_hr > 0:
            # Base degradation rate: 0.1% per 1000 hours
            base_degradation_rate = 0.001 / (1000 * 3600.0)  # per second
            
            # Current density factor (higher current = faster degradation)
            load_factor = self.current_h2_rate_kg_hr / self.target_h2_rate_kg_hr
            current_factor = 1.0 + (load_factor - 0.5) * 2.0  # Peak at 100% load
            
            # Temperature factor (higher temp = faster degradation)
            temp_factor = 1.0
            if self.current_temperature_k > self.operating_temperature_k:
                excess_temp = self.current_temperature_k - self.operating_temperature_k
                temp_factor = 1.0 + (excess_temp / 50.0) ** 1.5
            
            # Apply degradation
            degradation_rate = base_degradation_rate * current_factor * temp_factor
            degradation_increase = degradation_rate * dt_seconds
            self.electrode_degradation = min(0.9, self.electrode_degradation + degradation_increase)
            
            # Track operating hours
            self.stack_hours += dt_seconds / 3600.0
        
        # Membrane fouling (slower process)
        if self.current_h2_rate_kg_hr > 0:
            fouling_rate = 0.0001 / (8760 * 3600.0)  # 0.01% per year
            fouling_increase = fouling_rate * dt_seconds
            self.membrane_fouling = min(0.8, self.membrane_fouling + fouling_increase)
    
    def _calculate_production_rates(self, plant_state: PlantState) -> Dict[str, float]:
        """Calculate production rates based on available water and power."""
        
        # Check available water
        h2o_store = plant_state.get_material("H2O")
        available_h2o_kg = h2o_store.mass_kg
        
        # Calculate maximum possible H₂ production based on water
        # Need 9 kg H₂O per kg H₂
        max_h2_from_h2o = available_h2o_kg / self.h2o_to_h2_ratio
        water_limited_h2_kg_hr = max_h2_from_h2o * 3600.0  # Convert to hourly
        
        # Power-limited maximum rate
        if self.power_allocated_kw < self.min_power_kw:
            power_limited_h2_kg_hr = 0.0
        else:
            power_limited_h2_kg_hr = self.power_allocated_kw / self.power_per_kg_h2
        
        # Design-limited maximum rate
        design_limited_h2_kg_hr = self.target_h2_rate_kg_hr
        
        # Condition-dependent efficiency
        voltage_efficiency = self._calculate_voltage_efficiency()
        thermal_efficiency = self._calculate_thermal_efficiency()
        electrode_efficiency = 1.0 - self.electrode_degradation * 0.6  # Max 60% loss
        membrane_efficiency = 1.0 - self.membrane_fouling * 0.3  # Max 30% loss
        
        overall_efficiency = (voltage_efficiency * thermal_efficiency * 
                            electrode_efficiency * membrane_efficiency)
        
        # Actual production rate
        potential_h2_kg_hr = min(
            water_limited_h2_kg_hr,
            power_limited_h2_kg_hr,
            design_limited_h2_kg_hr
        )
        
        self.current_h2_rate_kg_hr = potential_h2_kg_hr * overall_efficiency
        self.current_efficiency = overall_efficiency
        
        # Calculate corresponding rates
        self.current_h2o_consumption_kg_hr = self.current_h2_rate_kg_hr * self.h2o_to_h2_ratio
        self.current_o2_rate_kg_hr = self.current_h2_rate_kg_hr * self.o2_to_h2_ratio
        
        # Update operating conditions
        if self.current_h2_rate_kg_hr > 0:
            load_factor = self.current_h2_rate_kg_hr / self.target_h2_rate_kg_hr
            self.current_density = self.optimal_current_density * load_factor
            
            # Cell voltage increases with current density
            self.current_cell_voltage = 1.23 + 0.25 * load_factor + 0.1 * (1 - electrode_efficiency)
        else:
            self.current_density = 0.0
            self.current_cell_voltage = 1.23  # Open circuit voltage
        
        return {
            "h2_production": self.current_h2_rate_kg_hr,
            "o2_production": self.current_o2_rate_kg_hr,
            "h2o_consumption": self.current_h2o_consumption_kg_hr
        }
    
    def _calculate_voltage_efficiency(self) -> float:
        """Calculate efficiency based on cell voltage."""
        # Theoretical minimum: 1.23V, practical range: 1.4-2.0V
        if self.current_cell_voltage <= 1.23:
            return 1.0
        else:
            # Efficiency drops as voltage increases
            return min(1.0, 1.23 / self.current_cell_voltage)
    
    def _calculate_thermal_efficiency(self) -> float:
        """Calculate efficiency factor based on temperature."""
        # PEM electrolyzers work best at 70-90°C
        optimal_range_low = 343.0  # 70°C
        optimal_range_high = 363.0  # 90°C
        
        if optimal_range_low <= self.current_temperature_k <= optimal_range_high:
            return 1.0
        elif self.current_temperature_k < optimal_range_low:
            # Lower efficiency when too cold
            return 0.7 + 0.3 * (self.current_temperature_k - 273.0) / (optimal_range_low - 273.0)
        else:
            # Efficiency drops when too hot
            temp_excess = self.current_temperature_k - optimal_range_high
            return max(0.5, 1.0 - temp_excess / 50.0)
    
    def _execute_electrolysis(self, plant_state: PlantState, rates: Dict[str, float], 
                            dt_seconds: float) -> Dict[str, float]:
        """Execute electrolysis: consume water and produce H₂ and O₂."""
        
        if rates["h2_production"] <= 0:
            return {"H2": 0.0, "O2": 0.0}
        
        # Calculate amounts for this timestep
        dt_hours = dt_seconds / 3600.0
        
        h2o_needed_kg = rates["h2o_consumption"] * dt_hours
        h2_produced_kg = rates["h2_production"] * dt_hours
        o2_produced_kg = rates["o2_production"] * dt_hours
        
        # Attempt to withdraw water
        h2o_store = plant_state.get_material("H2O")
        actual_h2o_consumed = h2o_store.withdraw(h2o_needed_kg)
        
        # Check if we got enough water
        if actual_h2o_consumed < h2o_needed_kg * 0.99:
            # Insufficient water - scale back production
            limiting_factor = actual_h2o_consumed / h2o_needed_kg if h2o_needed_kg > 0 else 0
            
            h2_produced_kg *= limiting_factor
            o2_produced_kg *= limiting_factor
            
            logger.warning(f"Electrolysis limited by water: {limiting_factor:.1%} of target rate")
        
        # Apply gas purity factors
        pure_h2_kg = h2_produced_kg * self.h2_purity
        pure_o2_kg = o2_produced_kg * self.o2_purity
        
        # Store products
        h2_store = plant_state.get_material("H2")
        o2_store = plant_state.get_material("O2")
        
        actual_h2_stored = h2_store.store(pure_h2_kg)
        actual_o2_stored = o2_store.store(pure_o2_kg)
        
        # Check for storage constraints
        if actual_h2_stored < pure_h2_kg:
            logger.warning(f"H₂ storage full: only stored {actual_h2_stored:.2f} kg of {pure_h2_kg:.2f} kg produced")
        
        if actual_o2_stored < pure_o2_kg:
            logger.warning(f"O₂ storage full: only stored {actual_o2_stored:.2f} kg of {pure_o2_kg:.2f} kg produced")
        
        # Set product properties (high pressure H₂ and O₂)
        h2_store.set_physical_properties(
            pressure_kpa=self.current_pressure_kpa,
            temperature_k=self.current_temperature_k
        )
        
        o2_store.set_physical_properties(
            pressure_kpa=self.current_pressure_kpa * 0.5,  # O₂ at lower pressure
            temperature_k=self.current_temperature_k
        )
        
        return {
            "H2": actual_h2_stored,
            "O2": actual_o2_stored
        }
    
    def _update_thermal_state(self, plant_state: PlantState, rates: Dict[str, float], dt_seconds: float):
        """Update thermal state based on electrical heating and cooling."""
        env = plant_state.environment
        
        if rates["h2_production"] > 0:
            # Heat generation from electrical losses
            electrical_power_kw = self.power_allocated_kw
            theoretical_power_kw = rates["h2_production"] * (1.23 * 96485 / 3600) / 1000  # Theoretical minimum
            
            waste_heat_kw = electrical_power_kw - theoretical_power_kw
            
            # Temperature rise from waste heat (simplified)
            thermal_mass_j_per_k = 100000.0  # Stack thermal mass
            temp_rise_per_s = (waste_heat_kw * 1000.0) / thermal_mass_j_per_k
            heating_effect = temp_rise_per_s * dt_seconds
            
            # Cooling to environment
            temp_diff = self.current_temperature_k - env.ambient_temperature_k
            cooling_rate = 0.002 * temp_diff  # K/s cooling rate
            cooling_effect = cooling_rate * dt_seconds
            
            # Net temperature change
            net_temp_change = heating_effect - cooling_effect
            self.current_temperature_k += net_temp_change
            
            # Active thermal management to maintain operating temperature
            target_temp = self.operating_temperature_k
            temp_error = self.current_temperature_k - target_temp
            
            # Temperature control (simplified)
            if abs(temp_error) > 10.0:  # Outside control band
                control_correction = -0.05 * temp_error * dt_seconds
                self.current_temperature_k += control_correction
        else:
            # Cool down to ambient when not operating
            temp_diff = self.current_temperature_k - env.ambient_temperature_k
            cooling_rate = 0.001 * temp_diff
            self.current_temperature_k -= cooling_rate * dt_seconds
        
        # Maintain reasonable bounds
        self.current_temperature_k = max(env.ambient_temperature_k, self.current_temperature_k)
        self.current_temperature_k = min(self.limits.max_temperature_k, self.current_temperature_k)
        
        # Pressure control (H₂ and O₂ pressure regulation)
        if rates["h2_production"] > 0:
            self.current_pressure_kpa = self.operating_pressure_kpa
        else:
            # Depressurize when not operating
            depressure_rate = 100.0  # kPa/s
            self.current_pressure_kpa = max(
                env.atmospheric_pressure_pa / 1000.0,
                self.current_pressure_kpa - depressure_rate * dt_seconds
            )
    
    def _update_statistics(self, products: Dict[str, float], dt_seconds: float):
        """Update production statistics."""
        
        self.total_h2_produced_kg += products.get("H2", 0.0)
        self.total_o2_produced_kg += products.get("O2", 0.0)
        self.total_energy_consumed_kwh += self.power_allocated_kw * (dt_seconds / 3600.0)
        
        # Electrode cycle counting
        if self.current_h2_rate_kg_hr > 0:
            cycle_fraction = (self.current_h2_rate_kg_hr * dt_seconds / 3600.0) / self.target_h2_rate_kg_hr
            self.electrode_cycles += cycle_fraction
    
    def _check_maintenance_schedule(self, plant_state: PlantState):
        """Check if electrode or membrane replacement is due."""
        current_time_hrs = plant_state.current_time / 3600.0
        
        # Electrode replacement check
        if (current_time_hrs - self.last_electrode_replacement >= self.electrode_replacement_interval_hrs or
            self.electrode_degradation >= 0.7):
            
            if self.status != ModuleStatus.SHUTDOWN:
                logger.info(f"Electrode replacement due: degradation {self.electrode_degradation:.1%}")
                self._perform_electrode_replacement(current_time_hrs)
        
        # Membrane replacement check
        if (current_time_hrs - self.last_membrane_replacement >= self.membrane_replacement_interval_hrs or
            self.membrane_fouling >= 0.6):
            
            if self.status != ModuleStatus.SHUTDOWN:
                logger.info(f"Membrane replacement due: fouling {self.membrane_fouling:.1%}")
                self._perform_membrane_replacement(current_time_hrs)
    
    def _perform_electrode_replacement(self, current_time_hrs: float):
        """Perform electrode replacement maintenance."""
        self.electrode_degradation = 0.0
        self.last_electrode_replacement = current_time_hrs
        logger.info(f"Electrode replacement completed")
    
    def _perform_membrane_replacement(self, current_time_hrs: float):
        """Perform membrane replacement maintenance."""
        self.membrane_fouling = 0.0
        self.last_membrane_replacement = current_time_hrs
        logger.info(f"Membrane replacement completed")
    
    def get_electrolysis_summary(self) -> Dict[str, Any]:
        """Get comprehensive electrolysis status."""
        return {
            "production": {
                "h2_rate_kg_hr": self.current_h2_rate_kg_hr,
                "o2_rate_kg_hr": self.current_o2_rate_kg_hr,
                "target_h2_rate_kg_hr": self.target_h2_rate_kg_hr,
                "efficiency": self.current_efficiency,
                "total_h2_kg": self.total_h2_produced_kg,
                "total_o2_kg": self.total_o2_produced_kg
            },
            "consumption": {
                "h2o_rate_kg_hr": self.current_h2o_consumption_kg_hr,
                "power_kw": self.power_allocated_kw,
                "specific_energy_kwh_per_kg_h2": (self.power_allocated_kw / self.current_h2_rate_kg_hr) if self.current_h2_rate_kg_hr > 0 else 0,
                "total_energy_kwh": self.total_energy_consumed_kwh
            },
            "conditions": {
                "temperature_k": self.current_temperature_k,
                "temperature_c": self.current_temperature_k - 273.15,
                "pressure_kpa": self.current_pressure_kpa,
                "cell_voltage": self.current_cell_voltage,
                "current_density": self.current_density
            },
            "health": {
                "electrode_degradation": self.electrode_degradation,
                "membrane_fouling": self.membrane_fouling,
                "stack_hours": self.stack_hours,
                "electrode_cycles": self.electrode_cycles,
                "electrode_replacement_due_hrs": self.electrode_replacement_interval_hrs - (self.stack_hours - self.last_electrode_replacement)
            },
            "status": {
                "module_status": self.status.value,
                "healthy": (self.electrode_degradation < 0.5 and 
                          self.membrane_fouling < 0.4 and 
                          self.current_temperature_k < self.limits.max_temperature_k),
                "gas_purity": {"h2": self.h2_purity, "o2": self.o2_purity}
            }
        }
    
    def force_electrode_replacement(self):
        """Manually trigger electrode replacement."""
        self.electrode_degradation = 0.0
        logger.info(f"Manual electrode replacement completed")
    
    def force_membrane_replacement(self):
        """Manually trigger membrane replacement."""
        self.membrane_fouling = 0.0
        logger.info(f"Manual membrane replacement completed")
    
    def set_target_production_rate(self, target_kg_hr: float):
        """Adjust target H₂ production rate."""
        if target_kg_hr < 0:
            raise ValueError("Target production rate cannot be negative")
        
        old_target = self.target_h2_rate_kg_hr
        self.target_h2_rate_kg_hr = target_kg_hr
        
        # Update operating limits
        self.limits.max_flow_rate_kg_hr = target_kg_hr * 1.5
        self.limits.min_flow_rate_kg_hr = target_kg_hr * 0.02
        
        logger.info(f"Target H₂ production changed from {old_target:.0f} to {target_kg_hr:.0f} kg/hr")
    
    def __repr__(self) -> str:
        return (f"ElectrolysisModule(target: {self.target_h2_rate_kg_hr:.0f} kg/hr H₂, "
                f"actual: {self.current_h2_rate_kg_hr:.0f} kg/hr, "
                f"efficiency: {self.current_efficiency:.1%}, "
                f"voltage: {self.current_cell_voltage:.2f}V, "
                f"status: {self.status.value})") 