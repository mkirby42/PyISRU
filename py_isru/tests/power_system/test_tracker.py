"""
Tests for solar tracker implementation.
"""
import pytest
import numpy as np

from py_isru.lib.power_system.solar.tracker import (
    Tracker,
    TrackerSpecification,
    TrackingType,
    PowerSystemStatus
)


@pytest.fixture
def basic_tracker_spec():
    """Basic tracker specification"""
    return TrackerSpecification(
        type=TrackingType.DUAL_AXIS,
        power_consumption=50.0,     # 50W when moving
        max_slew_rate=5.0,         # 5 deg/s
    )

def test_tracker_spec_validation():
    """Test tracker specification validation"""
    # Valid spec should work
    spec = TrackerSpecification(
        type=TrackingType.DUAL_AXIS,
        power_consumption=50.0,
        max_slew_rate=5.0,
    )
    assert spec.power_consumption == 50.0
    assert spec.max_slew_rate == 5.0
    
    # Invalid specs should raise
    with pytest.raises(ValueError):
        TrackerSpecification(
            type=TrackingType.DUAL_AXIS,
            power_consumption=-50.0,  # Negative power
            max_slew_rate=5.0,
        )
    
    with pytest.raises(ValueError):
        TrackerSpecification(
            type=TrackingType.DUAL_AXIS,
            power_consumption=50.0,
            max_slew_rate=0.0,  # Zero slew rate
        )

def test_tracker_initial_state(basic_tracker_spec):
    """Test initial tracker state"""
    tracker = Tracker(basic_tracker_spec)
    assert tracker.status == PowerSystemStatus.ONLINE
    assert tracker.azimuth == 0.0
    assert tracker.elevation == 0.0
    assert tracker.target_azimuth == 0.0
    assert tracker.target_elevation == 0.0
    assert not tracker.is_moving
    assert tracker.fault_condition is None

def test_fixed_tracker():
    """Test fixed (non-tracking) mount"""
    spec = TrackerSpecification(
        type=TrackingType.FIXED,
        power_consumption=50.0,
        max_slew_rate=5.0,
    )
    tracker = Tracker(spec)
    
    # Should not move when tracking sun
    tracker.track_sun(sun_azimuth=45.0, sun_elevation=30.0)
    tracker.update(dt=1.0)
    assert tracker.azimuth == 0.0
    assert tracker.elevation == 0.0
    assert not tracker.is_moving
    assert tracker.calculate_output() == 0.0  # No power consumption

def test_single_axis_tracking(basic_tracker_spec):
    """Test single-axis tracking"""
    spec = TrackerSpecification(
        type=TrackingType.SINGLE_AXIS,
        power_consumption=basic_tracker_spec.power_consumption,
        max_slew_rate=basic_tracker_spec.max_slew_rate,
    )
    tracker = Tracker(spec)
    
    # Should track azimuth but not elevation
    tracker.track_sun(sun_azimuth=45.0, sun_elevation=30.0)
    
    # Move for 5 seconds
    for _ in range(5):
        tracker.update(dt=1.0)
        
    assert np.isclose(tracker.azimuth, 25.0)  # 5 deg/s * 5s = 25 deg
    assert tracker.elevation == 0.0  # Should not change
    assert tracker.is_moving  # Still moving
    assert tracker.calculate_output() == -50.0  # Using power

def test_dual_axis_tracking(basic_tracker_spec):
    """Test dual-axis tracking"""
    tracker = Tracker(basic_tracker_spec)
    
    # Track sun at 45° azimuth, 30° elevation
    tracker.track_sun(sun_azimuth=45.0, sun_elevation=30.0)
    
    # Move for 5 seconds
    for _ in range(5):
        tracker.update(dt=1.0)
        
    assert np.isclose(tracker.azimuth, 25.0)  # 5 deg/s * 5s = 25 deg
    assert np.isclose(tracker.elevation, 25.0)  # 5 deg/s * 5s = 25 deg
    assert tracker.is_moving  # Still moving
    assert tracker.calculate_output() == -50.0  # Using power
    
    # Move until target reached
    for _ in range(5):
        tracker.update(dt=1.0)
        
    assert np.isclose(tracker.azimuth, 45.0, rtol=0.1)
    assert np.isclose(tracker.elevation, 30.0, rtol=0.1)
    assert not tracker.is_moving  # Should stop
    assert tracker.calculate_output() == 0.0  # No power when stopped

def test_slew_rate_limits(basic_tracker_spec):
    """Test movement rate limits"""
    tracker = Tracker(basic_tracker_spec)
    
    # Try to move 90 degrees
    tracker.track_sun(sun_azimuth=90.0, sun_elevation=0.0)
    tracker.update(dt=1.0)
    
    # Should only move at max rate
    assert np.isclose(tracker.azimuth, 5.0)  # max 5 deg/s
    
    # Test with small timestep
    tracker = Tracker(basic_tracker_spec)
    tracker.track_sun(sun_azimuth=90.0, sun_elevation=0.0)
    tracker.update(dt=0.1)
    
    assert np.isclose(tracker.azimuth, 0.5)  # 5 deg/s * 0.1s = 0.5 deg

def test_fault_handling(basic_tracker_spec):
    """Test fault detection and handling"""
    tracker = Tracker(basic_tracker_spec)
    
    # Test negative timestep
    with pytest.raises(ValueError):
        tracker.update(dt=-1.0)
    
    # Should stop moving in fault state
    tracker.track_sun(sun_azimuth=45.0, sun_elevation=30.0)
    tracker.status = PowerSystemStatus.FAULT
    tracker.update(dt=1.0)
    assert tracker.azimuth == 0.0  # Should not move
    assert tracker.calculate_output() == 0.0  # No power consumption 