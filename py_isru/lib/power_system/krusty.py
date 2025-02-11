"""
KRUSTY (Kilopower Reactor Using Stirling Technology) implementation.
"""
from dataclasses import dataclass
from typing import Optional

import numpy as np

from .base import PowerSystem, PowerSystemStatus
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

class KrustyReactor(PowerSystem):
    """Models a KRUSTY-style nuclear reactor with realistic degradation"""
    
    def __init__(self, spec: KrustySpecification):
        super().__init__()
        self.spec = spec
        self.status = PowerSystemStatus.OFFLINE
        
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
    
    def start(self) -> bool:
        """Begin reactor startup sequence"""
        if self.status == PowerSystemStatus.FAULT:
            return False
            
        if self.cooldown_progress < 1.0:
            return False
            
        self.status = PowerSystemStatus.ONLINE
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
            
        self.status = PowerSystemStatus.OFFLINE
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
    
    def step(self, dt: float) -> None:
        """Update reactor state"""
        # Validate timestep
        if dt <= 0:
            raise ValueError("Time step must be positive")
            
        try:
            if self.status == PowerSystemStatus.FAULT:
                self.current_power = 0.0
                return
                
            # Validate current power
            if not isinstance(self.current_power, (int, float)) or np.isnan(self.current_power):
                raise ValueError("Invalid power value")
                
            # Handle startup sequence
            if self.status == PowerSystemStatus.ONLINE and self.startup_progress < 1.0:
                self.startup_progress = min(1.0, self.startup_progress + dt / self.spec.startup_time)
                self.current_power = self.spec.nominal_power * self.startup_progress
                
            # Handle shutdown sequence
            elif self.status == PowerSystemStatus.OFFLINE and self.cooldown_progress < 1.0:
                self.cooldown_progress = min(1.0, self.cooldown_progress + dt / self.spec.cooldown_time)
                self.current_power = self.spec.nominal_power * (1.0 - self.cooldown_progress)
                
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