"""
StorageTank implementation for the ISRU plant.

This class models a storage tank for a specific resource (gas or liquid) with:
  - Phase determination (GAS, LIQUID, or SUPERCRITICAL)
  - Gas compressibility estimation using a van der Waals–inspired approach
  - Density calculation
  - Available volume computation
  - Resource addition and removal with state (temperature, pressure) updates
  - Thermal management and leak handling via a time-step update

All units are noted in variable names and docstrings.
"""

import numpy as np
from scipy import constants
import logging
from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict

# Assuming ResourceType is imported from the reactor module.
from .reactor import ResourceType

logger = logging.getLogger(__name__)

class PhaseType(Enum):
    """Physical phase of the stored material."""
    GAS = auto()
    LIQUID = auto()
    SUPERCRITICAL = auto()

@dataclass
class TankSpecification:
    """
    Physical specifications for a storage tank.
    
    Attributes:
      - volume_m3: Tank volume (m³)
      - max_pressure_Pa: Maximum allowable pressure (Pa)
      - max_temperature_K: Maximum allowable temperature (K)
      - material: Construction material (e.g., "Stainless Steel 316")
      - wall_thickness_m: Wall thickness (m)
      - thermal_conductivity_W_per_mK: Thermal conductivity of tank wall (W/(m·K))
      - safety_factor: Dimensionless safety factor
    """
    volume_m3: float
    max_pressure_Pa: float
    max_temperature_K: float
    material: str
    wall_thickness_m: float
    thermal_conductivity_W_per_mK: float
    safety_factor: float

