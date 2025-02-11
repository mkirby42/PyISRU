"""
Sabatier reactor implementation with detailed reaction kinetics.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional
import numpy as np
from scipy import constants

from .reactor import Reactor, ReactorSpecification, ResourceType, OperationalStatus
from .thermodynamics import ThermodynamicState, ReactionKinetics

@dataclass
class SabatierSpecification(ReactorSpecification):
    """Additional specifications specific to Sabatier reactor"""
    catalyst_type: str  # e.g., "Ru/Al₂O₃"
    catalyst_loading: float  # kg/m³
    catalyst_surface_area: float  # m²/g
    catalyst_porosity: float  # dimensionless

class SabatierReactor(Reactor):
    """
    Implements the Sabatier reaction: CO₂ + 4H₂ ⇌ CH₄ + 2H₂O
    Including side reactions and detailed catalyst modeling
    """
    
    def __init__(self,
                 spec: SabatierSpecification,
                 initial_state: ThermodynamicState,
                 kinetics: ReactionKinetics):
        super().__init__(spec, initial_state, kinetics)
        self.spec: SabatierSpecification = spec  # Type hint for IDE
        self.catalyst_degradation = 1.0  # Start with fresh catalyst
        
        # Standard Gibbs free energy changes (J/mol) at 298K
        self.delta_g_standard = {
            "main": -130.8e3,  # CO₂ + 4H₂ → CH₄ + 2H₂O
            "rwgs": 28.6e3,    # CO₂ + H₂ → CO + H₂O
            "methanation": -142.2e3  # CO + 3H₂ → CH₄ + H₂O
        }
        
    def step(self, dt: float, inputs: Dict[ResourceType, float]) -> Dict[ResourceType, float]:
        """Advance reactor state by one time step"""
        if not self.check_safety_limits():
            return {resource: 0.0 for resource in ResourceType}
            
        # Calculate equilibrium constants
        K_main = self.state.calculate_equilibrium_constant(self.delta_g_standard["main"])
        K_rwgs = self.state.calculate_equilibrium_constant(self.delta_g_standard["rwgs"])
        K_meth = self.state.calculate_equilibrium_constant(self.delta_g_standard["methanation"])
        
        # Calculate concentrations (mol/m³)
        concentrations = {
            "CO2": inputs.get(ResourceType.CO2, 0.0) / self.spec.volume,
            "H2": inputs.get(ResourceType.H2, 0.0) / self.spec.volume,
            "CH4": 0.0,  # Will be updated
            "H2O": 0.0,  # Will be updated
        }
        
        # Calculate main reaction rate
        forward_rate = self.kinetics.calculate_rate(
            concentrations,
            self.state.temperature,
            self.catalyst_degradation
        )
        
        # Calculate reverse rate based on equilibrium
        # At high temperatures, K_main decreases, increasing reverse rate
        reverse_rate = forward_rate / K_main
        net_rate = forward_rate - reverse_rate
        
        # Update concentrations based on stoichiometry
        outputs = {
            ResourceType.CO2: inputs.get(ResourceType.CO2, 0.0) - net_rate * dt,
            ResourceType.H2: inputs.get(ResourceType.H2, 0.0) - 4 * net_rate * dt,
            ResourceType.CH4: net_rate * dt,
            ResourceType.H2O: 2 * net_rate * dt
        }
        
        # Calculate heat generation (ΔH = -165.0 kJ/mol)
        # Positive heat means temperature increases
        heat_generated = -net_rate * -165.0e3  # Watts
        
        # Update thermal state
        heat_loss = self.calculate_heat_loss()
        net_heat = heat_generated - heat_loss
        
        # Add gas heat capacity effects
        total_moles = sum(inputs.values())
        if total_moles > 0:
            Cp_gas = 30.0  # J/(mol·K), approximate average
            gas_thermal_mass = total_moles * Cp_gas
            effective_thermal_mass = self.spec.thermal_mass + gas_thermal_mass
        else:
            effective_thermal_mass = self.spec.thermal_mass
            
        self.state.temperature += net_heat * dt / effective_thermal_mass
        
        # Update catalyst degradation (simple model)
        # 0.5% degradation per day at 700K, doubles every 10K above that
        base_degradation_rate = 0.005 / (24 * 3600)  # Convert to per second
        temp_factor = 2 ** ((self.state.temperature - 700) / 10)
        self.catalyst_degradation *= (1 - base_degradation_rate * temp_factor * dt)
        
        self.update_uptime(dt)
        return outputs
        
    def calculate_power_consumption(self) -> float:
        """Calculate power consumption for pumps and heating"""
        if self.operational_status != OperationalStatus.RUNNING:
            return 0.0
            
        # Power for maintaining temperature
        heating_power = max(0, self.calculate_heat_loss())
        
        # Power for pumps (simplified model)
        pump_power = 100.0
        
        return heating_power + pump_power
        
    def start(self):
        """Start the reactor"""
        if self.operational_status == OperationalStatus.STANDBY:
            self.operational_status = OperationalStatus.STARTUP
            # TODO: Implement startup sequence
            self.operational_status = OperationalStatus.RUNNING
            
    def shutdown(self):
        """Shutdown the reactor"""
        if self.operational_status == OperationalStatus.RUNNING:
            self.operational_status = OperationalStatus.SHUTDOWN
            # TODO: Implement shutdown sequence
            self.operational_status = OperationalStatus.STANDBY 