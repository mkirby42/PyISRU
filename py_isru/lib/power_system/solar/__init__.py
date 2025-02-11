"""
Solar power system components.

This package provides components for modeling solar power systems on Mars:
- Individual solar panels with realistic physics and degradation
- Solar tracking systems for optimizing panel orientation
- Environmental modeling of Mars conditions affecting solar power
"""

from .panel import SolarPanel, SolarPanelSpecification
from .tracker import Tracker, TrackerSpecification, TrackingType
from .array import SolarArray, SolarArraySpecification
from .environment import (
    MarsEnvironment,
    MarsEnvironmentSpecification,
    DustStormSeverity,
) 