class StorageTank:
    """
    StorageTank models a container for storing a resource (gas or liquid)
    with proper phase behavior and basic thermal management.
    """
    
    # Critical points for common resources: (critical_temperature_K, critical_pressure_Pa)
    CRITICAL_POINTS: Dict[ResourceType, tuple] = {
        ResourceType.CO2: (304.13, 7.37e6),
        ResourceType.H2: (33.15, 1.297e6),
        ResourceType.O2: (154.58, 5.043e6),
        ResourceType.CH4: (190.56, 4.599e6),
        ResourceType.H2O: (647.10, 22.064e6)
    }
    
    # Molar masses (kg/mol) for the resources.
    MOLAR_MASSES: Dict[ResourceType, float] = {
        ResourceType.CO2: 0.04401,
        ResourceType.H2: 0.00201588,
        ResourceType.O2: 0.031998,
        ResourceType.CH4: 0.01604,
        ResourceType.H2O: 0.01801528
    }
    
    def __init__(self,
                 spec: TankSpecification,
                 resource_type: ResourceType,
                 initial_state) -> None:
        """
        Initialize the storage tank.
        
        Args:
            spec: TankSpecification object with physical parameters.
            resource_type: The resource to be stored.
            initial_state: A ThermodynamicState object representing the initial state (temperature_K, pressure_Pa, etc.)
        """
        self.spec: TankSpecification = spec
        self.resource_type: ResourceType = resource_type
        self.state = initial_state
        self.moles: float = 0.0  # Current number of moles stored.
        self.leak_rate_mol_per_s: float = 0.0  # Leak rate (mol/s).
        self.phase: PhaseType = self._determine_phase()
    
    def __repr__(self):
        return (f"StorageTank(resource_type={self.resource_type}, moles={self.moles}, "
                f"temperature_K={self.state.temperature_K}, pressure_Pa={self.state.pressure_Pa}, "
                f"phase={self.phase}, leak_rate_mol_per_s={self.leak_rate_mol_per_s})")
    
    def _determine_phase(self) -> PhaseType:
        """
        Determine the phase (GAS, LIQUID, or SUPERCRITICAL) of the resource
        based on the current state (temperature and pressure).
        """
        T_crit_K, P_crit_Pa = self.CRITICAL_POINTS[self.resource_type]
        if self.state.temperature_K > T_crit_K and self.state.pressure_Pa > P_crit_Pa:
            return PhaseType.SUPERCRITICAL
        elif self.resource_type == ResourceType.H2O and self.state.temperature_K < 373.15:
            # For water below boiling point assume liquid.
            return PhaseType.LIQUID
        else:
            return PhaseType.GAS
    
    def _calculate_compressibility(self) -> float:
        """
        Calculate an approximate gas compressibility factor Z using a van der Waals–inspired approach.
        
        Returns:
            Compressibility factor Z (dimensionless).
        """
        # Van der Waals constants (approximate) for each resource.
        a_vals = {
            ResourceType.CO2: 0.364,
            ResourceType.H2: 0.0245,
            ResourceType.O2: 0.138,
            ResourceType.CH4: 0.228,
            ResourceType.H2O: 0.553
        }
        b_vals = {
            ResourceType.CO2: 4.267e-5,
            ResourceType.H2: 2.661e-5,
            ResourceType.O2: 3.183e-5,
            ResourceType.CH4: 4.278e-5,
            ResourceType.H2O: 3.049e-5
        }
        
        R = constants.R
        T_K = self.state.temperature_K
        P_Pa = self.state.pressure_Pa
        
        # Use ideal gas volume per mole as an initial guess:
        V_m3_per_mol = R * T_K / P_Pa
        a_val = a_vals[self.resource_type]
        b_val = b_vals[self.resource_type]
        
        # Define dimensionless parameters for van der Waals equation.
        A = a_val * P_Pa / (R * T_K)**2
        B = b_val * P_Pa / (R * T_K)
        
        # The cubic equation for Z: Z^3 - (1+B) Z^2 + A Z - A B = 0
        coeffs = [1, -(1 + B), A, -A * B]
        roots = np.roots(coeffs)
        real_roots = [r.real for r in roots if abs(r.imag) < 1e-6]
        # Choose the real root closest to unity.
        Z = min(real_roots, key=lambda z: abs(z - 1))
        return Z

    def calculate_density(self) -> float:
        """
        Calculate the density (kg/m³) of the stored material.
        
        For gases, uses the compressibility factor Z. For liquids, uses an approximate value.
        """
        if self.phase == PhaseType.GAS:
            Z = self._calculate_compressibility()
            M_kg_per_mol = self.MOLAR_MASSES[self.resource_type]
            T_K = self.state.temperature_K
            P_Pa = self.state.pressure_Pa
            return P_Pa * M_kg_per_mol / (Z * constants.R * T_K)
        else:
            # Approximate liquid density values (kg/m³).
            liquid_density = {
                ResourceType.H2O: 1000.0,
                ResourceType.CO2: 1101.0,
                ResourceType.O2: 1141.0,
                ResourceType.CH4: 422.62,
                ResourceType.H2: 70.85
            }
            return liquid_density[self.resource_type]

    def calculate_available_volume_m3(self) -> float:
        """
        Calculate the available volume (m³) remaining in the tank for additional resource.
        
        Uses the ideal gas law for gases.
        """
        if self.moles <= 0:
            return self.spec.volume_m3
        # Estimate current occupied volume (ideal gas approximation).
        V_current_m3 = self.moles * constants.R * self.state.temperature_K / self.state.pressure_Pa
        return max(0.0, self.spec.volume_m3 - V_current_m3)
    
    def add_resource(self, moles_to_add: float, incoming_temp_K: float) -> float:
        """
        Add resource to the tank.
        
        Args:
            moles_to_add: Amount to add (mol).
            incoming_temp_K: Temperature of the incoming resource (K).
            
        Returns:
            Amount actually added (mol).
        """
        if moles_to_add <= 0:
            return 0.0
        if incoming_temp_K <= 0:
            raise ValueError("Incoming temperature must be positive.")
        
        # Determine the current phase.
        phase = self._determine_phase()

        if phase == PhaseType.LIQUID:
            # For liquids, assume nearly constant pressure. If empty, set a default pressure (e.g., 101325 Pa).
            new_pressure_Pa = self.state.pressure_Pa if self.moles > 0 else 101325
        else:
            if self.moles > 0:
                # Add numerical stability checks
                try:
                    ratio = moles_to_add / max(self.moles, 1e-12)  # Prevent division by zero
                    if abs(ratio) > 1e6:  # Prevent extreme pressure changes
                        return 0.0
                    new_pressure_Pa = self.state.pressure_Pa * (1 + ratio)
                    # Ensure pressure stays within reasonable bounds
                    new_pressure_Pa = min(max(new_pressure_Pa, 1e3), self.spec.max_pressure_Pa)
                except (OverflowError, FloatingPointError):
                    return 0.0
            else:
                try:
                    new_pressure_Pa = moles_to_add * constants.R * incoming_temp_K / self.spec.volume_m3
                    new_pressure_Pa = min(max(new_pressure_Pa, 1e3), self.spec.max_pressure_Pa)
                except (OverflowError, FloatingPointError):
                    return 0.0
        
        # Do not add if new pressure would exceed tank maximum.
        if new_pressure_Pa > self.spec.max_pressure_Pa:
            return 0.0
        
        # Update the temperature by mixing the existing and incoming resource.
        # Here we assume equal molar heat capacity.
        if self.moles > 0:
            Cp_J_per_molK = 29.1  # approximate
            self.state.temperature_K = (self.moles * Cp_J_per_molK * self.state.temperature_K +
                                          moles_to_add * Cp_J_per_molK * incoming_temp_K) / ((self.moles + moles_to_add) * Cp_J_per_molK)
        else:
            self.state.temperature_K = incoming_temp_K
        
        # Update moles and pressure.
        self.moles += moles_to_add
        self.state.pressure_Pa = new_pressure_Pa
        self.phase = self._determine_phase()
        return moles_to_add

    def remove_resource(self, moles_to_remove: float) -> float:
        """
        Remove resource from the tank.
        
        Args:
            moles_to_remove: Amount to remove (mol).
            
        Returns:
            Amount actually removed (mol).
        """
        if moles_to_remove <= 0:
            return 0.0
        
        removed = min(moles_to_remove, self.moles)
        self.moles -= removed
        
        # Update pressure proportionally (ideal gas approximation).
        if self.moles > 0:
            self.state.pressure_Pa *= self.moles / (self.moles + removed)
        else:
            self.state.pressure_Pa = 0.0
        
        self.phase = self._determine_phase()
        return removed

    def step(self, dt_s: float) -> None:
        """
        Advance the tank state by one time step (s).

        This includes:
          - Handling resource leakage,
          - Updating the thermal state via heat transfer with the ambient.
        
        Args:
            dt_s: Time step (s).
        """
        # logger.info(f"Storage tank step: dt={dt_s:.2f} s, resource_type={self.resource_type}, moles={self.moles}, phase={self.phase}, leak_rate_mol_per_s={self.leak_rate_mol_per_s}")
        # Handle leakage.
        if self.leak_rate_mol_per_s > 0:
            leaked_mol = self.leak_rate_mol_per_s * dt_s
            self.remove_resource(leaked_mol)
        
        # Update thermal state.
        ambient_temp_K = 210.0  # Martian ambient temperature (K)
        heat_transfer_coeff_W_per_m2K = 5.0  # approximate value.
        # Estimate surface area: assume a simple cylindrical shape.
        # For simplicity, assume radius based on volume.
        radius_m = (self.spec.volume_m3 / np.pi)**0.5
        # Approximate lateral surface area + top/bottom.
        surface_area_m2 = 2 * np.pi * radius_m**2 + 2 * np.pi * radius_m * (self.spec.volume_m3 / (np.pi * radius_m**2))
        
        # Calculate heat transfer (W) over the time step.
        heat_transfer_W = heat_transfer_coeff_W_per_m2K * surface_area_m2 * (ambient_temp_K - self.state.temperature_K)
        
        if self.moles > 0:
            Cp_J_per_molK = 29.1  # approximate molar heat capacity.
            delta_T_K = heat_transfer_W * dt_s / (self.moles * Cp_J_per_molK)
            # Prevent temperature from going below reasonable bounds
            new_temp = self.state.temperature_K + delta_T_K
            self.state.temperature_K = min(max(new_temp, 273.15), self.spec.max_temperature_K)
            
            # Update pressure based on new temperature (ideal gas law)
            try:
                self.state.pressure_Pa = max(1e3, min(
                    self.moles * constants.R * self.state.temperature_K / self.spec.volume_m3,
                    self.spec.max_pressure_Pa
                ))
            except (OverflowError, FloatingPointError):
                self.state.pressure_Pa = self.spec.max_pressure_Pa
        # Update phase.
        self.phase = self._determine_phase()
