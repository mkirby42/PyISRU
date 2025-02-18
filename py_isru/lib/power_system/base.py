"""
Base classes for power systems.
"""
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import Optional

class PowerSystemStatus(Enum):
    """Operational status of power systems"""
    ONLINE = auto()
    OFFLINE = auto()
    DEGRADED = auto()
    FAULT = auto()
    MAINTENANCE = auto()
    STARTUP = auto()
    SHUTDOWN = auto()

class PowerSystem(ABC):
    """Abstract base class for all power systems"""
    
    def __init__(self):
        self.status = PowerSystemStatus.OFFLINE
        self.fault_condition: Optional[str] = None
        
    @abstractmethod
    def calculate_output(self) -> float:
        """Calculate current power output in Watts"""
        pass
        
    def step(self, dt: float) -> None:
        """Advance power system state by one time step"""
        if dt <= 0:
            raise ValueError("Time step must be positive")

class ThermalPowerSystem(PowerSystem):
    """Base class for systems with thermal management"""
    
    def __init__(self):
        super().__init__()
        self.temperature = 298.15  # K
        self.max_temp = 350.0  # K
        self.min_temp = 250.0  # K
        
    def manage_thermal(self, dt: float) -> None:
        """Handle thermal state changes"""
        # Check temperature limits
        if self.temperature > self.max_temp or self.temperature < self.min_temp:
            self.status = PowerSystemStatus.FAULT
            self.fault_condition = f"Temperature {self.temperature-273.15:.1f}°C outside limits"
        elif self.status == PowerSystemStatus.FAULT and self.fault_condition and "Temperature" in self.fault_condition:
            # Only clear temperature faults, leave other faults alone
            self.status = PowerSystemStatus.ONLINE
            self.fault_condition = None
        
    def step(self, dt: float) -> None:
        """Advance thermal power system state"""
        super().step(dt)
        self.manage_thermal(dt)

class StoragePowerSystem(PowerSystem):
    """Base class for energy storage systems"""
    
    def __init__(self):
        super().__init__()
        self.charging = False
        
    @abstractmethod
    def update(self, power: float, dt: float) -> float:
        """
        Handle charge/discharge
        Args:
            power: Power in Watts (positive = charging, negative = discharging)
            dt: Time step in seconds
        Returns:
            Actual power used (may be limited by constraints)
        """
        if dt <= 0:
            raise ValueError("Time step must be positive")
        return 0.0 