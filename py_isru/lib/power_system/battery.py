"""
Simple battery implementation tracking energy in/out with basic fault detection.
"""
from dataclasses import dataclass
from typing import Union, Optional
import math

from .base import PowerSystem, PowerSystemStatus

@dataclass
class BatterySpecification:
    capacity_wh: float  # Watt-hours
    max_power: float   # Watts (both charge and discharge)

    def __post_init__(self):
        if self.capacity_wh <= 0:
            raise ValueError("Capacity must be positive")
        if self.max_power <= 0:
            raise ValueError("Max power must be positive")

class Battery(PowerSystem):
    def __init__(self, spec: BatterySpecification):
        self.spec = spec
        self.energy_wh = 0.0  # Current energy stored
        self.status = PowerSystemStatus.ONLINE

    @property
    def state_of_charge(self) -> float:
        """Return state of charge as 0-1 percentage"""
        return self.energy_wh / self.spec.capacity_wh

    def update(self, power: Union[int, float], dt: float) -> float:
        """
        Update battery state with power flow for dt seconds
        Args:
            power: Power in Watts (positive = charging, negative = discharging)
            dt: Time step in seconds
        Returns:
            Actual power used (may be limited by constraints)
        """
        # Input validation
        if not isinstance(power, (int, float)):
            self.status = PowerSystemStatus.FAULT
            return 0.0

        if not isinstance(dt, (int, float)) or dt <= 0:
            self.status = PowerSystemStatus.FAULT
            return 0.0

        # Limit power to max rating
        power = max(-self.spec.max_power, min(power, self.spec.max_power))

        # Calculate energy change
        energy_change_wh = power * dt / 3600.0  # Convert W*s to Wh
        new_energy = self.energy_wh + energy_change_wh

        # Handle capacity limits
        if new_energy > self.spec.capacity_wh:
            # Calculate power needed to exactly fill the remaining capacity
            remaining_capacity = self.spec.capacity_wh - self.energy_wh
            power = remaining_capacity * 3600.0 / dt
        elif new_energy < 0:
            # Calculate power needed to exactly drain remaining energy
            power = -self.energy_wh * 3600.0 / dt

        # Final energy update with limited power
        energy_change_wh = power * dt / 3600.0
        self.energy_wh = min(self.spec.capacity_wh, max(0.0, self.energy_wh + energy_change_wh))

        return power

    def calculate_output(self) -> float:
        """Calculate maximum power output available in Watts"""
        if self.status != PowerSystemStatus.ONLINE:
            return 0.0
        
        # Can discharge up to max_power if we have energy
        if self.energy_wh > 0:
            return self.spec.max_power
        return 0.0