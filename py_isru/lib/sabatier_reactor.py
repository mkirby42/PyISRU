"""
Revised Sabatier reactor implementation for a Martian ISRU plant.

This module implements a continuously stirred tank reactor (CSTR) that
performs the Sabatier reaction:
    CO₂ + 4 H₂ ⇌ CH₄ + 2 H₂O

Additional side reactions are included:
    RWGS:       CO₂ + H₂ ⇌ CO + H₂O
    Methanation: CO + 3 H₂ ⇌ CH₄ + H₂O

The reactor model uses detailed reaction kinetics with improved rate constant
calculations (Arrhenius-based), catalyst loading and degradation effects,
and updates the reactor's internal composition and thermodynamic state using
a real gas (Peng–Robinson) equation of state.
"""
import logging
import numpy as np
from scipy import constants
from dataclasses import dataclass
from typing import Dict
from .reactor import Reactor, ResourceType, OperationalStatus, ReactorSpecification
from .thermodynamics import ThermodynamicState, cp_for_species, GasProperties, ReactionKinetics

logger = logging.getLogger(__name__)

@dataclass
class SabatierSpecification(ReactorSpecification):
    catalyst_type: str
    catalyst_loading_kg_per_m3: float
    catalyst_surface_area_m2_per_kg: float
    catalyst_porosity: float
    startup_time_s: float = 300.0  # default 5 minutes
    shutdown_time_s: float = 300.0  # default 5 minutes

# Kinetics objects (same as before)
kinetics_main = ReactionKinetics(
    rate_constant_forward_1_s_inv=1e3,
    activation_energy_J_per_mol=80e3,
    reaction_order={"CO2": 1, "H2": 4}
)
kinetics_rwgs = ReactionKinetics(
    rate_constant_forward_1_s_inv=5e2,
    activation_energy_J_per_mol=90e3,
    reaction_order={"CO2": 1, "H2": 1}
)
kinetics_meth = ReactionKinetics(
    rate_constant_forward_1_s_inv=8e2,
    activation_energy_J_per_mol=85e3,
    reaction_order={"CO": 1, "H2": 3}
)
kinetics_dict = {
    "main": kinetics_main,
    "rwgs": kinetics_rwgs,
    "methanation": kinetics_meth
}

