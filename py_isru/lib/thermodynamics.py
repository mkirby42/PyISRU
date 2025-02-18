"""
Core thermodynamic models and calculations for the ISRU system.
"""
from dataclasses import dataclass
from typing import Dict, Optional
from enum import Enum, auto
import numpy as np
from scipy import constants


@dataclass
class ThermodynamicState:
    """
    Represents the thermodynamic state of the reactor.
    
    Units:
      - temperature_K: temperature (K)
      - pressure_Pa: pressure (Pa)
      - enthalpy_J: enthalpy (J)
      - entropy_J_per_K: entropy (J/K)
      - gibbs_energy_J: Gibbs free energy (J)
    """
    temperature_K: float
    pressure_Pa: float
    enthalpy_J: float
    entropy_J_per_K: float
    gibbs_energy_J: float

    @classmethod
    def from_temperature_pressure(cls, temperature_K: float, pressure_Pa: float, substance: str = "H2O") -> 'ThermodynamicState':
        """
        Create a ThermodynamicState from temperature and pressure.
        Uses generic Cp, S0, and H0 values for the specified substance.
        """
        # Standard properties at 298.15 K, 101325 Pa (example values)
        properties = {
            "H2O": {"Cp_J_per_molK": 33.6, "S0_J_per_molK": 188.8, "H0_J_per_mol": -241.8e3},
            "H2": {"Cp_J_per_molK": 28.8, "S0_J_per_molK": 130.7, "H0_J_per_mol": 0.0},
            "O2": {"Cp_J_per_molK": 29.4, "S0_J_per_molK": 205.2, "H0_J_per_mol": 0.0},
            "CO2": {"Cp_J_per_molK": 37.1, "S0_J_per_molK": 213.8, "H0_J_per_mol": -393.5e3},
            "CH4": {"Cp_J_per_molK": 35.7, "S0_J_per_molK": 186.3, "H0_J_per_mol": -74.9e3},
            "CO": {"Cp_J_per_molK": 29.1, "S0_J_per_molK": 197.7, "H0_J_per_mol": -110.5e3}
        }
        props = properties.get(substance, properties["H2O"])
        T_ref = 298.15  # reference temperature (K)
        P_ref = 101325  # reference pressure (Pa)

        # For a generic integration, assume constant Cp (could be replaced by numerical integration)
        enthalpy_J = props["H0_J_per_mol"] + props["Cp_J_per_molK"] * (temperature_K - T_ref)
        # More precise entropy calculation (integrating Cp/T)
        entropy_J_per_K = props["S0_J_per_molK"] + props["Cp_J_per_molK"] * np.log(temperature_K / T_ref) - constants.R * np.log(pressure_Pa / P_ref)
        gibbs_energy_J = enthalpy_J - temperature_K * entropy_J_per_K
        return cls(temperature_K, pressure_Pa, enthalpy_J, entropy_J_per_K, gibbs_energy_J)
    
    def calculate_equilibrium_constant(self, delta_g_standard_J_per_mol: float) -> float:
        """
        Calculate equilibrium constant K from the standard Gibbs free energy change.
        
        Returns:
            Equilibrium constant (dimensionless)
        """
        return np.exp(-delta_g_standard_J_per_mol / (constants.R * self.temperature_K))

@dataclass
class ReactionKinetics:
    """
    Models reaction kinetics including rate constants and activation energies.
    
    The kinetics model uses the Arrhenius equation combined with the mass action law.
    
    Attributes:
      - rate_constant_forward_1_s_inv: Pre-exponential factor (s⁻¹ or appropriate units)
      - activation_energy_J_per_mol: Activation energy (J/mol)
      - reaction_order: Dict mapping species (by name) to their reaction order
    """
    rate_constant_forward_1_s_inv: float
    activation_energy_J_per_mol: float
    reaction_order: Dict[str, int]

    def calculate_rate(self,
                       concentrations_mol_per_m3: Dict[str, float],
                       temperature_K: float,
                       catalyst_factor: float = 1.0) -> float:
        """
        Calculate the forward reaction rate using the Arrhenius equation and mass action law.
        
        Args:
            concentrations_mol_per_m3: Species concentrations (mol/m³) with keys as strings.
            temperature_K: Reactor temperature in Kelvin.
            catalyst_factor: Effective catalyst factor (loading × degradation), dimensionless.
            
        Returns:
            Reaction rate (mol/(m³·s))
        """
        # Compute the temperature-dependent rate constant (Arrhenius)
        k_forward = self.rate_constant_forward_1_s_inv * np.exp(-self.activation_energy_J_per_mol / (constants.R * temperature_K))
        
        # Mass action law (product over species raised to their reaction order)
        rate = k_forward
        for species, order in self.reaction_order.items():
            conc = concentrations_mol_per_m3.get(species, 1e-12)  # avoid zero division
            rate *= conc ** order
        
        # Multiply by catalyst factor
        return rate * catalyst_factor

