"""
Solar tracker implementation with basic mechanical limits and power consumption.
"""
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional, Tuple

import numpy as np

from ..base import PowerSystem, PowerSystemStatus


class TrackingType(Enum):
    """Type of tracking system"""
    FIXED = auto()        # No tracking
    SINGLE_AXIS = auto()  # One axis (typically E-W)
    DUAL_AXIS = auto()    # Two axes (complete sun tracking)


@dataclass
class TrackerSpecification:
    type: TrackingType        # Type of tracking system
    power_consumption: float  # Power used by tracking system (W)
    max_slew_rate: float     # Maximum rotation speed (deg/s)
    
    def __post_init__(self):
        """Validate specifications"""
        if self.power_consumption < 0:
            raise ValueError("Power consumption must be non-negative")
        if self.max_slew_rate <= 0:
            raise ValueError("Maximum slew rate must be positive")


class Tracker(PowerSystem):
    """Models a solar tracker with mechanical limits"""
    
    def __init__(self, spec: TrackerSpecification):
        super().__init__()
        self.spec = spec
        self.status = PowerSystemStatus.ONLINE
        
        # Current angles (degrees)
        self.azimuth: float = 0.0    # E-W rotation
        self.elevation: float = 0.0   # N-S tilt
        
        # Target angles (degrees)
        self.target_azimuth: float = 0.0
        self.target_elevation: float = 0.0
        
        # Operating state
        self.is_moving: bool = False
        
        # Fault tracking
        self.fault_condition: Optional[str] = None
    
    def calculate_output(self) -> float:
        """Calculate power consumption in Watts (negative since consuming)"""
        if self.status == PowerSystemStatus.FAULT:
            return 0.0
            
        # Only consume power when moving
        if self.is_moving:
            return -self.spec.power_consumption
        return 0.0
    
    def get_angles(self) -> Tuple[float, float]:
        """Get current tracker angles"""
        return self.azimuth, self.elevation
    
    def update(self, dt: float) -> None:
        """Update tracker position"""
        if dt <= 0:
            raise ValueError("Time step must be positive")
            
        if self.status == PowerSystemStatus.FAULT:
            return
            
        try:
            # Calculate maximum movement this timestep
            max_movement = self.spec.max_slew_rate * dt
            
            # Track if any movement occurred
            moved = False
            
            # Update azimuth if using appropriate tracking
            if self.spec.type in [TrackingType.SINGLE_AXIS, TrackingType.DUAL_AXIS]:
                az_diff = self.target_azimuth - self.azimuth
                az_move = np.clip(az_diff, -max_movement, max_movement)
                if abs(az_move) > 0.1:
                    self.azimuth += az_move
                    moved = True
                
            # Update elevation if using dual axis
            if self.spec.type == TrackingType.DUAL_AXIS:
                el_diff = self.target_elevation - self.elevation
                el_move = np.clip(el_diff, -max_movement, max_movement)
                if abs(el_move) > 0.1:
                    self.elevation += el_move
                    moved = True
                
            # Update movement state after moving
            self.is_moving = moved
            
        except Exception as e:
            self.status = PowerSystemStatus.FAULT
            self.fault_condition = f"Movement error: {str(e)}"
    
    def track_sun(self, sun_azimuth: float, sun_elevation: float) -> None:
        """
        Set tracking angles to follow the sun
        Args:
            sun_azimuth: Sun's azimuth angle (degrees)
            sun_elevation: Sun's elevation angle (degrees)
        """
        if self.status == PowerSystemStatus.FAULT:
            return
            
        if self.spec.type == TrackingType.FIXED:
            return
            
        # Update azimuth for single/dual axis
        if self.spec.type in [TrackingType.SINGLE_AXIS, TrackingType.DUAL_AXIS]:
            self.target_azimuth = sun_azimuth
            
        # Update elevation for dual axis
        if self.spec.type == TrackingType.DUAL_AXIS:
            self.target_elevation = sun_elevation
            
        # Check if we need to move after setting targets
        self.is_moving = (
            abs(self.target_azimuth - self.azimuth) > 0.1 or
            abs(self.target_elevation - self.elevation) > 0.1
        )
