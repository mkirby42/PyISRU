"""
Base reactor class and related enums for the ISRU system.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, List, Optional

from .thermodynamics import ThermodynamicState, ReactionKinetics

class ResourceType(Enum):
    """Types of resources that can be produced or consumed"""
    CO2 = auto()
    H2 = auto()
    O2 = auto()
    CH4 = auto()
    H2O = auto()

class OperationalStatus(Enum):
    """Possible operational states of a reactor"""
    STARTUP = auto()
    RUNNING = auto()
    SHUTDOWN = auto()
    STANDBY = auto()
    FAULT = auto()
    MAINTENANCE = auto()

@dataclass
class ReactorSpecification:
    """Specification for a reactor including physical parameters"""
    volume: float  # m³
    max_temperature: float  # K
    max_pressure: float  # Pa
    thermal_mass: float  # J/K
    heat_loss_coefficient: float  # W/(m²⋅K)
    surface_area: float  # m²

class Reactor(ABC):
    """Abstract base class for all chemical reactors in the system"""
    
    def __init__(self, 
                 spec: ReactorSpecification,
                 initial_state: ThermodynamicState,
                 kinetics: ReactionKinetics):
        self.spec = spec
        self.state = initial_state
        self.kinetics = kinetics
        self.operational_status = OperationalStatus.STANDBY
        self.fault_condition: Optional[str] = None
        self.uptime = 0.0  # hours
        
    @abstractmethod
    def step(self, dt: float, inputs: Dict[ResourceType, float]) -> Dict[ResourceType, float]:
        """
        Advance reactor simulation by one time step
        
        Args:
            dt: Time step in seconds
            inputs: Dict of input resource flow rates in mol/s
            
        Returns:
            Dict of output resource flow rates in mol/s
        """
        pass
    
    @abstractmethod
    def calculate_power_consumption(self) -> float:
        """Calculate current power consumption in Watts"""
        pass
    
    def check_safety_limits(self) -> bool:
        """Check if reactor is operating within safety limits"""
        if self.state.temperature > self.spec.max_temperature:
            self.fault_condition = "Temperature exceeded maximum limit"
            self.operational_status = OperationalStatus.FAULT
            return False
            
        if self.state.pressure > self.spec.max_pressure:
            self.fault_condition = "Pressure exceeded maximum limit"
            self.operational_status = OperationalStatus.FAULT
            return False
            
        return True
    
    def calculate_heat_loss(self) -> float:
        """Calculate heat loss to environment in Watts"""
        # Assuming Martian ambient temperature of 210K
        return self.spec.heat_loss_coefficient * self.spec.surface_area * \
               (self.state.temperature - 210)
               
    def update_uptime(self, dt: float):
        """Update reactor uptime"""
        if self.operational_status == OperationalStatus.RUNNING:
            self.uptime += dt / 3600  # Convert seconds to hours 