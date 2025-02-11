"""
Core thermodynamic models and calculations for the ISRU system.
"""
from dataclasses import dataclass
from typing import Dict, Optional
import numpy as np
from scipy import constants

@dataclass
class ThermodynamicState:
    """Represents the thermodynamic state of a system"""
    temperature: float  # Kelvin
    pressure: float    # Pascal
    enthalpy: float   # Joules
    entropy: float    # J/K
    gibbs_energy: float  # Joules
    
    @classmethod
    def from_temperature_pressure(cls, temperature: float, pressure: float) -> 'ThermodynamicState':
        """Create a ThermodynamicState from temperature and pressure, calculating other properties"""
        # TODO: Implement real gas calculations
        enthalpy = 0.0  # Placeholder
        entropy = 0.0   # Placeholder
        gibbs_energy = enthalpy - temperature * entropy
        return cls(temperature, pressure, enthalpy, entropy, gibbs_energy)
    
    def calculate_equilibrium_constant(self, delta_g_standard: float) -> float:
        """Calculate equilibrium constant K from standard Gibbs free energy change"""
        return np.exp(-delta_g_standard / (constants.R * self.temperature))

@dataclass
class ReactionKinetics:
    """Models reaction kinetics including rate constants and activation energies"""
    rate_constants: Dict[str, float]
    activation_energy: float  # J/mol
    catalyst_surface_area: float  # m²
    reaction_order: Dict[str, int]
    
    def calculate_rate(self, 
                      concentrations: Dict[str, float],
                      temperature: float,
                      inhibition_factor: Optional[float] = None) -> float:
        """
        Calculate reaction rate using Arrhenius equation and mass action law
        
        Args:
            concentrations: Dict of species concentrations (mol/m³)
            temperature: Temperature in Kelvin
            inhibition_factor: Optional catalyst inhibition factor (0-1)
            
        Returns:
            Reaction rate in mol/(m³⋅s)
        """
        # Arrhenius equation
        k = self.rate_constants["forward"] * np.exp(-self.activation_energy / (constants.R * temperature))
        
        # Mass action law
        rate = k
        for species, order in self.reaction_order.items():
            rate *= concentrations[species] ** order
            
        # Apply catalyst effects
        if inhibition_factor is not None:
            rate *= inhibition_factor * self.catalyst_surface_area
            
        return rate

class GasProperties:
    """Utility class for gas property calculations"""
    
    @staticmethod
    def calculate_density(pressure: float, temperature: float, molar_mass: float) -> float:
        """Calculate gas density using real gas law"""
        # TODO: Implement real gas equation (e.g., Peng-Robinson)
        return pressure * molar_mass / (constants.R * temperature)
    
    @staticmethod
    def calculate_viscosity(temperature: float, reference_visc: float, reference_temp: float) -> float:
        """Calculate gas viscosity using Sutherland's law"""
        return reference_visc * (temperature / reference_temp) ** 1.5 * \
               (reference_temp + 110) / (temperature + 110) 