class GasProperties:
    """
    Utility class for gas property calculations using a simplified Peng–Robinson EOS.
    """

    # Dummy Peng-Robinson parameters for common species (SI units)
    PR_PARAMETERS = {
        "CO2": {"a": 0.45724 * (constants.R ** 2) * (304.2 ** 2) / 7374000, "b": 0.07780 * constants.R * 304.2 / 7374000},
        "H2":  {"a": 0.45724 * (constants.R ** 2) * (33.2 ** 2) / 1200000, "b": 0.07780 * constants.R * 33.2 / 1200000},
        "CH4": {"a": 0.45724 * (constants.R ** 2) * (190.6 ** 2) / 4599000, "b": 0.07780 * constants.R * 190.6 / 4599000},
        "H2O": {"a": 0.45724 * (constants.R ** 2) * (647.1 ** 2) / 22064000, "b": 0.07780 * constants.R * 647.1 / 22064000},
        "CO":  {"a": 0.45724 * (constants.R ** 2) * (132.9 ** 2) / 3400000, "b": 0.07780 * constants.R * 132.9 / 3400000},
        "O2":  {"a": 0.45724 * (constants.R ** 2) * (154.6 ** 2) / 5040000, "b": 0.07780 * constants.R * 154.6 / 5040000},
    }

    @staticmethod
    def calculate_density_PR(temperature_K: float, pressure_Pa: float, mole_fraction: Dict[str, float], molar_mass_dict: Dict[str, float]) -> float:
        """
        Calculate mixture density using a simplified Peng–Robinson EOS.
        
        Args:
            temperature_K: Temperature in Kelvin.
            pressure_Pa: Pressure in Pascal.
            mole_fraction: Dict mapping species (str) to mole fraction.
            molar_mass_dict: Dict mapping species (str) to molar mass (kg/mol).
            
        Returns:
            Mixture density (kg/m³)
        """
        # Compute mixture parameters (using classical mixing rules)
        a_mix = 0.0
        b_mix = 0.0
        for species, x in mole_fraction.items():
            params = GasProperties.PR_PARAMETERS.get(species, None)
            if params is None:
                continue
            a_i = params["a"]
            b_i = params["b"]
            a_mix += x * a_i  # simplified; a true mixing rule would sum over pairs
            b_mix += x * b_i
        
        # Initial guess for molar volume (ideal gas law)
        n_over_V = pressure_Pa / (constants.R * temperature_K)
        V_m = 1 / n_over_V  # m³/mol
        
        # Solve the Peng-Robinson cubic equation iteratively for compressibility factor Z.
        # The Peng–Robinson cubic in Z: Z^3 - (1 - B)*Z^2 + (A - 3*B**2 - 2*B)*Z - (A*B - B**2 - B**3) = 0,
        # where A = a_mix*pressure_Pa/(constants.R**2 * temperature_K**2)
        # and B = b_mix*pressure_Pa/(constants.R * temperature_K)
        A = a_mix * pressure_Pa / (constants.R ** 2 * temperature_K ** 2)
        B = b_mix * pressure_Pa / (constants.R * temperature_K)
        # For simplicity, we choose the largest real root as Z.
        coeffs = [1, -(1 - B), A - 3 * B ** 2 - 2 * B, -(A * B - B ** 2 - B ** 3)]
        roots = np.roots(coeffs)
        Z = np.max([root.real for root in roots if np.isreal(root)])
        V_m = Z * constants.R * temperature_K / pressure_Pa  # m³/mol
        
        # Average molar mass of mixture
        M_mix = sum(mole_fraction[species] * molar_mass_dict.get(species, 0.028) for species in mole_fraction)
        density = M_mix / V_m  # kg/m³
        return density

    @staticmethod
    def calculate_viscosity_Sutherland(temperature_K: float, reference_visc_Pa_s: float, reference_temp_K: float) -> float:
        """
        Calculate gas viscosity using Sutherland's law.
        
        Args:
            temperature_K: Temperature in Kelvin.
            reference_visc_Pa_s: Reference viscosity in Pa·s.
            reference_temp_K: Reference temperature in Kelvin.
            
        Returns:
            Viscosity (Pa·s)
        """
        return reference_visc_Pa_s * (temperature_K / reference_temp_K) ** 1.5 * ((reference_temp_K + 110) / (temperature_K + 110))

def cp_for_species(species: str, temperature_K: float) -> float:
    """
    Return the heat capacity at constant pressure (Cp) for a given species.
    (Units: J/(mol·K)). For demonstration, we use approximate constant values.
    """
    cp_values = {
        "CO2": 37.1,
        "H2": 28.8,
        "CH4": 35.7,
        "H2O": 33.6,
        "CO": 29.1,
        "O2": 29.4
    }
    return cp_values.get(species, 30.0)