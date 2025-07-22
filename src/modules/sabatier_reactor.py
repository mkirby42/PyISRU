import math
from typing import Dict, Any, Optional
import logging

from core import BaseModule, PlantState, ModuleStatus

logger = logging.getLogger(__name__)

class SabatierReactorModule(BaseModule):
    """
    Sabatier reactor module for Mars ISRU plant.
    Performs the reaction: CO₂ + 4H₂ → CH₄ + 2H₂O
    
    Key design considerations:
    - Temperature-dependent reaction kinetics
    - Catalyst activity and degradation
    - Heat management (exothermic reaction)
    - Stoichiometric flow control
    """
    
    def __init__(self, 
                 name: str = "SabatierReactor",
                 target_ch4_rate_kg_hr: float = 460.0,  # ~11,000 kg/day per PRD
                 operating_temperature_k: float = 623.0,  # 350°C optimal
                 operating_pressure_kpa: float = 300.0,  # 3 bar
                 ignore_temp_overage: bool = False):
        
        super().__init__(name, priority=2, ignore_temp_overage=ignore_temp_overage)
        
        # Design parameters
        self.target_ch4_rate_kg_hr = target_ch4_rate_kg_hr
        self.operating_temperature_k = operating_temperature_k
        self.operating_pressure_kpa = operating_pressure_kpa
        
        # Reaction stoichiometry: CO₂ + 4H₂ → CH₄ + 2H₂O
        # Molecular weights: CO₂=44, H₂=2, CH₄=16, H₂O=18
        self.mw_co2 = 44.0
        self.mw_h2 = 2.0
        self.mw_ch4 = 16.0
        self.mw_h2o = 18.0
        
        # Stoichiometric ratios (mass basis)
        self.co2_to_ch4_ratio = self.mw_co2 / self.mw_ch4  # 2.75 kg CO₂ per kg CH₄
        self.h2_to_ch4_ratio = (4 * self.mw_h2) / self.mw_ch4  # 0.5 kg H₂ per kg CH₄
        self.h2o_to_ch4_ratio = (2 * self.mw_h2o) / self.mw_ch4  # 2.25 kg H₂O per kg CH₄
        
        # Power requirements (heating, mixing, control)
        # Baseline: ~200 kWh/kg CH₄ from PRD
        self.power_per_kg_ch4 = 200.0  # kW per kg/hr CH₄ throughput
        self.min_power_fraction = 0.15  # Minimum 15% power to maintain temperature
        
        # Current operating state
        self.current_ch4_rate_kg_hr = 0.0
        self.current_co2_consumption_kg_hr = 0.0
        self.current_h2_consumption_kg_hr = 0.0
        self.current_h2o_production_kg_hr = 0.0
        self.current_temperature_k = 298.0  # Room temperature startup
        self.current_pressure_kpa = 101.3
        self.current_conversion_efficiency = 0.0
        
        # Catalyst state
        self.catalyst_activity = 1.0  # 1.0 = fresh catalyst, 0.0 = dead
        self.catalyst_temp_damage = 0.0  # Thermal deactivation
        self.catalyst_poison_level = 0.0  # Chemical poisoning
        self.total_operating_time_hrs = 0.0
        
        # Performance coefficients
        self.max_conversion_efficiency = 0.95  # 95% theoretical max
        self.optimal_temperature_k = 623.0  # 350°C
        self.optimal_pressure_kpa = 300.0   # 3 bar
        
        # Operating limits
        self.limits.max_temperature_k = 673.0  # 400°C (catalyst sintering limit)
        self.limits.max_pressure_kpa = 2000.0  # 20 bar safety limit
        self.limits.max_flow_rate_kg_hr = target_ch4_rate_kg_hr * 1.2
        self.limits.min_flow_rate_kg_hr = target_ch4_rate_kg_hr * 0.05  # 5% minimum
        
        # Heat management
        self.reaction_heat_kj_per_mol_ch4 = -165.0  # Exothermic reaction
        self.heat_capacity_j_per_k = 50000.0  # Reactor thermal mass
        self.heat_loss_coefficient = 0.1  # Heat loss to environment
        
        # Statistics
        self.total_ch4_produced_kg = 0.0
        self.total_h2o_produced_kg = 0.0
        self.total_co2_consumed_kg = 0.0
        self.total_h2_consumed_kg = 0.0
        self.catalyst_cycles = 0.0
        
        # Maintenance scheduling
        self.catalyst_replacement_interval_hrs = 8760.0  # 1 year
        self.last_catalyst_replacement = 0.0
        
    def simulate(self, plant_state: PlantState, dt_seconds: float) -> Dict[str, Any]:
        """Simulate Sabatier reactor operation."""
        
        # Calculate required power
        target_power_kw = self.target_ch4_rate_kg_hr * self.power_per_kg_ch4
        min_power_kw = target_power_kw * self.min_power_fraction
        
        # Set power requirements
        self.min_power_kw = min_power_kw
        self.max_power_kw = target_power_kw * 1.1
        
        # Request power
        self.request_power(plant_state, target_power_kw)
        
        # Update catalyst condition
        self._update_catalyst_condition(dt_seconds)
        
        # Calculate reaction rates based on available materials and conditions
        reaction_rates = self._calculate_reaction_rates(plant_state)
        
        # Execute the reaction (consume reactants, produce products)
        products_produced = self._execute_reaction(plant_state, reaction_rates, dt_seconds)
        
        # Update thermal state
        self._update_thermal_state(plant_state, reaction_rates, dt_seconds)
        
        # Update statistics
        self._update_statistics(products_produced, dt_seconds, plant_state)
        
        # Check maintenance needs
        self._check_maintenance_schedule(plant_state)
        
        return {
            "ch4_production_kg_hr": self.current_ch4_rate_kg_hr,
            "co2_consumption_kg_hr": self.current_co2_consumption_kg_hr,
            "h2_consumption_kg_hr": self.current_h2_consumption_kg_hr,
            "h2o_production_kg_hr": self.current_h2o_production_kg_hr,
            "ch4_produced_kg": products_produced.get("CH4", 0.0),
            "h2o_produced_kg": products_produced.get("H2O", 0.0),
            "conversion_efficiency": self.current_conversion_efficiency,
            "catalyst_activity": self.catalyst_activity,
            "reactor_temperature_k": self.current_temperature_k,
            "reactor_pressure_kpa": self.current_pressure_kpa,
            "power_consumption_kw": self.power_allocated_kw,
            "total_ch4_produced_kg": self.total_ch4_produced_kg
        }
    
    def _update_catalyst_condition(self, dt_seconds: float):
        """Update catalyst activity based on operating conditions and time."""
        
        # Thermal deactivation (high temperature damage)
        if self.current_temperature_k > self.optimal_temperature_k:
            excess_temp = self.current_temperature_k - self.optimal_temperature_k
            temp_damage_rate = 0.001 * (excess_temp / 50.0) ** 2  # Exponential damage
            temp_damage_increase = temp_damage_rate * (dt_seconds / 3600.0)
            self.catalyst_temp_damage = min(1.0, self.catalyst_temp_damage + temp_damage_increase)
        
        # Time-based deactivation (sintering, fouling)
        if self.current_ch4_rate_kg_hr > 0:
            time_deactivation_rate = 0.0001 / 3600.0  # 0.01% per hour
            load_factor = self.current_ch4_rate_kg_hr / self.target_ch4_rate_kg_hr
            actual_deactivation = time_deactivation_rate * load_factor * (dt_seconds / 3600.0)
            
            self.catalyst_activity = max(0.1, self.catalyst_activity - actual_deactivation)
            self.total_operating_time_hrs += dt_seconds / 3600.0
        
        # Overall catalyst activity
        self.catalyst_activity *= (1.0 - self.catalyst_temp_damage * 0.5)  # Max 50% thermal damage
        self.catalyst_activity = max(0.05, self.catalyst_activity)  # Minimum 5% activity
    
    def _calculate_reaction_rates(self, plant_state: PlantState) -> Dict[str, float]:
        """Calculate reaction rates based on available reactants and conditions."""
        
        # Check available reactants
        co2_store = plant_state.get_material("CO2")
        h2_store = plant_state.get_material("H2")
        
        available_co2_kg = co2_store.mass_kg
        available_h2_kg = h2_store.mass_kg
        
        # Calculate maximum possible CH₄ production based on reactants
        # Limited by stoichiometry: need 2.75 kg CO₂ + 0.5 kg H₂ per kg CH₄
        max_ch4_from_co2 = available_co2_kg / self.co2_to_ch4_ratio
        max_ch4_from_h2 = available_h2_kg / self.h2_to_ch4_ratio
        
        # Reactant-limited maximum rate
        reactant_limited_ch4_kg_hr = min(max_ch4_from_co2, max_ch4_from_h2) * 3600.0  # Convert to hourly
        
        # Power-limited maximum rate
        if self.power_allocated_kw < self.min_power_kw:
            power_limited_ch4_kg_hr = 0.0
        else:
            power_limited_ch4_kg_hr = self.power_allocated_kw / self.power_per_kg_ch4
        
        # Design-limited maximum rate
        design_limited_ch4_kg_hr = self.target_ch4_rate_kg_hr
        
        # Condition-dependent efficiency
        temp_efficiency = self._calculate_temperature_efficiency()
        pressure_efficiency = self._calculate_pressure_efficiency()
        catalyst_efficiency = self.catalyst_activity
        
        overall_efficiency = temp_efficiency * pressure_efficiency * catalyst_efficiency
        
        # Actual production rate
        potential_ch4_kg_hr = min(
            reactant_limited_ch4_kg_hr,
            power_limited_ch4_kg_hr,
            design_limited_ch4_kg_hr
        )
        
        self.current_ch4_rate_kg_hr = potential_ch4_kg_hr * overall_efficiency
        self.current_conversion_efficiency = overall_efficiency
        
        # Calculate corresponding consumption rates
        self.current_co2_consumption_kg_hr = self.current_ch4_rate_kg_hr * self.co2_to_ch4_ratio
        self.current_h2_consumption_kg_hr = self.current_ch4_rate_kg_hr * self.h2_to_ch4_ratio
        self.current_h2o_production_kg_hr = self.current_ch4_rate_kg_hr * self.h2o_to_ch4_ratio
        
        return {
            "ch4_production": self.current_ch4_rate_kg_hr,
            "co2_consumption": self.current_co2_consumption_kg_hr,
            "h2_consumption": self.current_h2_consumption_kg_hr,
            "h2o_production": self.current_h2o_production_kg_hr
        }
    
    def _calculate_temperature_efficiency(self) -> float:
        """Calculate efficiency factor based on temperature."""
        # Arrhenius-like temperature dependence
        # Peak efficiency at optimal temperature, drops off at extremes
        
        if self.current_temperature_k < 400.0:  # Too cold
            return 0.1 * (self.current_temperature_k / 400.0)
        elif self.current_temperature_k > 700.0:  # Too hot
            return 0.1 * (700.0 / self.current_temperature_k)
        else:
            # Bell curve around optimal temperature
            temp_deviation = abs(self.current_temperature_k - self.optimal_temperature_k)
            return max(0.3, 1.0 - (temp_deviation / 100.0) ** 2)
    
    def _calculate_pressure_efficiency(self) -> float:
        """Calculate efficiency factor based on pressure."""
        # Higher pressure generally favors the reaction (Le Chatelier's principle)
        if self.current_pressure_kpa < 50.0:  # Too low
            return 0.2
        elif self.current_pressure_kpa > 1000.0:  # Diminishing returns
            return 0.95
        else:
            # Logarithmic increase with pressure
            return 0.2 + 0.75 * math.log(self.current_pressure_kpa / 50.0) / math.log(20.0)
    
    def _execute_reaction(self, plant_state: PlantState, rates: Dict[str, float], 
                         dt_seconds: float) -> Dict[str, float]:
        """Execute the reaction: consume reactants and produce products."""
        
        if rates["ch4_production"] <= 0:
            return {"CH4": 0.0, "H2O": 0.0}
        
        # Calculate amounts for this timestep
        dt_hours = dt_seconds / 3600.0
        
        co2_needed_kg = rates["co2_consumption"] * dt_hours
        h2_needed_kg = rates["h2_consumption"] * dt_hours
        ch4_produced_kg = rates["ch4_production"] * dt_hours
        h2o_produced_kg = rates["h2o_production"] * dt_hours
        
        # Attempt to withdraw reactants
        co2_store = plant_state.get_material("CO2")
        h2_store = plant_state.get_material("H2")
        
        actual_co2_consumed = co2_store.withdraw(co2_needed_kg)
        actual_h2_consumed = h2_store.withdraw(h2_needed_kg)
        
        # Check if we got enough reactants (should be true based on calculation)
        if actual_co2_consumed < co2_needed_kg * 0.99 or actual_h2_consumed < h2_needed_kg * 0.99:
            # Insufficient reactants - scale back production
            limiting_factor = min(
                actual_co2_consumed / co2_needed_kg if co2_needed_kg > 0 else 0,
                actual_h2_consumed / h2_needed_kg if h2_needed_kg > 0 else 0
            )
            
            ch4_produced_kg *= limiting_factor
            h2o_produced_kg *= limiting_factor
            
            logger.warning(f"Sabatier reaction limited by reactants: {limiting_factor:.1%} of target rate")
        
        # Store products
        ch4_store = plant_state.get_material("CH4")
        h2o_store = plant_state.get_material("H2O")
        
        actual_ch4_stored = ch4_store.store(ch4_produced_kg)
        actual_h2o_stored = h2o_store.store(h2o_produced_kg)
        
        # Check for storage constraints
        if actual_ch4_stored < ch4_produced_kg:
            logger.warning(f"CH₄ storage full: only stored {actual_ch4_stored:.2f} kg of {ch4_produced_kg:.2f} kg produced")
        
        if actual_h2o_stored < h2o_produced_kg:
            logger.warning(f"H₂O storage full: only stored {actual_h2o_stored:.2f} kg of {h2o_produced_kg:.2f} kg produced")
        
        # Set product properties
        ch4_store.set_physical_properties(
            pressure_kpa=self.current_pressure_kpa,
            temperature_k=self.current_temperature_k
        )
        
        h2o_store.set_physical_properties(
            pressure_kpa=self.current_pressure_kpa,
            temperature_k=self.current_temperature_k
        )
        
        return {
            "CH4": actual_ch4_stored,
            "H2O": actual_h2o_stored
        }
    
    def _update_thermal_state(self, plant_state: PlantState, rates: Dict[str, float], dt_seconds: float):
        """Update reactor temperature based on reaction heat and heat management."""
        env = plant_state.environment
        
        if rates["ch4_production"] > 0:
            # Heat generation from exothermic reaction
            # Convert kg/hr CH₄ to mol/s, then calculate heat generation
            ch4_mol_per_s = (rates["ch4_production"] / 3600.0) / (self.mw_ch4 / 1000.0)  # mol/s
            heat_generation_w = ch4_mol_per_s * abs(self.reaction_heat_kj_per_mol_ch4) * 1000.0  # W
            
            # Temperature rise from reaction heat
            temp_rise_per_s = heat_generation_w / self.heat_capacity_j_per_k
            reaction_heating = temp_rise_per_s * dt_seconds
            
            # Heat loss to environment
            temp_diff = self.current_temperature_k - env.ambient_temperature_k
            heat_loss_per_s = self.heat_loss_coefficient * temp_diff
            cooling_per_s = heat_loss_per_s / self.heat_capacity_j_per_k
            environmental_cooling = cooling_per_s * dt_seconds
            
            # Net temperature change
            net_temp_change = reaction_heating - environmental_cooling
            self.current_temperature_k += net_temp_change
            
            # Heating/cooling system to maintain target temperature
            target_temp = self.operating_temperature_k
            temp_error = self.current_temperature_k - target_temp
            
            # Simple proportional control (would be PID in reality)
            if abs(temp_error) > 5.0:  # Dead band of ±5K
                control_action = -0.1 * temp_error  # Proportional gain
                self.current_temperature_k += control_action * dt_seconds
        else:
            # Cool down to ambient when not operating
            temp_diff = self.current_temperature_k - env.ambient_temperature_k
            cooling_rate = 0.001 * temp_diff  # K/s
            self.current_temperature_k -= cooling_rate * dt_seconds
        
        # Maintain reasonable bounds
        self.current_temperature_k = max(env.ambient_temperature_k, self.current_temperature_k)
        self.current_temperature_k = min(self.limits.max_temperature_k, self.current_temperature_k)
        
        # Pressure is approximately proportional to temperature (ideal gas)
        # Plus contribution from reaction (4 moles gas → 3 moles gas = net reduction)
        if rates["ch4_production"] > 0:
            self.current_pressure_kpa = self.operating_pressure_kpa
        else:
            self.current_pressure_kpa = env.atmospheric_pressure_pa / 1000.0
    
    def _update_statistics(self, products: Dict[str, float], dt_seconds: float, plant_state):
        """Update production statistics."""
        
        self.total_ch4_produced_kg += products.get("CH4", 0.0)
        self.total_h2o_produced_kg += products.get("H2O", 0.0)
        
        # Update plant-wide totals
        plant_state.update_production_totals(
            ch4_produced_kg=products.get("CH4", 0.0),
            energy_consumed_kwh=self.power_allocated_kw * (dt_seconds / 3600.0)
        )
        
        # Catalyst cycle counting
        if self.current_ch4_rate_kg_hr > 0:
            cycle_fraction = (self.current_ch4_rate_kg_hr * dt_seconds / 3600.0) / self.target_ch4_rate_kg_hr
            self.catalyst_cycles += cycle_fraction
    
    def _check_maintenance_schedule(self, plant_state: PlantState):
        """Check if catalyst replacement is due."""
        current_time_hrs = plant_state.current_time / 3600.0
        
        # Catalyst replacement check
        if (current_time_hrs - self.last_catalyst_replacement >= self.catalyst_replacement_interval_hrs or
            self.catalyst_activity <= 0.3):
            
            if self.status != ModuleStatus.SHUTDOWN:
                logger.info(f"Catalyst replacement due: activity {self.catalyst_activity:.1%}")
                self._perform_catalyst_replacement(current_time_hrs)
    
    def _perform_catalyst_replacement(self, current_time_hrs: float):
        """Perform catalyst replacement maintenance."""
        self.catalyst_activity = 1.0
        self.catalyst_temp_damage = 0.0
        self.catalyst_poison_level = 0.0
        self.last_catalyst_replacement = current_time_hrs
        logger.info(f"Catalyst replacement completed")
    
    def get_reaction_summary(self) -> Dict[str, Any]:
        """Get comprehensive reaction status."""
        return {
            "production": {
                "ch4_rate_kg_hr": self.current_ch4_rate_kg_hr,
                "target_rate_kg_hr": self.target_ch4_rate_kg_hr,
                "efficiency": self.current_conversion_efficiency,
                "total_ch4_kg": self.total_ch4_produced_kg,
                "total_h2o_kg": self.total_h2o_produced_kg
            },
            "consumption": {
                "co2_rate_kg_hr": self.current_co2_consumption_kg_hr,
                "h2_rate_kg_hr": self.current_h2_consumption_kg_hr,
                "total_co2_kg": self.total_co2_consumed_kg,
                "total_h2_kg": self.total_h2_consumed_kg
            },
            "conditions": {
                "temperature_k": self.current_temperature_k,
                "temperature_c": self.current_temperature_k - 273.15,
                "pressure_kpa": self.current_pressure_kpa,
                "optimal_temp_k": self.optimal_temperature_k,
                "optimal_pressure_kpa": self.optimal_pressure_kpa
            },
            "catalyst": {
                "activity": self.catalyst_activity,
                "temp_damage": self.catalyst_temp_damage,
                "operating_hours": self.total_operating_time_hrs,
                "cycles": self.catalyst_cycles,
                "replacement_due_hrs": self.catalyst_replacement_interval_hrs - (self.total_operating_time_hrs - self.last_catalyst_replacement)
            },
            "status": {
                "module_status": self.status.value,
                "power_kw": self.power_allocated_kw,
                "healthy": self.catalyst_activity > 0.5 and self.current_temperature_k < self.limits.max_temperature_k
            }
        }
    
    def force_catalyst_replacement(self):
        """Manually trigger catalyst replacement."""
        self.catalyst_activity = 1.0
        self.catalyst_temp_damage = 0.0
        self.catalyst_poison_level = 0.0
        logger.info(f"Manual catalyst replacement completed")
    
    def set_target_production_rate(self, target_kg_hr: float):
        """Adjust target production rate."""
        if target_kg_hr < 0:
            raise ValueError("Target production rate cannot be negative")
        
        old_target = self.target_ch4_rate_kg_hr
        self.target_ch4_rate_kg_hr = target_kg_hr
        
        # Update operating limits
        self.limits.max_flow_rate_kg_hr = target_kg_hr * 1.2
        self.limits.min_flow_rate_kg_hr = target_kg_hr * 0.05
        
        logger.info(f"Target CH₄ production changed from {old_target:.0f} to {target_kg_hr:.0f} kg/hr")
    
    def __repr__(self) -> str:
        return (f"SabatierReactorModule(target: {self.target_ch4_rate_kg_hr:.0f} kg/hr CH₄, "
                f"actual: {self.current_ch4_rate_kg_hr:.0f} kg/hr, "
                f"efficiency: {self.current_conversion_efficiency:.1%}, "
                f"catalyst: {self.catalyst_activity:.1%}, "
                f"status: {self.status.value})") 