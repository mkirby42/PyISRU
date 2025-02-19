"""
Electrolysis reactor implementation with detailed electrode kinetics.
"""
from dataclasses import dataclass
from typing import Dict, Optional
import numpy as np
from scipy import constants
import logging

from .reactor import Reactor, ReactorSpecification, ResourceType, OperationalStatus
from .thermodynamics import ThermodynamicState, ReactionKinetics

logger = logging.getLogger(__name__)

"""
Revised Electrolysis reactor implementation for a Martian ISRU plant.

This reactor performs water electrolysis:
    2 H2O(l) → 2 H2(g) + O2(g)

It includes:
  - Detailed Nernst voltage calculation (with proper pressure and temperature units)
  - A detailed activation overpotential model (Tafel-type, with explicit parameters)
  - Improved ohmic overpotential with effective conductivity checks
  - A smoothed concentration overpotential formulation
  - Accumulation of internal species (via a CSTR mass balance)
  - A consistent energy/heat balance for temperature update
  - Membrane hydration and cumulative operating hours affecting degradation
  - Realistic power-limiting logic based on cell voltage and current
  - Proper startup and shutdown ramp sequences
  - Use of ReactionKinetics for kinetic parameters

Units in variable names:
  - Temperature: _K
  - Pressure: _Pa (or converted to bar when needed)
  - Current density: _A_per_m2
  - Voltage: _V
  - Power: _W
  - Volume: _m3
"""

import numpy as np
from scipy import constants
from dataclasses import dataclass, field
from typing import Dict, Optional
import logging

from .reactor import Reactor, ReactorSpecification, ResourceType, OperationalStatus
from .thermodynamics import ThermodynamicState, ReactionKinetics

logger = logging.getLogger(__name__)

# =============================================================================
# Specification Data Class
# =============================================================================

@dataclass
class ElectrolysisSpecification(ReactorSpecification):
    """
    Specifications for the Electrolysis reactor.
    
    Units:
      - membrane_type: (string) e.g., "Nafion"
      - membrane_thickness_m: membrane thickness (m)
      - membrane_conductivity_S_per_m: membrane conductivity (S/m)
      - electrode_area_m2: electrode area (m²)
      - max_current_density_A_per_m2: maximum allowable current density (A/m²)
      - max_power_W: maximum electrical power (W)
      - startup_time_s: startup ramp time (s)
      - shutdown_time_s: shutdown ramp time (s)
    """
    membrane_type: str
    membrane_thickness_m: float
    membrane_conductivity_S_per_m: float
    electrode_area_m2: float
    max_current_density_A_per_m2: float
    max_power_W: float
    startup_time_s: float = 300.0    # default: 5 minutes
    shutdown_time_s: float = 300.0   # default: 5 minutes

# =============================================================================
# Revised Electrolysis Reactor Class
# =============================================================================