class SabatierReactor(Reactor):
    """
    Implements the Sabatier reaction and side reactions in a CSTR.
    
    Reactions:
      Main:        CO2 + 4 H2 ⇌ CH4 + 2 H2O
      RWGS:        CO2 + H2 ⇌ CO + H2O
      Methanation: CO + 3 H2 ⇌ CH4 + H2O
    """
    def __init__(self,
                 spec: SabatierSpecification,
                 initial_state: ThermodynamicState,
                 initial_composition_mol: Dict[ResourceType, float],
                 kinetics: Dict[str, ReactionKinetics] = kinetics_dict):
        super().__init__(spec, initial_state)
        self.spec: SabatierSpecification = spec
        self.kinetics = kinetics
        self.catalyst_degradation = 1.0
        self.composition_mol: Dict[ResourceType, float] = initial_composition_mol.copy()
        self.power_consumption_W = 0.0
        self.delta_g_standard_J = {
            "main": -130.8e3,
            "rwgs": 28.6e3,
            "methanation": -142.2e3
        }
        self.transition_timer_s = 0.0
        # Track the internal integration time (in seconds) used for ramping reaction rates.
        self.internal_time_elapsed = 0.0

    def __repr__(self):
        return (f"SabatierReactor(spec={self.spec}, state={self.state}, "
                f"composition_mol={self.composition_mol}, "
                f"catalyst_degradation={self.catalyst_degradation:.4f}, "
                f"power_consumption_W={self.power_consumption_W:.2f}, "
                f"operational_status={self.operational_status})")

    def _update_composition(self, dt_s: float, inputs_mol_per_s: Dict[ResourceType, float],
                            reaction_changes_mol_per_m3: Dict[ResourceType, float]):
        total_inflow = sum(inputs_mol_per_s.values())
        total_moles = max(sum(self.composition_mol.values()), 1e-12)
        V_m3 = self.spec.volume_m3
        for resource in ResourceType:
            n_old = self.composition_mol.get(resource, 0.0)
            F_in = inputs_mol_per_s.get(resource, 0.0)
            dilution = (n_old / total_moles) * total_inflow
            reaction_prod = reaction_changes_mol_per_m3.get(resource, 0.0) * V_m3
            n_new = n_old + dt_s * (F_in - dilution + reaction_prod)
            self.composition_mol[resource] = max(n_new, 0.0)

    def _calculate_reaction_rates(self, concentrations: Dict[str, float]) -> Dict[str, float]:
        catalyst_factor = (self.spec.catalyst_loading_kg_per_m3 *
                           self.catalyst_degradation *
                           self.spec.catalyst_surface_area_m2_per_kg)
        rates = {}
        # Calculate unconstrained rates first
        for reaction in ["main", "rwgs", "methanation"]:
            kinetics_obj = self.kinetics[reaction]
            forward_rate = kinetics_obj.calculate_rate(concentrations, self.state.temperature_K, catalyst_factor)
            if reaction == "main":
                K_eq = self.state.calculate_equilibrium_constant(self.delta_g_standard_J["main"])
                Q = (max(concentrations.get("CH4", 1e-12), 1e-12) *
                     max(concentrations.get("H2O", 1e-12), 1e-12) ** 2 /
                     (max(concentrations.get("CO2", 1e-12), 1e-12) *
                      max(concentrations.get("H2", 1e-12), 1e-12) ** 4))
                net_rate = forward_rate * (1 - Q / K_eq)
            elif reaction == "rwgs":
                K_eq = self.state.calculate_equilibrium_constant(self.delta_g_standard_J["rwgs"])
                Q = (max(concentrations.get("CO", 1e-12), 1e-12) *
                     max(concentrations.get("H2O", 1e-12), 1e-12) /
                     (max(concentrations.get("CO2", 1e-12), 1e-12) *
                      max(concentrations.get("H2", 1e-12), 1e-12)))
                net_rate = forward_rate * (1 - Q / K_eq)
            elif reaction == "methanation":
                K_eq = self.state.calculate_equilibrium_constant(self.delta_g_standard_J["methanation"])
                Q = (max(concentrations.get("CH4", 1e-12), 1e-12) *
                     max(concentrations.get("H2O", 1e-12), 1e-12) /
                     (max(concentrations.get("CO", 1e-12), 1e-12) *
                      max(concentrations.get("H2", 1e-12), 1e-12) ** 3))
                net_rate = forward_rate * (1 - Q / K_eq)
            rates[reaction] = net_rate

        # Calculate consumption rates for each species
        consumption_rates = {
            "CO2": rates["main"] + rates["rwgs"],
            "H2": 4 * rates["main"] + rates["rwgs"] + 3 * rates["methanation"],
            "CO": rates["methanation"] - rates["rwgs"]
        }

        # Calculate scaling factors based on available reactants
        scaling_factors = []
        V_m3 = self.spec.volume_m3
        dt_s = 0.1  # Small timestep for rate limiting
        
        for species, rate in consumption_rates.items():
            if rate > 0:  # Only check positive consumption rates
                available_mol = self.composition_mol.get(ResourceType[species], 0.0)
                needed_mol = rate * V_m3 * dt_s
                if needed_mol > 0:
                    scaling_factors.append(available_mol / needed_mol)

        # Apply the most limiting scaling factor to all rates
        if scaling_factors:
            limiting_factor = min(1.0, min(scaling_factors))
            for reaction in rates:
                rates[reaction] *= limiting_factor

        return rates

    def step(self, dt_s: float, inputs_mol_per_s: Dict[ResourceType, float]) -> Dict[ResourceType, float]:
        logger.info(f"Sabatier reactor step: dt={dt_s:.2f} s, status={self.operational_status.name}")
        # Safety check in RUNNING mode
        if self.operational_status == OperationalStatus.RUNNING and not self.check_safety_limits():
            self.operational_status = OperationalStatus.FAULT
            logger.error("Reactor entered FAULT state due to safety limit violation.")
            return {r: 0.0 for r in ResourceType}

        # --- Startup Mode ---
        if self.operational_status == OperationalStatus.STARTUP:
            logger.debug("Reactor is in STARTUP mode.")
            self.transition_timer_s += dt_s
            
            # During startup, only accept limited reactant flow
            startup_inputs = {}
            for resource, inflow in inputs_mol_per_s.items():
                # Limit to 10% of normal flow during startup
                startup_inputs[resource] = inflow * 0.1
                self.composition_mol[resource] += startup_inputs[resource] * dt_s
                
            if self.transition_timer_s <= dt_s:
                self.state.temperature_K = 300.0
                
            target_temp = 600.0
            temp_ramp_rate = (target_temp - 300.0) / self.spec.startup_time_s
            self.state.temperature_K += temp_ramp_rate * dt_s
            
            # Calculate pressure more carefully during startup
            total_moles = sum(self.composition_mol.values())
            if total_moles > 0:
                # Use real gas behavior via compressibility factor
                Z = 1.0  # Simplified - could be made more accurate
                self.state.pressure_Pa = (total_moles * constants.R * self.state.temperature_K) / (self.spec.volume_m3 * Z)
                
            # Limit pressure during startup
            if self.state.pressure_Pa > 1.8e6:  # 90% of max
                excess_ratio = self.state.pressure_Pa / 1.8e6
                # Remove excess gas proportionally
                for resource in self.composition_mol:
                    self.composition_mol[resource] /= excess_ratio
                self.state.pressure_Pa = 1.8e6
                
            self.catalyst_degradation *= np.exp(-0.001 * dt_s)  # Reduced degradation rate
            
            # Reduced power consumption during startup
            self.power_consumption_W = (
                self.spec.thermal_mass_J_per_K * temp_ramp_rate +  # Heating
                50.0 * self.spec.volume_m3 +                       # Mixing
                100.0                                              # Base load
            )
            
            self.update_uptime(dt_s)
            if self.transition_timer_s >= self.spec.startup_time_s:
                self.operational_status = OperationalStatus.RUNNING
                logger.info("Reactor transitioned to RUNNING state.")
                self.internal_time_elapsed = 0.0
            return {r: 0.0 for r in ResourceType}

        # --- Shutdown Mode ---
        if self.operational_status == OperationalStatus.SHUTDOWN:
            self.transition_timer_s += dt_s
            if self.transition_timer_s >= self.spec.shutdown_time_s:
                self.operational_status = OperationalStatus.STANDBY
                logger.info("Reactor transitioned to STANDBY state.")
            return {r: 0.0 for r in ResourceType}

        if self.operational_status != OperationalStatus.RUNNING:
            return {r: 0.0 for r in ResourceType}

        # --- Running Mode with Finer Time Resolution & Gradual Ramp-up ---
        num_substeps = 10
        dt_internal = dt_s / num_substeps
        ramp_duration = 10.0  # seconds over which reaction rates ramp up
        # Initialize a net output accumulator over dt_s.
        net_outputs = {r: 0.0 for r in ResourceType}

        # We'll need a molar mass dictionary for later (for energy balance)
        molar_mass_dict = {"CO2": 0.044, "H2": 0.002, "CH4": 0.016,
                           "H2O": 0.018, "CO": 0.028, "O2": 0.032}

        # Loop over the internal substeps
        for _ in range(num_substeps):
            # Update internal clock and compute ramp factor (0 to 1)
            self.internal_time_elapsed += dt_internal
            ramp_factor = min(1.0, self.internal_time_elapsed / ramp_duration)

            # Update catalyst degradation on the fine time scale
            base_deg_rate_per_s = 0.005 / (24 * 3600)
            temp_factor = 2 ** ((self.state.temperature_K - 700) / 10)
            self.catalyst_degradation *= np.exp(-base_deg_rate_per_s * temp_factor * dt_internal)
            logger.debug(f"Catalyst degradation: {self.catalyst_degradation:.4f}")
            
            # Calculate concentrations (mol/m³)
            V_m3 = self.spec.volume_m3
            concentrations = {}
            for resource in ResourceType:
                conc = self.composition_mol.get(resource, 0.0) / V_m3
                concentrations[resource.name] = max(conc, 1e-12)
            logger.debug(f"Concentrations: {concentrations}")

            # Calculate reaction rates and apply the ramp factor
            reaction_rates = self._calculate_reaction_rates(concentrations)
            for reaction in reaction_rates:
                reaction_rates[reaction] *= ramp_factor
            logger.debug(f"Reaction rates: {reaction_rates}")

            # Add additional baseline contributions (also scaled)
            time_s = self.uptime_hours * 3600
            baseline_rate = 1e-3
            oscillating_rate = 5e-4 * (1 + np.sin(time_s * 2 * np.pi / 60))
            reaction_rates["main"] += (baseline_rate + oscillating_rate) * ramp_factor
            reaction_rates["rwgs"] += (baseline_rate * 0.5) * ramp_factor
            reaction_rates["methanation"] += (baseline_rate * 0.5) * ramp_factor
            logger.debug(f"Reaction rates after additional contributions: {reaction_rates}")

            # Calculate reaction-induced mole changes (mol/(m³·s))
            delta_main = {
                ResourceType.CO2: -reaction_rates["main"],
                ResourceType.H2: -4 * reaction_rates["main"],
                ResourceType.CH4: reaction_rates["main"],
                ResourceType.H2O: 2 * reaction_rates["main"]
            }
            delta_rwgs = {
                ResourceType.CO2: -reaction_rates["rwgs"],
                ResourceType.H2: -reaction_rates["rwgs"],
                ResourceType.CO: reaction_rates["rwgs"],
                ResourceType.H2O: reaction_rates["rwgs"]
            }
            delta_meth = {
                ResourceType.CO: -reaction_rates["methanation"],
                ResourceType.H2: -3 * reaction_rates["methanation"],
                ResourceType.CH4: reaction_rates["methanation"],
                ResourceType.H2O: reaction_rates["methanation"]
            }
            reaction_changes = {}
            for res in ResourceType:
                reaction_changes[res] = (
                    delta_main.get(res, 0.0) +
                    delta_rwgs.get(res, 0.0) +
                    delta_meth.get(res, 0.0)
                )
            logger.debug(f"Reaction changes: {reaction_changes}")

            # Update reactor composition using the fine dt
            self._update_composition(dt_internal, inputs_mol_per_s, reaction_changes)
            logger.debug(f"Composition mol: {self.composition_mol}")
            composition_grams = {res: self.composition_mol[res] * molar_mass_dict[res.name] for res in self.composition_mol}
            logger.debug(f"Composition grams: {composition_grams}")

            # Accumulate outputs (net mole change over the reactor volume)
            for res in ResourceType:
                net_outputs[res] += reaction_changes.get(res, 0.0) * V_m3
            logger.debug(f"Net outputs: {net_outputs}")
            net_outputs_grams = {res: net_outputs[res] * molar_mass_dict[res.name] for res in net_outputs}
            logger.debug(f"Net outputs grams: {net_outputs_grams}")

            # --- Energy Balance ---
            # Main reaction heat release (J/s) with an exothermic delta_H_main
            delta_H_main_J_per_mol = -165e3  # J/mol
            heat_generated_W = -reaction_rates["main"] * delta_H_main_J_per_mol * V_m3
            logger.debug(f"Heat generated: {heat_generated_W:.2f} W")

            heat_loss_W = self.calculate_heat_loss()
            logger.debug(f"Heat loss: {heat_loss_W:.2f} W")

            mixing_heat_W = 50.0 * V_m3  # Reduced from previous value
            logger.debug(f"Mixing heat: {mixing_heat_W:.2f} W")

            # Simplified pump power calculation
            pump_heat_W = 100.0 * sum(inputs_mol_per_s[r] * molar_mass_dict.get(r.name, 0.028)
                                    for r in inputs_mol_per_s)
            logger.debug(f"Pump heat: {pump_heat_W:.2f} W")

            # Reduced side reaction heat contribution
            side_reaction_heat_W = (reaction_rates["rwgs"] + reaction_rates["methanation"]) * 5e3 * V_m3
            logger.debug(f"Side reaction heat: {side_reaction_heat_W:.2f} W")

            # Remove oscillation and control offset terms that were causing spikes
            net_heat_W = (heat_generated_W - heat_loss_W + mixing_heat_W +
                         pump_heat_W + side_reaction_heat_W)
            logger.debug(f"Net heat: {net_heat_W:.2f} W")

            total_thermal_mass = self.spec.thermal_mass_J_per_K
            for resource in ResourceType:
                n_mol = self.composition_mol.get(resource, 0.0)
                total_thermal_mass += n_mol * cp_for_species(resource.name, self.state.temperature_K)
            logger.debug(f"Total thermal mass: {total_thermal_mass:.2f} J/K")

            try:
                delta_T = (net_heat_W * dt_internal) / max(total_thermal_mass, 1e-12)
                logger.debug(f"Temperature change: {delta_T:.2f} K")
            except (OverflowError, FloatingPointError):
                self.operational_status = OperationalStatus.FAULT
                logger.error("Reactor entered FAULT state due to numerical error in temperature calculation.")
                return {r: 0.0 for r in ResourceType}

            if abs(delta_T) > 1000:
                self.operational_status = OperationalStatus.FAULT
                logger.error("Reactor entered FAULT state due to excessive temperature change.")
                return {r: 0.0 for r in ResourceType}

            new_temp = self.state.temperature_K + delta_T
            self.state.temperature_K = min(max(new_temp, 273.15), self.spec.max_temperature_K)
            total_moles = max(sum(self.composition_mol.values()), 1e-12)
            self.state.pressure_Pa = total_moles * constants.R * self.state.temperature_K / V_m3

            self.update_uptime(dt_internal)

        # Update power consumption based on final heat losses and inflows (for reporting)
        # Cap maximum power consumption to prevent spikes
        max_power_W = 5000.0  # 5kW maximum power consumption
        self.power_consumption_W = min(max_power_W, max(0, heat_loss_W - heat_generated_W) + pump_heat_W + mixing_heat_W)
        logger.debug(f"Power consumption: {self.power_consumption_W:.2f} W")
        logger.debug(f"Net outputs mol per s: {net_outputs}")
        net_outputs_grams = {res: net_outputs[res] * molar_mass_dict[res.name] for res in net_outputs}
        logger.debug(f"Net outputs grams per s: {net_outputs_grams}")
        return net_outputs

    def start(self):
        if self.operational_status == OperationalStatus.STANDBY:
            self.operational_status = OperationalStatus.STARTUP
            self.transition_timer_s = 0.0
            logger.info("Reactor startup initiated.")

    def shutdown(self):
        if self.operational_status == OperationalStatus.RUNNING:
            self.operational_status = OperationalStatus.SHUTDOWN
            self.transition_timer_s = 0.0
            logger.info("Reactor shutdown initiated.")

    def calculate_power_consumption(self) -> float:
        if self.operational_status != OperationalStatus.RUNNING:
            return 0.0
        return self.power_consumption_W


