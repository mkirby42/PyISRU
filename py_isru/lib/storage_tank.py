"""
Storage tank implementation with gas/liquid phase modeling.
"""
from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, Optional
import numpy as np
from scipy import constants

from .reactor import ResourceType
from .thermodynamics import ThermodynamicState, GasProperties

class PhaseType(Enum):
    """Physical phase of the stored material"""
    GAS = auto()
    LIQUID = auto()
    SUPERCRITICAL = auto()

@dataclass
class TankSpecification:
    """Physical specifications for a storage tank"""
    volume: float  # m³
    max_pressure: float  # Pa
    max_temperature: float  # K
    material: str  # e.g., "Stainless Steel 316"
    wall_thickness: float  # m
    thermal_conductivity: float  # W/(m⋅K)
    safety_factor: float  # dimensionless

class StorageTank:
    """
    Models a storage tank for gases or liquids with proper phase behavior
    and thermal management
    """
    
    # Critical points for common resources (K, Pa)
    CRITICAL_POINTS = {
        ResourceType.CO2: (304.13, 7.37e6),
        ResourceType.H2: (33.145, 1.297e6),
        ResourceType.O2: (154.58, 5.043e6),
        ResourceType.CH4: (190.56, 4.599e6),
        ResourceType.H2O: (647.10, 22.064e6)
    }
    
    # Molar masses (kg/mol)
    MOLAR_MASSES = {
        ResourceType.CO2: 0.04401,
        ResourceType.H2: 0.00201588,
        ResourceType.O2: 0.031998,
        ResourceType.CH4: 0.01604,
        ResourceType.H2O: 0.01801528
    }
    
    def __init__(self,
                 spec: TankSpecification,
                 resource_type: ResourceType,
                 initial_state: ThermodynamicState):
        self.spec = spec
        self.resource_type = resource_type
        self.state = initial_state
        self.moles = 0.0  # Current number of moles stored
        self.leak_rate = 0.0  # mol/s
        self.phase = self._determine_phase()
        
    def _determine_phase(self) -> PhaseType:
        """Determine the phase of the stored material"""
        T_crit, P_crit = self.CRITICAL_POINTS[self.resource_type]
        
        if self.state.temperature > T_crit and self.state.pressure > P_crit:
            return PhaseType.SUPERCRITICAL
        elif self.resource_type in [ResourceType.H2O] and self.state.temperature < 373.15:
            return PhaseType.LIQUID
        else:
            return PhaseType.GAS
            
    def _calculate_compressibility(self) -> float:
        """Calculate gas compressibility factor using van der Waals equation"""
        # Van der Waals constants (approximate)
        a = {
            ResourceType.CO2: 0.364,
            ResourceType.H2: 0.0245,
            ResourceType.O2: 0.138,
            ResourceType.CH4: 0.228,
            ResourceType.H2O: 0.553
        }
        b = {
            ResourceType.CO2: 4.267e-5,
            ResourceType.H2: 2.661e-5,
            ResourceType.O2: 3.183e-5,
            ResourceType.CH4: 4.278e-5,
            ResourceType.H2O: 3.049e-5
        }
        
        # Solve cubic equation for compressibility factor Z
        R = constants.R
        T = self.state.temperature
        P = self.state.pressure
        V = self.spec.volume / self.moles if self.moles > 0 else float('inf')
        
        a_val = a[self.resource_type]
        b_val = b[self.resource_type]
        
        # Cubic equation coefficients
        A = a_val * P / (R * T)**2
        B = b_val * P / (R * T)
        
        # Solve Z³ - (1 + B)Z² + AZ - AB = 0
        coeffs = [1, -(1 + B), A, -A*B]
        roots = np.roots(coeffs)
        
        # Select the real root closest to 1
        real_roots = roots[np.abs(roots.imag) < 1e-10].real
        return float(real_roots[np.argmin(np.abs(real_roots - 1))])
        
    def calculate_density(self) -> float:
        """Calculate current density of stored material"""
        if self.phase == PhaseType.GAS:
            Z = self._calculate_compressibility()
            return self.state.pressure * self.MOLAR_MASSES[self.resource_type] / \
                   (Z * constants.R * self.state.temperature)
        else:
            # Approximate liquid density (kg/m³)
            liquid_density = {
                ResourceType.H2O: 1000.0,
                ResourceType.CO2: 1101.0,  # At critical point
                ResourceType.O2: 1141.0,   # At normal boiling point
                ResourceType.CH4: 422.62,  # At normal boiling point
                ResourceType.H2: 70.85     # At normal boiling point
            }
            return liquid_density[self.resource_type]
            
    def calculate_available_volume(self) -> float:
        """Calculate available volume for additional storage"""
        current_volume = self.moles * constants.R * self.state.temperature / self.state.pressure
        return max(0.0, self.spec.volume - current_volume)
        
    def add_resource(self, moles: float, temperature: float) -> float:
        """
        Add resource to tank, returns amount actually added
        
        Args:
            moles: Amount to add (mol)
            temperature: Temperature of incoming material (K)
            
        Returns:
            Amount actually added (mol)
        """
        if moles <= 0:
            return 0.0
            
        if temperature <= 0:
            raise ValueError("Temperature must be positive")
            
        # Check pressure limit
        new_pressure = self.state.pressure * (1 + moles / self.moles) if self.moles > 0 else \
                      moles * constants.R * temperature / self.spec.volume
                      
        if new_pressure > self.spec.max_pressure:
            return 0.0
            
        # Update state
        if self.moles > 0:
            # Mix temperatures based on heat capacity
            Cp = 29.1  # J/(mol⋅K) - approximate average
            self.state.temperature = (self.moles * Cp * self.state.temperature + 
                                    moles * Cp * temperature) / ((self.moles + moles) * Cp)
        else:
            self.state.temperature = temperature
            
        self.moles += moles
        self.state.pressure = new_pressure
        self.phase = self._determine_phase()
        
        return moles
        
    def remove_resource(self, moles: float) -> float:
        """
        Remove resource from tank, returns amount actually removed
        
        Args:
            moles: Amount to remove (mol)
            
        Returns:
            Amount actually removed (mol)
        """
        if moles <= 0:
            return 0.0
            
        amount_removed = min(moles, self.moles)
        self.moles -= amount_removed
        
        if self.moles > 0:
            self.state.pressure *= (self.moles / (self.moles + amount_removed))
        else:
            self.state.pressure = 0.0
            
        self.phase = self._determine_phase()
        return amount_removed
        
    def step(self, dt: float) -> None:
        """
        Advance tank state by one time step
        
        Args:
            dt: Time step in seconds
        """
        # Handle leaks
        if self.leak_rate > 0:
            leaked = self.remove_resource(self.leak_rate * dt)
            
        # Update thermal state (simplified)
        ambient_temp = 210.0  # K (Mars average)
        heat_transfer_coeff = 5.0  # W/(m²⋅K)
        surface_area = 2 * np.pi * np.sqrt(self.spec.volume / np.pi) * \
                      (np.sqrt(self.spec.volume / np.pi) + self.spec.volume / \
                       (np.pi * np.sqrt(self.spec.volume / np.pi)))
                       
        heat_transfer = heat_transfer_coeff * surface_area * \
                       (ambient_temp - self.state.temperature) * dt
                       
        if self.moles > 0:
            # Approximate heat capacity
            Cp = 29.1  # J/(mol⋅K)
            self.state.temperature += heat_transfer / (self.moles * Cp)
            
            # Update pressure based on new temperature
            self.state.pressure = self.moles * constants.R * self.state.temperature / self.spec.volume