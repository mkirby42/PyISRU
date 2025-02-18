"""
Base reactor class and related enums for the ISRU system.
"""
from abc import ABC, abstractmethod
import logging
from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, List, Optional
from .thermodynamics import ThermodynamicState

logger = logging.getLogger(__name__)
class ResourceType(Enum):
    """Types of resources that can be produced or consumed"""
    CO2 = auto()
    H2 = auto()
    O2 = auto()
    CH4 = auto()
    H2O = auto()
    CO = auto()  # Needed for RWGS and methanation

    def __repr__(self):
        return f"{self.name}"

class OperationalStatus(Enum):
    """Possible operational states of a reactor"""
    STARTUP = auto()
    RUNNING = auto()
    SHUTDOWN = auto()
    STANDBY = auto()
    FAULT = auto()
    MAINTENANCE = auto()

    def __repr__(self):
        return f"OperationalStatus.{self.name}"

@dataclass
class ReactorSpecification:
    """
    Specification for a reactor including physical parameters.
    
    Units:
      - volume_m3: reactor volume in m³
      - max_temperature_K: maximum operating temperature (K)
      - max_pressure_Pa: maximum operating pressure (Pa)
      - thermal_mass_J_per_K: reactor structural thermal mass (J/K)
      - heat_loss_coefficient_W_per_m2K: heat loss coefficient (W/(m²·K))
      - surface_area_m2: external surface area (m²)
    """
    volume_m3: float
    max_temperature_K: float
    max_pressure_Pa: float
    thermal_mass_J_per_K: float
    heat_loss_coefficient_W_per_m2K: float
    surface_area_m2: float

class Reactor:
    """
    Abstract base class for all reactors.
    """
    def __init__(self,
                 spec: ReactorSpecification,
                 initial_state: ThermodynamicState):
        self.spec = spec
        self.state = initial_state
        self.operational_status = OperationalStatus.STANDBY
        self.fault_condition: Optional[str] = None
        self.uptime_hours = 0.0

    def check_safety_limits(self) -> bool:
        """Check if reactor is operating within safety limits."""
        if self.state.temperature_K > self.spec.max_temperature_K:
            logger.error(f"Temperature exceeded maximum limit: {self.state.temperature_K:.2f} K > {self.spec.max_temperature_K:.2f} K")
            self.fault_condition = "Temperature exceeded maximum limit"
            self.operational_status = OperationalStatus.FAULT
            return False
        if self.state.pressure_Pa > self.spec.max_pressure_Pa:
            logger.error(f"Pressure exceeded maximum limit: {self.state.pressure_Pa:.2f} Pa > {self.spec.max_pressure_Pa:.2f} Pa")
            self.fault_condition = "Pressure exceeded maximum limit"
            self.operational_status = OperationalStatus.FAULT
            return False
        return True

    def calculate_heat_loss(self) -> float:
        """
        Calculate heat loss to the environment (W).
        Assumes a Martian ambient temperature of 210 K.
        """
        return self.spec.heat_loss_coefficient_W_per_m2K * self.spec.surface_area_m2 * (self.state.temperature_K - 210)

    def update_uptime(self, dt_s: float):
        """Update reactor uptime (in hours)."""
        if self.operational_status in [OperationalStatus.RUNNING, OperationalStatus.STARTUP]:
            self.uptime_hours += dt_s / 3600