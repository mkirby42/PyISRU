"""
Base classes and types for power systems.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, Optional

class PowerSystemStatus(Enum):
    """Operational status of power systems"""
    ONLINE = auto()
    OFFLINE = auto()
    DEGRADED = auto()
    FAULT = auto()
    MAINTENANCE = auto()

class PowerPriority(Enum):
    """Power priority levels for load shedding"""
    CRITICAL = auto()  # Life support, thermal control
    HIGH = auto()      # ISRU core processes
    MEDIUM = auto()    # Storage, compression
    LOW = auto()       # Maintenance, cleaning

@dataclass
class PowerQuality:
    """Power quality parameters"""
    voltage_nominal: float  # V
    frequency_nominal: float  # Hz
    thd_limit: float  # Total Harmonic Distortion limit (0-1)
    voltage_tolerance: float  # Allowed voltage deviation (0-1)
    
@dataclass
class ThermalManagement:
    """Thermal management parameters"""
    max_temp: float  # K
    min_temp: float  # K
    cooling_power: float  # W/K
    heating_power: float  # W/K
    
@dataclass
class LoadProfile:
    """Power load profile"""
    priority: PowerPriority
    min_power: float  # W
    nominal_power: float  # W
    max_power: float  # W

class PowerSystem(ABC):
    """Abstract base class for all power systems"""
    
    def __init__(self):
        self.status = PowerSystemStatus.OFFLINE
        self.current_output = 0.0  # W
        self.fault_condition: Optional[str] = None
        
        # Power quality monitoring
        self.power_quality = PowerQuality(
            voltage_nominal=120.0,  # V
            frequency_nominal=60.0,  # Hz
            thd_limit=0.05,  # 5% THD limit
            voltage_tolerance=0.1  # ±10% voltage tolerance
        )
        self.current_voltage = self.power_quality.voltage_nominal
        self.current_frequency = self.power_quality.frequency_nominal
        self.current_thd = 0.0
        
        # Thermal management
        self._base_thermal = ThermalManagement(
            max_temp=350.0,  # K
            min_temp=250.0,  # K
            cooling_power=100.0,  # W/K
            heating_power=50.0  # W/K
        )
        self.thermal_management = ThermalManagement(
            max_temp=self._base_thermal.max_temp,
            min_temp=self._base_thermal.min_temp,
            cooling_power=self._base_thermal.cooling_power,
            heating_power=self._base_thermal.heating_power
        )
        self.temperature = 298.15  # K
        self.thermal_power = 0.0  # W
        
        # Load management
        self.loads: Dict[str, LoadProfile] = {}
        self.active_loads: Dict[str, bool] = {}
        self.load_power: Dict[str, float] = {}
        
    def add_load(self, name: str, profile: LoadProfile) -> None:
        """Add a new load to the power system"""
        self.loads[name] = profile
        self.active_loads[name] = False
        self.load_power[name] = 0.0
        
    def activate_load(self, name: str) -> bool:
        """Attempt to activate a load"""
        if name not in self.loads:
            return False
            
        # Check if this is a critical load
        is_critical = self.loads[name].priority == PowerPriority.CRITICAL
        required_power = self.loads[name].min_power
        available_power = self.calculate_available_power()
        
        # If critical load and not enough power, enter emergency mode
        if is_critical and available_power < required_power:
            self.enter_emergency_mode()
            # Activate with reduced power
            self.active_loads[name] = True
            self.load_power[name] = available_power
            return True
            
        # Normal load activation
        if available_power >= required_power:
            self.active_loads[name] = True
            self.load_power[name] = required_power
            return True
            
        return False
        
    def deactivate_load(self, name: str) -> None:
        """Deactivate a load"""
        if name in self.active_loads:
            self.active_loads[name] = False
            self.load_power[name] = 0.0
            
    def calculate_available_power(self) -> float:
        """Calculate power available for new loads"""
        total_output = self.calculate_output()
        current_load = sum(self.load_power.values())
        thermal_load = abs(self.thermal_power)
        return max(0.0, total_output - current_load - thermal_load)
        
    def check_power_quality(self) -> bool:
        """Check if power quality is within limits"""
        voltage_deviation = abs(self.current_voltage - self.power_quality.voltage_nominal)
        voltage_ok = voltage_deviation <= (self.power_quality.voltage_tolerance * 
                                        self.power_quality.voltage_nominal)
                                        
        frequency_ok = abs(self.current_frequency - self.power_quality.frequency_nominal) <= 1.0
        thd_ok = self.current_thd <= self.power_quality.thd_limit
        
        return voltage_ok and frequency_ok and thd_ok
        
    def manage_thermal(self, dt: float) -> None:
        """Manage thermal control"""
        if self.temperature > self.thermal_management.max_temp:
            # Need cooling
            delta_t = self.temperature - self.thermal_management.max_temp
            self.thermal_power = -self.thermal_management.cooling_power * delta_t
        elif self.temperature < self.thermal_management.min_temp:
            # Need heating
            delta_t = self.thermal_management.min_temp - self.temperature
            self.thermal_power = self.thermal_management.heating_power * delta_t
        else:
            self.thermal_power = 0.0
            
    def perform_load_shedding(self) -> None:
        """Perform load shedding based on priorities"""
        available_power = self.calculate_output()
        current_load = sum(self.load_power.values())
        
        if available_power >= current_load:
            return
            
        # Sort loads by priority (lowest to highest)
        sorted_loads = sorted(
            [(name, load) for name, load in self.loads.items()],
            key=lambda x: x[1].priority.value,
            reverse=True  # Reverse to get LOW (4) first
        )
        
        # Deactivate loads from lowest priority until we have enough power
        # Deactivate loads from lowest priority until we have enough power
        for name, load in sorted_loads:  # No need for reversed() since we sorted in reverse
            if not self.active_loads[name] or load.priority == PowerPriority.CRITICAL:
                continue
                
            self.deactivate_load(name)
            current_load = sum(self.load_power.values())
            
            if available_power >= current_load:
                break
                
    def enter_emergency_mode(self) -> None:
        """Enter emergency power mode"""
        # Deactivate all non-critical loads
        for name, load in self.loads.items():
            if load.priority != PowerPriority.CRITICAL:
                self.deactivate_load(name)
                
        # Set minimum thermal control
        self.thermal_management = ThermalManagement(
            max_temp=self._base_thermal.max_temp,
            min_temp=self._base_thermal.min_temp,
            cooling_power=self._base_thermal.cooling_power * 0.5,
            heating_power=self._base_thermal.heating_power * 0.5
        )
        
        self.status = PowerSystemStatus.DEGRADED
        
    def exit_emergency_mode(self) -> None:
        """Exit emergency power mode"""
        # Restore thermal control
        self.thermal_management = ThermalManagement(
            max_temp=self._base_thermal.max_temp,
            min_temp=self._base_thermal.min_temp,
            cooling_power=self._base_thermal.cooling_power,
            heating_power=self._base_thermal.heating_power
        )
        
        self.status = PowerSystemStatus.ONLINE
        
    def step(self, dt: float) -> None:
        """Advance power system state by one time step"""
        # Update thermal management
        self.manage_thermal(dt)
        
        # Check power quality
        if not self.check_power_quality():
            if self.status != PowerSystemStatus.DEGRADED:
                self.enter_emergency_mode()
        elif self.status == PowerSystemStatus.DEGRADED:
            self.exit_emergency_mode()
            
        # Perform load shedding if needed
        self.perform_load_shedding()
        
    @abstractmethod
    def calculate_output(self) -> float:
        """Calculate current power output in Watts"""
        pass 