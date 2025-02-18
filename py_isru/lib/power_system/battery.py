"""
Simple battery implementation tracking energy in/out with basic fault detection.
"""
import logging
from dataclasses import dataclass
from typing import Union, Optional

from .base import StoragePowerSystem, PowerSystemStatus

logger = logging.getLogger(__name__)

@dataclass
class BatterySpecification:
    capacity_wh: float  # Watt-hours
    max_power: float   # Watts (both charge and discharge)
    initial_state_of_charge: Optional[float] = 0.0  # Default to 0, range 0-1

    def __post_init__(self):
        if self.capacity_wh <= 0:
            raise ValueError("Capacity must be positive")
        if self.max_power <= 0:
            raise ValueError("Max power must be positive")
        if not (0.0 <= self.initial_state_of_charge <= 1.0):
            raise ValueError("Initial state of charge must be between 0 and 1")

    def __repr__(self):
        return (f"BatterySpecification(capacity_wh={self.capacity_wh}, "
                f"max_power={self.max_power}, "
                f"initial_state_of_charge={self.initial_state_of_charge})")

class Battery(StoragePowerSystem):
    def __init__(self, spec: BatterySpecification):
        super().__init__()
        self.spec = spec
        self.energy_wh = self.spec.capacity_wh * self.spec.initial_state_of_charge
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
        Raises:
            ValueError: If dt <= 0 (programming error)
        """
        # logger.info(f"Battery update: power={power}, dt={dt}")
        try:
            # Convert to float first, will raise TypeError/ValueError if invalid
            power = float(power)
        except (TypeError, ValueError) as e:
            self.status = PowerSystemStatus.FAULT
            self.fault_condition = f"Invalid power input: {str(e)}"
            return 0.0
            
        # Validate dt is a number
        try:
            dt = float(dt)
        except (TypeError, ValueError) as e:
            self.status = PowerSystemStatus.FAULT
            self.fault_condition = f"Invalid time step type: {str(e)}"
            return 0.0
            
        # Programming error - let ValueError propagate
        if dt <= 0:
            raise ValueError("Time step must be positive")
        
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
        self.charging = power > 0

        return power

    def calculate_output(self) -> float:
        """Calculate maximum power output available in Watts"""
        if self.status != PowerSystemStatus.ONLINE:
            return 0.0
        
        # Can discharge up to max_power if we have energy
        if self.energy_wh > 0:
            return self.spec.max_power
        return 0.0

    # Override the manage_thermal method to do nothing
    def manage_thermal(self, dt: float) -> None:
        pass
    
    # Override the check_power_quality method to do nothing
    def check_power_quality(self) -> bool:
        return True
    
    # def step(self, dt: float) -> None:
    #     self.manage_thermal(dt)
    #     self.check_power_quality()  
    #     self.update(0.0, dt)
    #     self.update_status()
    #     self.calculate_output()

    def __repr__(self):
        return (f"Battery(status={self.status}, energy_wh={self.energy_wh:.2f}, "
                f"state_of_charge={self.state_of_charge:.2f})")