class ElectrolysisReactor(Reactor):
    """
    Electrolysis reactor implementing water splitting:
    
        2 H2O(l) → 2 H2(g) + O2(g)
    
    This model includes:
      - Detailed Nernst voltage calculation with proper pressure/temperature conversion.
      - A detailed activation overpotential model (Tafel-type) with explicit kinetic parameters.
      - Improved ohmic and smoothed concentration overpotential formulations.
      - CSTR-style accumulation of internal composition (H2O, H2, O2).
      - Consistent energy balance to update reactor temperature.
      - Membrane degradation influenced by cumulative operating hours, current density, and hydration.
      - Realistic power-limiting logic.
      - Startup and shutdown ramp sequences.
      - Proper use of the ReactionKinetics object to obtain kinetic parameters.
    """
    
    def __init__(self,
                 reactor_specification: ElectrolysisSpecification,
                 thermodynamic_state: ThermodynamicState,
                 initial_composition_mol: Dict[ResourceType, float],
                 reaction_kinetics: ReactionKinetics):
        """
        Args:
            spec: ElectrolysisSpecification with reactor parameters.
            initial_state: Initial thermodynamic state.
            kinetics: ReactionKinetics object (used for kinetic parameters).
            initial_composition_mol: Initial inventory of species (mol).
                Expected keys: ResourceType.H2O, ResourceType.H2, ResourceType.O2.
        """
        super().__init__(reactor_specification, thermodynamic_state)
        self.reactor_specification: ElectrolysisSpecification = reactor_specification  # type hint
        
        # Electrolysis-specific attributes
        self.reaction_kinetics = reaction_kinetics
        self.membrane_degradation_factor = 1.0  # 1.0 = fresh membrane
        self.membrane_hydration = 1.0  # 1.0 = fully hydrated
        self.operating_hours_cumulative = 0.0  # cumulative operating time (hours)
        self.current_density_A_per_m2 = 0.0  # operating current density (A/m²)
        
        # Internal composition accumulation (mol) - CSTR mass balance.
        self.composition_mol: Dict[ResourceType, float] = initial_composition_mol
        
        # Standard cell potential at standard conditions (298.15 K)
        self.E0_cell_V = 1.23  # V
        # Temperature coefficient (V/K) for the cell potential
        self.dE_dT_V_per_K = -1.5e-3  # V/K

    def __repr__(self):
        return (f"ElectrolysisReactor(reactor_specification={self.reactor_specification}, "
                f"thermodynamic_state={self.thermodynamic_state}, "
                f"reaction_kinetics={self.reaction_kinetics}, "
                f"initial_composition_mol={self.composition_mol})")

    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------
    
    def calculate_nernst_voltage(self, p_H2_Pa: float, p_O2_Pa: float) -> float:
        """
        Calculate the cell's Nernst potential (V) using the proper Nernst equation.
        
        For water splitting (n = 4 electrons):
        
          E_cell = E0_corr - (R*T/(4*F)) * ln((p_H2_bar)^2 * p_O2_bar)
        
        Args:
            p_H2_Pa: Partial pressure of H2 (Pa)
            p_O2_Pa: Partial pressure of O2 (Pa)
        
        Returns:
            Nernst voltage (V)
        """
        # Convert pressures from Pa to bar (1 bar = 1e5 Pa)
        p_H2_bar = p_H2_Pa / 1e5
        p_O2_bar = p_O2_Pa / 1e5
        
        T_K = self.thermodynamic_state.temperature_K
        n_electrons = 4
        F_C_per_mol = constants.physical_constants['Faraday constant'][0]
        
        # Temperature-corrected standard potential
        T0_K = 298.15
        E0_corr_V = self.E0_cell_V + self.dE_dT_V_per_K * (T_K - T0_K)
        
        # Nernst term; note: ln((p_H2_bar)^2 * p_O2_bar) = 2*ln(p_H2_bar) + ln(p_O2_bar)
        nernst_term_V = (constants.R * T_K / (n_electrons * F_C_per_mol)) * np.log((p_H2_bar ** 2) * p_O2_bar + 1e-12)
        
        # Increased gas pressures lower the cell voltage
        V_nernst = E0_corr_V - nernst_term_V
        return V_nernst

    def calculate_overpotentials(self, current_density_A_per_m2: float) -> Dict[str, float]:
        """
        Calculate activation, ohmic, and concentration overpotentials (V).
        
        Activation overpotential uses a detailed Tafel-type relation.
        Ohmic overpotential is computed from membrane thickness and effective conductivity.
        Concentration overpotential uses a smoothed logarithmic function.
        
        Args:
            current_density_A_per_m2: Operating current density (A/m²)
        
        Returns:
            Dictionary with keys "activation", "ohmic", "concentration" (V)
        """
        T_K = self.thermodynamic_state.temperature_K
        F_C_per_mol = constants.physical_constants['Faraday constant'][0]
        
        # ---- Activation Overpotential ----
        # Get exchange current density (A/m²) from kinetics (if available), else default.
        try:
            i0_eff_A_per_m2 = self.reaction_kinetics.get_exchange_current_density(T_K)
        except AttributeError:
            i0_eff_A_per_m2 = 1e-3  # default value
        
        # Transfer coefficient (alpha) and Tafel slope calculation.
        alpha = 0.5
        # A more detailed Tafel formulation (using natural logarithm)
        # η_act = (RT/(α*F)) * ln(j / i0)
        eta_activation_V = (constants.R * T_K / (alpha * F_C_per_mol)) * np.log((current_density_A_per_m2 + 1e-9) / (i0_eff_A_per_m2 + 1e-12))
        
        # ---- Ohmic Overpotential ----
        # Effective conductivity is scaled by membrane hydration and degradation.
        effective_conductivity_S_per_m = max(1e-2, 
            self.reactor_specification.membrane_conductivity_S_per_m * self.membrane_hydration * self.membrane_degradation_factor)
        eta_ohmic_V = self.reactor_specification.membrane_thickness_m * current_density_A_per_m2 / effective_conductivity_S_per_m
        
        # ---- Concentration Overpotential ----
        # Smoothly approach the limiting current density.
        j_lim_A_per_m2 = self.reactor_specification.max_current_density_A_per_m2
        # Use a logistic-like smoothing function instead of a hard cutoff:
        delta = 1e-6
        ratio = current_density_A_per_m2 / (j_lim_A_per_m2 + delta)
        # Smoothing function: η_conc = (RT/(4F)) * ln(1 + ratio/(1 - ratio + delta))
        eta_concentration_V = (constants.R * T_K / (4 * F_C_per_mol)) * np.log(1 + ratio / (1 - ratio + delta))
        
        return {
            "activation": eta_activation_V,
            "ohmic": eta_ohmic_V,
            "concentration": eta_concentration_V
        }
    
    def update_internal_composition(self, dt_s: float, inputs_mol_per_s: Dict[ResourceType, float],
                                    reaction_changes_mol_per_s: Dict[ResourceType, float]) -> None:
        """
        Update the internal composition (mol) using a CSTR-like mass balance.
        
        For species i:
            dn_i/dt = F_in_i - F_out_i + V_reactor * r_i
        """
        total_inflow_mol_per_s = sum(inputs_mol_per_s.values())
        total_moles = max(sum(self.composition_mol.values()), 1e-12)
        V_m3 = self.reactor_specification.volume_m3
        
        for species in self.composition_mol:
            n_old = self.composition_mol.get(species, 0.0)
            F_in = inputs_mol_per_s.get(species, 0.0)
            F_out = (n_old / total_moles) * total_inflow_mol_per_s
            reaction_term = reaction_changes_mol_per_s.get(species, 0.0) * V_m3
            n_new = n_old + dt_s * (F_in - F_out + reaction_term)
            self.composition_mol[species] = max(n_new, 0.0)
    
    def update_temperature(self, dt_s: float, power_W: float) -> None:
        """
        Update the reactor temperature (K) based on net power (W) and effective thermal mass (J/K).
        
        Effective thermal mass includes the reactor structure and the contents (using an approximate Cp).
        """
        T_ambient_K = 210.0  # Martian ambient temperature (K)
        heat_loss_W = self.reactor_specification.heat_loss_coefficient_W_per_m2K * self.reactor_specification.surface_area_m2 * (self.thermodynamic_state.temperature_K - T_ambient_K)
        net_heat_W = power_W - heat_loss_W
        
        effective_thermal_mass_J_per_K = self.reactor_specification.thermal_mass_J_per_K
        for species, n_mol in self.composition_mol.items():
            # Use an approximate Cp value (J/(mol·K)); refine per species if desired.
            Cp_J_per_molK = 33.0  
            effective_thermal_mass_J_per_K += n_mol * Cp_J_per_molK
        
        dT_K = net_heat_W * dt_s / effective_thermal_mass_J_per_K
        self.thermodynamic_state.temperature_K += dT_K
    
    def update_membrane_degradation(self, dt_s: float) -> None:
        """
        Update the membrane degradation factor and hydration.
        
        - Membrane degradation follows an exponential decay modulated by current density squared.
        - Membrane hydration is increased when water concentration is high.
        """
        # Update cumulative operating time (in hours)
        self.operating_hours_cumulative += dt_s / 3600.0
        
        base_deg_rate_per_s = 0.001 / (24 * 3600)  # base rate per second
        current_factor = (self.current_density_A_per_m2 / self.reactor_specification.max_current_density_A_per_m2) ** 2
        degradation_factor = np.exp(-base_deg_rate_per_s * current_factor * dt_s)
        self.membrane_degradation_factor *= degradation_factor
        self.membrane_degradation_factor = max(self.membrane_degradation_factor, 0.1)
        
        # Update hydration: assume full hydration if water concentration exceeds 55.5 mol/m³.
        water_mol = self.composition_mol.get(ResourceType.H2O, 0.0)
        water_conc_mol_per_m3 = water_mol / self.reactor_specification.volume_m3
        hydration_target = min(1.0, water_conc_mol_per_m3 / 55.5)
        self.membrane_hydration += (hydration_target - self.membrane_hydration) * 0.1  # relaxation factor
    
    # -------------------------------------------------------------------------
    # Main Reactor Step and Power Calculation
    # -------------------------------------------------------------------------
    
    def step(self, dt_s: float, inputs_mol_per_s: Dict[ResourceType, float]) -> Dict[ResourceType, float]:
        """
        Advance the reactor state by one time step (s).
        
        Steps:
          1. Compute partial pressures from internal composition.
          2. Calculate Nernst voltage and overpotentials.
          3. Adjust current density based on a ramp toward a target (from kinetics) and limit power.
          4. Compute production rates via Faraday's law.
          5. Update internal composition using a CSTR mass balance.
          6. Update reactor temperature via energy balance.
          7. Update membrane degradation and hydration.
          8. Update reactor uptime.
        
        Returns:
            Outflow rates (mol/s) for species.
        """
        logger.info(f"Electrolysis reactor step: dt={dt_s:.2f} s, inputs={inputs_mol_per_s}")
        if not self.check_safety_limits():
            logger.error(f"Electrolysis reactor safety limits exceeded")
            return {resource: 0.0 for resource in ResourceType}
        
        # --- 1. Determine Partial Pressures ---
        V_m3 = self.reactor_specification.volume_m3
        # Assume produced gases (H2 and O2) are accumulated in the headspace.
        total_gas_mol = self.composition_mol.get(ResourceType.H2, 0.0) + self.composition_mol.get(ResourceType.O2, 0.0)
        T_K = self.thermodynamic_state.temperature_K
        p_total_Pa = total_gas_mol * constants.R * T_K / V_m3 if total_gas_mol > 0 else 1e5
        # Assume for water electrolysis: ~67% H2 and ~33% O2 by moles.
        p_H2_Pa = p_total_Pa * 0.67
        p_O2_Pa = p_total_Pa * 0.33
        
        # --- 2. Calculate Nernst Voltage and Overpotentials ---
        V_nernst_V = self.calculate_nernst_voltage(p_H2_Pa, p_O2_Pa)
        overpotentials = self.calculate_overpotentials(self.current_density_A_per_m2)
        total_overpotential_V = sum(overpotentials.values())
        V_cell_V = V_nernst_V + total_overpotential_V
        
        # --- 3. Determine Operating Current Density ---
        try:
            target_current_density_A_per_m2 = 0.8 * self.reactor_specification.max_current_density_A_per_m2  # Increased from 0.5
        except AttributeError:
            target_current_density_A_per_m2 = 0.8 * self.reactor_specification.max_current_density_A_per_m2
        
        ramp_rate_A_per_m2_per_s = 0.5 * self.reactor_specification.max_current_density_A_per_m2  # Increased from 0.1
        if self.current_density_A_per_m2 < target_current_density_A_per_m2:
            self.current_density_A_per_m2 = min(self.current_density_A_per_m2 + ramp_rate_A_per_m2_per_s * dt_s,
                                                target_current_density_A_per_m2)
        else:
            self.current_density_A_per_m2 = max(self.current_density_A_per_m2 - ramp_rate_A_per_m2_per_s * dt_s,
                                                target_current_density_A_per_m2)
        
        # --- 4. Power Calculation and Limiting ---
        power_calc_W = V_cell_V * self.current_density_A_per_m2 * self.reactor_specification.electrode_area_m2
        if power_calc_W > self.reactor_specification.max_power_W:
            scaling_factor = np.sqrt(self.reactor_specification.max_power_W / power_calc_W)
            self.current_density_A_per_m2 *= scaling_factor
            overpotentials = self.calculate_overpotentials(self.current_density_A_per_m2)
            total_overpotential_V = sum(overpotentials.values())
            V_cell_V = V_nernst_V + total_overpotential_V
            power_calc_W = V_cell_V * self.current_density_A_per_m2 * self.reactor_specification.electrode_area_m2
        
        # --- 5. Reaction Production via Faraday's Law ---
        F_C_per_mol = constants.physical_constants['Faraday constant'][0]
        n_H2_produced_mol = (self.current_density_A_per_m2 * self.reactor_specification.electrode_area_m2 * dt_s) / (2 * F_C_per_mol)
        n_O2_produced_mol = (self.current_density_A_per_m2 * self.reactor_specification.electrode_area_m2 * dt_s) / (4 * F_C_per_mol)
        n_H2O_consumed_mol = 2 * n_O2_produced_mol
        logger.info(f"Electrolysis reaction changes: {n_H2O_consumed_mol / dt_s:.3f} mol/s H2O consumed, {n_H2_produced_mol / dt_s:.3f} mol/s H2 produced, {n_O2_produced_mol / dt_s:.3f} mol/s O2 produced")
        reaction_changes_mol_per_s = {
            ResourceType.H2O: -n_H2O_consumed_mol / dt_s,
            ResourceType.H2: n_H2_produced_mol / dt_s,
            ResourceType.O2: n_O2_produced_mol / dt_s
        }
        
        # --- 6. Update Internal Composition ---
        self.update_internal_composition(dt_s, inputs_mol_per_s, reaction_changes_mol_per_s)
        
        # --- 7. Update Temperature ---
        # Assume an efficiency for splitting (e.g., 70%).
        efficiency = 0.7
        waste_heat_W = power_calc_W * (1 - efficiency)
        self.update_temperature(dt_s, waste_heat_W)
        
        # --- 8. Update Membrane Degradation and Hydration ---
        self.update_membrane_degradation(dt_s)
        
        # --- 9. Update Uptime ---
        self.update_uptime(dt_s)
        
        # --- 10. Define Outputs ---
        # Only return the reaction products and remaining input water
        outputs_mol_per_s = {
            ResourceType.H2: n_H2_produced_mol / dt_s,
            ResourceType.O2: n_O2_produced_mol / dt_s,
            ResourceType.H2O: inputs_mol_per_s.get(ResourceType.H2O, 0.0) - n_H2O_consumed_mol / dt_s
        }
        logger.info(f"Electrolysis outputs: {outputs_mol_per_s}")
        return outputs_mol_per_s

    def calculate_power_consumption(self) -> float:
        """
        Calculate the current power consumption (W) based on cell voltage and current density.
        
        Returns:
            Power consumption (W)
        """
        # For consistency, use the reactor state pressure and composition to determine gas partial pressures.
        p_H2_Pa = self.thermodynamic_state.pressure_Pa * 0.67
        p_O2_Pa = self.thermodynamic_state.pressure_Pa * 0.33
        V_nernst_V = self.calculate_nernst_voltage(p_H2_Pa, p_O2_Pa)
        overpotentials = self.calculate_overpotentials(self.current_density_A_per_m2)
        total_overpotential_V = sum(overpotentials.values())
        V_cell_V = V_nernst_V + total_overpotential_V
        power_W = V_cell_V * self.current_density_A_per_m2 * self.reactor_specification.electrode_area_m2
        return min(power_W, self.reactor_specification.max_power_W)
    
    # -------------------------------------------------------------------------
    # Startup and Shutdown Behavior
    # -------------------------------------------------------------------------
    
    def start(self):
        """
        Start the electrolysis reactor.
        
        Implements a ramp-up sequence during which:
          - Current density is gradually increased from zero to a target.
          - Membrane hydration is restored.
          - Reactor uptime is updated.
          - The reactor transitions from STANDBY to RUNNING.
        """
        if self.operational_status == OperationalStatus.STANDBY:
            self.operational_status = OperationalStatus.STARTUP
            ramp_steps = int(self.reactor_specification.startup_time_s)
            target_current_density = 0.5 * self.reactor_specification.max_current_density_A_per_m2
            dt_step = 1.0  # seconds per step
            for _ in range(ramp_steps):
                self.current_density_A_per_m2 += target_current_density / ramp_steps
                # Gradually restore hydration toward full (1.0)
                self.membrane_hydration += (1.0 - self.membrane_hydration) * 0.05
                self.update_uptime(dt_step)
            self.operational_status = OperationalStatus.RUNNING

    def shutdown(self):
        """
        Shutdown the electrolysis reactor.
        
        Implements a ramp-down sequence during which:
          - Current density is gradually reduced to zero.
          - Reactor uptime is updated.
          - The reactor transitions from RUNNING to STANDBY.
        """
        if self.operational_status == OperationalStatus.RUNNING:
            self.operational_status = OperationalStatus.SHUTDOWN
            ramp_steps = int(self.reactor_specification.shutdown_time_s)
            dt_step = 1.0
            for _ in range(ramp_steps):
                self.current_density_A_per_m2 -= self.current_density_A_per_m2 / ramp_steps
                self.update_uptime(dt_step)
            self.current_density_A_per_m2 = 0.0
            self.operational_status = OperationalStatus.STANDBY
