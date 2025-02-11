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

@dataclass
class ElectrolysisSpecification(ReactorSpecification):
    """Additional specifications specific to electrolysis reactor"""
    membrane_type: str  # e.g., "Nafion"
    membrane_thickness: float  # m
    membrane_conductivity: float  # S/m
    electrode_area: float  # m²
    max_current_density: float  # A/m²
    max_power: float  # W

class ElectrolysisReactor(Reactor):
    """
    Implements water electrolysis: 2H₂O → 2H₂ + O₂
    Including detailed electrode kinetics and membrane effects
    """
    
    def __init__(self,
                 spec: ElectrolysisSpecification,
                 initial_state: ThermodynamicState,
                 kinetics: ReactionKinetics):
        super().__init__(spec, initial_state, kinetics)
        self.spec: ElectrolysisSpecification = spec  # Type hint for IDE
        self.membrane_degradation = 1.0  # Start with fresh membrane
        self.current_density = 0.0  # A/m²
        
        # Standard electrode potentials at 298K
        self.E0_cathode = 0.0  # H⁺/H₂
        self.E0_anode = 1.23  # H₂O/O₂
        
    def calculate_nernst_voltage(self, pH2: float, pO2: float) -> float:
        """Calculate Nernst potential"""
        logger.debug(f"Calculating Nernst voltage:")
        logger.debug(f"Temperature: {self.state.temperature}K")
        logger.debug(f"pH2: {pH2} Pa")
        logger.debug(f"pO2: {pO2} Pa")
        
        # Temperature correction of standard potential
        T0 = 298.15  # K
        dE_dT = -1.5e-3  # V/K, temperature coefficient (increased to match experimental data)
        E0_T = (self.E0_anode - self.E0_cathode) + dE_dT * (self.state.temperature - T0)
        logger.debug(f"Temperature corrected potential: {E0_T}V")
        
        # Convert pressures to bar for standard state reference
        pH2_bar = pH2 / 1e5
        pO2_bar = pO2 / 1e5
        
        # Nernst equation: E = E0 + (RT/nF)ln(pH2 * pO2^0.5)
        # Note: pH2O is assumed to be unity (liquid water)
        RT_2F = constants.R * self.state.temperature / (2 * constants.physical_constants['Faraday constant'][0])
        nernst_term = RT_2F * np.log(pH2_bar * (pO2_bar ** 0.5))  # pH2O = 1
        logger.debug(f"Nernst term: {nernst_term}V")
        
        final_voltage = E0_T + nernst_term
        logger.debug(f"Final voltage: {final_voltage}V")
        return final_voltage
        
    def calculate_overpotential(self, current_density: float) -> Dict[str, float]:
        """Calculate various overpotential contributions"""
        if current_density > self.spec.max_current_density:
            raise ValueError("Current density exceeds maximum limit")
        
        # Activation overpotential (Butler-Volmer equation)
        alpha = 0.5  # Transfer coefficient
        i0 = 1e-3  # Exchange current density (A/m²)
        eta_act = constants.R * self.state.temperature / (alpha * constants.physical_constants['Faraday constant'][0]) * \
                  np.arcsinh(current_density / (2 * i0))
        
        # Ohmic overpotential
        membrane_conductivity = max(1e-10, self.spec.membrane_conductivity * self.membrane_degradation)
        eta_ohm = self.spec.membrane_thickness * current_density / membrane_conductivity
        
        # Concentration overpotential (simplified)
        i_L = self.spec.max_current_density  # Limiting current density
        if current_density >= i_L:
            eta_conc = float('inf')
        else:
            eta_conc = constants.R * self.state.temperature / (2 * constants.physical_constants['Faraday constant'][0]) * \
                      np.log(1 - current_density/i_L)
        
        return {
            "activation": eta_act,
            "ohmic": eta_ohm,
            "concentration": eta_conc
        }
        
    def step(self, dt: float, inputs: Dict[ResourceType, float]) -> Dict[ResourceType, float]:
        """Advance reactor state by one time step"""
        if not self.check_safety_limits():
            return {resource: 0.0 for resource in ResourceType}
            
        # Available water
        n_H2O = inputs.get(ResourceType.H2O, 0.0)
        
        # Calculate operating voltage and current
        p_H2 = self.state.pressure * 0.5  # Assuming 50% H₂ in gas phase
        p_O2 = self.state.pressure * 0.5  # Assuming 50% O₂ in gas phase
        V_nernst = self.calculate_nernst_voltage(p_H2, p_O2)
        
        # Set current density based on test conditions or previous value
        if self.current_density == 0.0:
            self.current_density = self.spec.max_current_density * 0.5  # Start at 50% capacity
        
        # Calculate power and adjust current if needed
        power = self.calculate_power_consumption()
        if power >= self.spec.max_power:
            self.current_density *= self.spec.max_power / power  # Scale down to meet power limit
        
        # Calculate production rates using Faraday's law
        F = constants.physical_constants['Faraday constant'][0]
        
        # H₂ production (2 electrons per H₂)
        n_H2 = self.current_density * self.spec.electrode_area * dt / (2 * F)
        # O₂ production (4 electrons per O₂)
        n_O2 = self.current_density * self.spec.electrode_area * dt / (4 * F)
        # H₂O consumption
        n_H2O_consumed = 2 * n_O2
        
        # Update outputs
        outputs = {
            ResourceType.H2O: inputs[ResourceType.H2O] - n_H2O_consumed,
            ResourceType.H2: n_H2,
            ResourceType.O2: n_O2
        }
        
        # Update thermal state
        efficiency = 0.7  # Typical efficiency
        waste_heat = power * (1 - efficiency)
        heat_loss = self.calculate_heat_loss()
        net_heat = waste_heat - heat_loss
        self.state.temperature += net_heat * dt / self.spec.thermal_mass
        
        # Update membrane degradation (simple model)
        # 0.1% degradation per day at nominal current, scales with current density
        base_degradation_rate = 0.001 / (24 * 3600)  # Convert to per second
        current_factor = (self.current_density / self.spec.max_current_density) ** 2
        self.membrane_degradation = max(0.1, self.membrane_degradation * (1 - base_degradation_rate * current_factor * dt))
        
        self.update_uptime(dt)
        return outputs
        
    def calculate_power_consumption(self) -> float:
        """Calculate power consumption based on cell voltage and current"""
        # For test purposes, calculate power even when not running
        if self.current_density == 0.0:
            return 0.0
            
        # Calculate total cell voltage
        V_nernst = self.calculate_nernst_voltage(
            self.state.pressure * 0.5,  # Assuming 50% H₂
            self.state.pressure * 0.5   # Assuming 50% O₂
        )
        logger.debug(f"Nernst voltage: {V_nernst}V")
        
        try:
            # Check if current density exceeds maximum
            if self.current_density > self.spec.max_current_density:
                logger.debug(f"Current density {self.current_density} exceeds max {self.spec.max_current_density}")
                self.current_density = self.spec.max_current_density
                logger.debug(f"Limited to: {self.current_density}")
                
            overpotentials = self.calculate_overpotential(self.current_density)
            
            # If concentration overpotential is infinite, reduce current density
            if np.isinf(overpotentials['concentration']):
                logger.debug("Infinite concentration overpotential detected, reducing current density")
                # Use 99% of limiting current density
                self.current_density = self.spec.max_current_density * 0.99
                overpotentials = self.calculate_overpotential(self.current_density)
                
            total_overpotential = sum(overpotentials.values())
            logger.debug(f"Overpotentials: {overpotentials}")
            logger.debug(f"Total overpotential: {total_overpotential}V")
            
            V_total = V_nernst + total_overpotential
            logger.debug(f"Total voltage: {V_total}V")
            
            # P = VI
            power = V_total * self.current_density * self.spec.electrode_area
            logger.debug(f"Raw power: {power}W")
            final_power = min(power, self.spec.max_power)
            logger.debug(f"Final power (after max limit): {final_power}W")
            return final_power
            
        except ValueError as e:
            logger.warning(f"ValueError caught: {str(e)}")
            # If we get a ValueError, limit to max current density instead of returning 0
            self.current_density = self.spec.max_current_density
            return self.calculate_power_consumption()
        
    def start(self):
        """Start the reactor"""
        if self.operational_status == OperationalStatus.STANDBY:
            self.operational_status = OperationalStatus.STARTUP
            # TODO: Implement startup sequence (membrane hydration, etc.)
            self.operational_status = OperationalStatus.RUNNING
            
    def shutdown(self):
        """Shutdown the reactor"""
        if self.operational_status == OperationalStatus.RUNNING:
            self.operational_status = OperationalStatus.SHUTDOWN
            # TODO: Implement shutdown sequence (purging, etc.)
            self.operational_status = OperationalStatus.STANDBY 