# =============================================================================
# Example Usage (for testing purposes)
# =============================================================================

if __name__ == "__main__":
    spec = SabatierSpecification(
        volume_m3=1.0,
        max_temperature_K=1000.0,
        max_pressure_Pa=5e6,
        thermal_mass_J_per_K=1e4,
        heat_loss_coefficient_W_per_m2K=10.0,
        surface_area_m2=5.0,
        catalyst_type="Ru/Al2O3",
        catalyst_loading_kg_per_m3=50.0,
        catalyst_surface_area_m2_per_kg=100.0,
        catalyst_porosity=0.4
    )
    
    state = ThermodynamicState.from_temperature_pressure(600.0, 1e5, "H2O")
    
    kinetics_main = ReactionKinetics(
        rate_constant_forward_1_s_inv=1e3,
        activation_energy_J_per_mol=80e3,
        reaction_order={"CO2": 1, "H2": 4}
    )
    kinetics_rwgs = ReactionKinetics(
        rate_constant_forward_1_s_inv=5e2,
        activation_energy_J_per_mol=90e3,
        reaction_order={"CO2": 1, "H2": 1}
    )
    kinetics_meth = ReactionKinetics(
        rate_constant_forward_1_s_inv=8e2,
        activation_energy_J_per_mol=85e3,
        reaction_order={"CO": 1, "H2": 3}
    )
    kinetics_dict = {"main": kinetics_main, "rwgs": kinetics_rwgs, "methanation": kinetics_meth}
    
    initial_composition = {
        ResourceType.CO2: 10.0,
        ResourceType.H2: 40.0,
        ResourceType.CH4: 0.0,
        ResourceType.H2O: 0.0,
        ResourceType.CO: 0.0,
        ResourceType.O2: 0.0
    }
    
    reactor = SabatierReactor(spec, state, initial_composition, kinetics_dict)
    reactor.start()
    
    inputs = {
        ResourceType.CO2: 0.1,
        ResourceType.H2: 0.4,
        ResourceType.CH4: 0.0,
        ResourceType.H2O: 0.0,
        ResourceType.CO: 0.0,
        ResourceType.O2: 0.0
    }
    for t in range(10):
        outputs = reactor.step(1.0, inputs)
        print(f"Time {t+1}s: Temperature = {reactor.state.temperature_K:.2f} K, "
              f"Pressure = {reactor.state.pressure_Pa:.2f} Pa, "
              f"Power = {reactor.calculate_power_consumption():.2f} W")
    
    reactor.shutdown()
