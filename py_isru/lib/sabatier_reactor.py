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
from .thermodynamics import ThermodynamicState, cp_for_species, GasProperties, ReactionKinetics, sabatier_reactor_kinetics_dict

logger = logging.getLogger(__name__)

@dataclass
class SabatierSpecification(ReactorSpecification):
    catalyst_type: str
    catalyst_loading_kg_per_m3: float
    catalyst_surface_area_m2_per_kg: float
    catalyst_porosity: float
    startup_time_s: float = 300.0  # default 5 minutes
    shutdown_time_s: float = 300.0  # default 5 minutes
    
    
class SabatierReactor(Reactor):
    """
    Implements the Sabatier reaction and side reactions in a CSTR.
    
    Reactions:
      Main:        CO2 + 4 H2 ⇌ CH4 + 2 H2O
      RWGS:        CO2 + H2 ⇌ CO + H2O
      Methanation: CO + 3 H2 ⇌ CH4 + H2O
      
    Models the Sabatier reaction and side reactions in a Continuously Stirred Tank Reactor (CSTR).
    """
    def __init__(self,
                 reactor_specification: SabatierSpecification,
                 thermodynamic_state: ThermodynamicState,
                 initial_composition_mol: Dict[ResourceType, float],
                 reaction_kinetics: Dict[str, ReactionKinetics] = sabatier_reactor_kinetics_dict):
        super().__init__(reactor_specification, thermodynamic_state)
        self.reactor_specification: SabatierSpecification = reactor_specification
        self.reaction_kinetics = reaction_kinetics
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
        return (f"SabatierReactor(reactor_specification={self.reactor_specification}, "
                f"thermodynamic_state={self.thermodynamic_state}, "
                f"composition_mol={self.composition_mol}, "
                f"catalyst_degradation={self.catalyst_degradation:.4f}, "
                f"power_consumption_W={self.power_consumption_W:.2f}, "
                f"operational_status={self.operational_status})")

    def _update_composition(self, dt_s: float, inputs_mol_per_s: Dict[ResourceType, float],
                            reaction_changes_mol_per_m3: Dict[ResourceType, float]):
        total_inflow = sum(inputs_mol_per_s.values())
        total_moles = max(sum(self.composition_mol.values()), 1e-12)
        V_m3 = self.reactor_specification.volume_m3
        for resource in ResourceType:
            n_old = self.composition_mol.get(resource, 0.0)
            F_in = inputs_mol_per_s.get(resource, 0.0)
            dilution = (n_old / total_moles) * total_inflow
            reaction_prod = reaction_changes_mol_per_m3.get(resource, 0.0) * V_m3
            n_new = n_old + dt_s * (F_in - dilution + reaction_prod)
            self.composition_mol[resource] = max(n_new, 0.0)

    def _calculate_reaction_rates(self, concentrations: Dict[str, float]) -> Dict[str, float]:
        catalyst_factor = (self.reactor_specification.catalyst_loading_kg_per_m3 *
                           self.catalyst_degradation *
                           self.reactor_specification.catalyst_surface_area_m2_per_kg)
        rates = {}
        # Calculate unconstrained rates first
        for reaction in ["main", "rwgs", "methanation"]:
            kinetics = self.reaction_kinetics[reaction]
            forward_rate = kinetics.calculate_rate(concentrations, self.thermodynamic_state.temperature_K, catalyst_factor)
            if reaction == "main":
                K_eq = self.thermodynamic_state.calculate_equilibrium_constant(self.delta_g_standard_J["main"])
                Q = (max(concentrations.get("CH4", 1e-12), 1e-12) *
                     max(concentrations.get("H2O", 1e-12), 1e-12) ** 2 /
                     (max(concentrations.get("CO2", 1e-12), 1e-12) *
                      max(concentrations.get("H2", 1e-12), 1e-12) ** 4))
                net_rate = forward_rate * (1 - Q / K_eq)
            elif reaction == "rwgs":
                K_eq = self.thermodynamic_state.calculate_equilibrium_constant(self.delta_g_standard_J["rwgs"])
                Q = (max(concentrations.get("CO", 1e-12), 1e-12) *
                     max(concentrations.get("H2O", 1e-12), 1e-12) /
                     (max(concentrations.get("CO2", 1e-12), 1e-12) *
                      max(concentrations.get("H2", 1e-12), 1e-12)))
                net_rate = forward_rate * (1 - Q / K_eq)
            elif reaction == "methanation":
                K_eq = self.thermodynamic_state.calculate_equilibrium_constant(self.delta_g_standard_J["methanation"])
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
        V_m3 = self.reactor_specification.volume_m3
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

        if self.operational_status != OperationalStatus.RUNNING:
            return {r: 0.0 for r in ResourceType}

        # Molar mass dictionary for energy balance
        molar_mass_dict = {"CO2": 0.044, "H2": 0.002, "CH4": 0.016,
                          "H2O": 0.018, "CO": 0.028, "O2": 0.032}

        # Calculate concentrations (mol/m³)
        V_m3 = self.reactor_specification.volume_m3
        concentrations = {}
        for resource in ResourceType:
            conc = self.composition_mol.get(resource, 0.0) / V_m3
            concentrations[resource.name] = max(conc, 1e-12)

        # Calculate reaction rates
        reaction_rates = self._calculate_reaction_rates(concentrations)

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

        # Update reactor composition
        self._update_composition(dt_s, inputs_mol_per_s, reaction_changes)

        # Energy Balance
        delta_H_main_J_per_mol = -165e3  # J/mol
        heat_generated_W = -reaction_rates["main"] * delta_H_main_J_per_mol * V_m3
        heat_loss_W = self.calculate_heat_loss()
        mixing_heat_W = 50.0 * V_m3
        pump_heat_W = 100.0 * sum(inputs_mol_per_s[r] * molar_mass_dict.get(r.name, 0.028)
                                for r in inputs_mol_per_s)
        side_reaction_heat_W = (reaction_rates["rwgs"] + reaction_rates["methanation"]) * 5e3 * V_m3
        net_heat_W = heat_generated_W - heat_loss_W + mixing_heat_W + pump_heat_W + side_reaction_heat_W

        # Update temperature and pressure
        total_thermal_mass = self.reactor_specification.thermal_mass_J_per_K
        for resource in ResourceType:
            n_mol = self.composition_mol.get(resource, 0.0)
            total_thermal_mass += n_mol * cp_for_species(resource.name, self.thermodynamic_state.temperature_K)

        try:
            delta_T = (net_heat_W * dt_s) / max(total_thermal_mass, 1e-12)
        except (OverflowError, FloatingPointError):
            self.operational_status = OperationalStatus.FAULT
            logger.error("Reactor entered FAULT state due to numerical error in temperature calculation.")
            return {r: 0.0 for r in ResourceType}

        if abs(delta_T) > 1000:
            self.operational_status = OperationalStatus.FAULT
            logger.error("Reactor entered FAULT state due to excessive temperature change.")
            return {r: 0.0 for r in ResourceType}

        new_temp = self.thermodynamic_state.temperature_K + delta_T
        self.thermodynamic_state.temperature_K = min(max(new_temp, 273.15), self.reactor_specification.max_temperature_K)
        total_moles = max(sum(self.composition_mol.values()), 1e-12)
        self.thermodynamic_state.pressure_Pa = total_moles * constants.R * self.thermodynamic_state.temperature_K / V_m3

        self.update_uptime(dt_s)
        
        # Update power consumption
        max_power_W = 5000.0  # 5kW maximum power consumption
        self.power_consumption_W = min(max_power_W, max(0, heat_loss_W - heat_generated_W) + pump_heat_W + mixing_heat_W)

        # Calculate net outputs (mol/s)
        net_outputs = {res: reaction_changes.get(res, 0.0) * V_m3 for res in ResourceType}
        return net_outputs

    def start(self):
        if self.operational_status == OperationalStatus.STANDBY:
            self.operational_status = OperationalStatus.RUNNING
            self.thermodynamic_state.temperature_K = 600.0  # Set to operating temperature immediately
            logger.info("Reactor started.")

    def shutdown(self):
        if self.operational_status == OperationalStatus.RUNNING:
            self.operational_status = OperationalStatus.STANDBY
            logger.info("Reactor shut down.")

    def calculate_power_consumption(self) -> float:
        if self.operational_status != OperationalStatus.RUNNING:
            return 0.0
        return self.power_consumption_W


# =============================================================================
# Example Usage (for testing purposes)
# =============================================================================

if __name__ == "__main__":
    reactor_specification = SabatierSpecification(
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
    
    thermodynamic_state = ThermodynamicState.from_temperature_pressure(600.0, 1e5, "H2O")
    
    initial_composition = {
        ResourceType.CO2: 10.0,
        ResourceType.H2: 40.0,
        ResourceType.CH4: 0.0,
        ResourceType.H2O: 0.0,
        ResourceType.CO: 0.0,
        ResourceType.O2: 0.0
    }
    
    reactor = SabatierReactor(reactor_specification, thermodynamic_state, initial_composition, sabatier_reactor_kinetics_dict)
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
        print(f"Time {t+1}s: Temperature = {reactor.thermodynamic_state.temperature_K:.2f} K, "
              f"Pressure = {reactor.thermodynamic_state.pressure_Pa:.2f} Pa, "
              f"Power = {reactor.calculate_power_consumption():.2f} W")
    
    reactor.shutdown()
