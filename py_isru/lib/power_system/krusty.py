"""
KRUSTY (Kilopower Reactor Using Stirling Technology) implementation.
"""
from dataclasses import dataclass
from typing import Optional

import numpy as np

from .base import ThermalPowerSystem, PowerSystemStatus
from .constants import (
    SECONDS_PER_YEAR,
    KRUSTY_BURNUP_PER_YEAR,
    KRUSTY_TE_DEG_PER_YEAR,
    KRUSTY_CREEP_PER_YEAR
)

@dataclass
class KrustySpecification:
    """KRUSTY reactor specifications"""
    nominal_power: float      # Nominal power output in Watts
    max_power: float         # Maximum safe power output in Watts
    startup_time: float      # Time required for full startup in seconds
    cooldown_time: float     # Time required for safe shutdown in seconds
    burn_in_time: float      # Required burn-in time in seconds
    
    def __post_init__(self):
        """Validate specifications"""
        if self.nominal_power <= 0:
            raise ValueError("Nominal power must be positive")
        if self.max_power <= self.nominal_power:
            raise ValueError("Max power must be greater than nominal power")
        if self.startup_time <= 0:
            raise ValueError("Startup time must be positive")
        if self.cooldown_time <= 0:
            raise ValueError("Cooldown time must be positive")
        if self.burn_in_time <= 0:
            raise ValueError("Burn-in time must be positive")
    
    def __repr__(self):
        return (f"KrustySpecification(nominal_power={self.nominal_power}, "
                f"max_power={self.max_power}, startup_time={self.startup_time}, "
                f"cooldown_time={self.cooldown_time}, burn_in_time={self.burn_in_time})")

class KrustyReactor(ThermalPowerSystem):
    """Models a KRUSTY-style nuclear reactor with realistic degradation"""
    
    def __init__(self, spec: KrustySpecification):
        super().__init__()
        self.spec = spec
        self.status = PowerSystemStatus.OFFLINE
        
        # Set thermal limits and initial temperature for nuclear reactor
        self.max_temp = 800.0  # K (typical for small nuclear reactor)
        self.min_temp = 400.0  # K (minimum for efficient operation)
        self.temperature = 450.0  # K (initial temperature during standby)
        
        # Progress tracking
        self.startup_progress = 0.0
        self.cooldown_progress = 1.0  # Start fully cooled down
        self.burn_in_time = 0.0
        
        # Operating state
        self.current_power = 0.0  # W
        
        # Degradation tracking
        self.fuel_burnup = 0.0
        self.thermoelectric_degradation = 0.0
        self.material_creep = 0.0
        
        # State flags
        self.burn_in_complete = False
        self.fault_condition: Optional[str] = None
    
    def __repr__(self):
        return (f"KrustyReactor(status={self.status}, current_power={self.current_power}, "
                f"temperature={self.temperature}, startup_progress={self.startup_progress}, "
                f"cooldown_progress={self.cooldown_progress}, burn_in_time={self.burn_in_time}, "
                f"fuel_burnup={self.fuel_burnup}, thermoelectric_degradation={self.thermoelectric_degradation}, "
                f"material_creep={self.material_creep}, fault_condition={self.fault_condition})")
    
    def start(self) -> bool:
        """Begin reactor startup sequence"""
        if self.status == PowerSystemStatus.FAULT:
            return False
            
        if self.cooldown_progress < 1.0:
            return False
            
        self.status = PowerSystemStatus.STARTUP
        self.startup_progress = 0.0
        self.burn_in_complete = False
        self.burn_in_time = 0.0
        return True
    
    def shutdown(self) -> bool:
        """Begin reactor shutdown sequence"""
        if self.status == PowerSystemStatus.FAULT:
            return False
            
        if self.startup_progress < 1.0:
            return False
            
        self.status = PowerSystemStatus.SHUTDOWN
        self.cooldown_progress = 0.0
        return True
    
    def calculate_output(self) -> float:
        """Calculate current power output in Watts"""
        if self.status == PowerSystemStatus.FAULT:
            return 0.0
            
        # Allow power output during cooldown
        if self.status == PowerSystemStatus.OFFLINE and self.cooldown_progress >= 1.0:
            return 0.0
            
        try:
            # Check for invalid power values
            if np.isnan(self.current_power):
                self.status = PowerSystemStatus.FAULT
                self.fault_condition = "Invalid power value: NaN detected"
                return 0.0
                
            # Apply degradation factors
            degradation = 1.0 - (
                self.fuel_burnup +
                self.thermoelectric_degradation +
                self.material_creep
            )
            
            return self.current_power * degradation
            
        except Exception as e:
            self.status = PowerSystemStatus.FAULT
            self.fault_condition = f"Power calculation error: {str(e)}"
            return 0.0
    
    def manage_thermal(self, dt: float) -> None:
        """Update reactor thermal state"""
        try:
            # Call parent thermal management first
            super().manage_thermal(dt)
            
            # Check for invalid power values
            if np.isnan(self.current_power):
                self.status = PowerSystemStatus.FAULT
                self.fault_condition = "Power calculation error: NaN value detected"
                self.current_power = 0.0
                return
            
            if self.status == PowerSystemStatus.FAULT:
                self.current_power = 0.0
                return
                
            # Handle startup sequence
            if self.status == PowerSystemStatus.STARTUP and self.startup_progress < 1.0:
                self.startup_progress = min(1.0, self.startup_progress + dt / self.spec.startup_time)
                self.current_power = self.spec.nominal_power * self.startup_progress
                if self.startup_progress >= 1.0:
                    self.status = PowerSystemStatus.ONLINE
                
            # Handle shutdown sequence
            elif self.status == PowerSystemStatus.SHUTDOWN and self.cooldown_progress < 1.0:
                self.cooldown_progress = min(1.0, self.cooldown_progress + dt / self.spec.cooldown_time)
                self.current_power = self.spec.nominal_power * (1.0 - self.cooldown_progress)
                if self.cooldown_progress >= 1.0:
                    self.status = PowerSystemStatus.OFFLINE
                
            # Track burn-in time only when at full power
            if (self.status == PowerSystemStatus.ONLINE and 
                self.startup_progress >= 1.0 and 
                np.isclose(self.current_power, self.spec.nominal_power, rtol=1e-10) and
                not self.burn_in_complete):
                self.burn_in_time += dt
                if self.burn_in_time >= self.spec.burn_in_time:
                    self.burn_in_complete = True
            
            # Update degradation
            self._update_fuel_burnup(dt)
            self._update_thermoelectric(dt)
            self._update_material_creep(dt)
            
        except Exception as e:
            self.status = PowerSystemStatus.FAULT
            self.fault_condition = f"Step error: {str(e)}"
    
    def _update_fuel_burnup(self, dt: float) -> None:
        """Update fuel burnup degradation"""
        if self.current_power > 0:
            burnup_rate = KRUSTY_BURNUP_PER_YEAR * (self.current_power / self.spec.nominal_power)
            self.fuel_burnup += burnup_rate * dt / SECONDS_PER_YEAR
    
    def _update_thermoelectric(self, dt: float) -> None:
        """Update thermoelectric degradation"""
        if self.current_power > 0:  # Only degrade when operating
            self.thermoelectric_degradation += KRUSTY_TE_DEG_PER_YEAR * dt / SECONDS_PER_YEAR
    
    def _update_material_creep(self, dt: float) -> None:
        """Update material creep degradation"""
        if self.current_power > 0:  # Only degrade when operating
            self.material_creep += KRUSTY_CREEP_PER_YEAR * dt / SECONDS_PER_YEAR 