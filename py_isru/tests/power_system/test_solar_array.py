"""
Tests for solar array implementation.
"""
import pytest
import numpy as np

from py_isru.lib.power_system.solar.array import (
    SolarArray,
    SolarArraySpecification,
    SolarPanelSpecification,
    TrackerSpecification,
    TrackingType,
    PowerSystemStatus
)

@pytest.fixture
def basic_panel_spec():
    """Basic solar panel specification"""
    return SolarPanelSpecification(
        area=2.0,              # 2 m²
        base_efficiency=0.20,  # 20% efficient
        max_temp=100.0,       # 100°C max
        min_temp=-100.0,      # -100°C min
        mass=10.0,            # 10 kg
        dust_tolerance=0.30    # 30% dust coverage before degraded
    )

@pytest.fixture
def basic_tracker_spec():
    """Basic tracker specification"""
    return TrackerSpecification(
        type=TrackingType.DUAL_AXIS,
        power_consumption=50.0,     # 50W when moving
        max_slew_rate=5.0,         # 5 deg/s
    )

@pytest.fixture
def basic_array_spec(basic_panel_spec, basic_tracker_spec):
    """Basic array specification"""
    return SolarArraySpecification(
        n_panels=4,
        panel_spec=basic_panel_spec,
        tracker_spec=basic_tracker_spec
    )

def test_array_spec_validation(basic_panel_spec, basic_tracker_spec):
    """Test array specification validation"""
    # Valid spec should work
    spec = SolarArraySpecification(
        n_panels=4,
        panel_spec=basic_panel_spec,
        tracker_spec=basic_tracker_spec
    )
    assert spec.n_panels == 4
    
    # Invalid specs should raise
    with pytest.raises(ValueError):
        SolarArraySpecification(
            n_panels=0,
            panel_spec=basic_panel_spec,
            tracker_spec=basic_tracker_spec
        )

def test_array_initial_state(basic_array_spec):
    """Test initial array state"""
    array = SolarArray(basic_array_spec)
    assert array.status == PowerSystemStatus.ONLINE
    assert len(array.panels) == basic_array_spec.n_panels
    assert len(array.trackers) == basic_array_spec.n_panels
    assert array.fault_condition is None

def test_array_basic_output(basic_array_spec):
    """Test basic power output calculation"""
    array = SolarArray(basic_array_spec)
    
    # Update with standard test conditions
    array.update_environment(
        incident_power=1000.0,  # 1000 W/m²
        temperature=25.0,       # 25°C
        sun_azimuth=0.0,       # Sun directly south
        sun_elevation=90.0,     # Sun directly overhead
        dust_added=0.0,         # Clean panels
        dt=1.0                  # 1 second step
    )
    
    # Let trackers complete movement (18 steps at 5 deg/s to reach 90°)
    for _ in range(18):
        array.update_environment(
            incident_power=1000.0,
            temperature=25.0,
            sun_azimuth=0.0,
            sun_elevation=90.0,
            dust_added=0.0,
            dt=1.0
        )
    
    # Expected: 4 panels * (1000 W/m² * 2 m² * 0.20 efficiency) = 1600W
    # No tracker power consumption when not moving
    assert np.isclose(array.calculate_output(), 1600.0, rtol=1e-10)

def test_array_tracking_power(basic_array_spec):
    """Test power consumption during tracking"""
    array = SolarArray(basic_array_spec)
    
    # Update with moving trackers
    array.update_environment(
        incident_power=1000.0,
        temperature=25.0,
        sun_azimuth=45.0,      # Requires movement
        sun_elevation=45.0,
        dust_added=0.0,
        dt=1.0
    )
    
    # Check power during movement
    # 1600W - (4 trackers * 50W) = 1400W
    assert np.isclose(array.calculate_output(), 1400.0, rtol=1e-10)
    
    # Let trackers complete movement (9 steps at 5 deg/s to reach 45°)
    for _ in range(9):
        array.update_environment(
            incident_power=1000.0,
            temperature=25.0,
            sun_azimuth=45.0,
            sun_elevation=45.0,
            dust_added=0.0,
            dt=1.0
        )
    
    # After movement, should have full power
    assert np.isclose(array.calculate_output(), 1600.0, rtol=1e-10)

def test_array_dust_impact(basic_array_spec):
    """Test dust impact on array"""
    array = SolarArray(basic_array_spec)
    
    # Start clean
    array.update_environment(
        incident_power=1000.0,
        temperature=25.0,
        sun_azimuth=0.0,
        sun_elevation=90.0,
        dust_added=0.0,
        dt=1.0
    )
    
    # Let trackers complete movement (18 steps at 5 deg/s to reach 90°)
    for _ in range(18):
        array.update_environment(
            incident_power=1000.0,
            temperature=25.0,
            sun_azimuth=0.0,
            sun_elevation=90.0,
            dust_added=0.0,
            dt=1.0
        )
    
    initial_power = array.calculate_output()
    
    # Add dust
    array.update_environment(
        incident_power=1000.0,
        temperature=25.0,
        sun_azimuth=0.0,
        sun_elevation=90.0,
        dust_added=0.20,  # 20% coverage
        dt=1.0
    )
    
    # Power should be reduced by 20%
    assert np.isclose(array.calculate_output(), initial_power * 0.8, rtol=1e-10)
    assert array.status == PowerSystemStatus.ONLINE  # Still under tolerance
    
    # Add more dust to exceed tolerance
    array.update_environment(
        incident_power=1000.0,
        temperature=25.0,
        sun_azimuth=0.0,
        sun_elevation=90.0,
        dust_added=0.20,  # Another 20%
        dt=1.0
    )
    
    # Array should be degraded
    assert array.status == PowerSystemStatus.DEGRADED
    
    # Clean array
    array.clean()
    array.update_environment(
        incident_power=1000.0,
        temperature=25.0,
        sun_azimuth=0.0,
        sun_elevation=90.0,
        dust_added=0.0,
        dt=1.0
    )
    assert np.isclose(array.calculate_output(), initial_power, rtol=1e-10)
    assert array.status == PowerSystemStatus.ONLINE

def test_array_temperature_protection(basic_array_spec):
    """Test temperature protection"""
    array = SolarArray(basic_array_spec)
    
    # Start at normal temperature
    array.update_environment(
        incident_power=1000.0,
        temperature=25.0,
        sun_azimuth=0.0,
        sun_elevation=90.0,
        dust_added=0.0,
        dt=1.0
    )
    initial_power = array.calculate_output()
    
    # Heat beyond limits
    array.update_environment(
        incident_power=1000.0,
        temperature=150.0,  # Above max temp
        sun_azimuth=0.0,
        sun_elevation=90.0,
        dust_added=0.0,
        dt=1.0
    )
    
    # Array should fault
    assert array.status == PowerSystemStatus.FAULT
    assert array.calculate_output() == 0.0
    
    # Return to normal temperature
    array.update_environment(
        incident_power=1000.0,
        temperature=25.0,
        sun_azimuth=0.0,
        sun_elevation=90.0,
        dust_added=0.0,
        dt=1.0
    )
    
    # Should recover
    assert array.status == PowerSystemStatus.ONLINE
    assert np.isclose(array.calculate_output(), initial_power, rtol=1e-10)

def test_array_fault_handling(basic_array_spec):
    """Test fault handling"""
    array = SolarArray(basic_array_spec)
    
    # Invalid time step
    with pytest.raises(ValueError):
        array.update_environment(
            incident_power=1000.0,
            temperature=25.0,
            sun_azimuth=0.0,
            sun_elevation=90.0,
            dust_added=0.0,
            dt=-1.0
        )
    
    # Force tracker fault
    array.trackers[0].status = PowerSystemStatus.FAULT
    array.update_environment(
        incident_power=1000.0,
        temperature=25.0,
        sun_azimuth=0.0,
        sun_elevation=90.0,
        dust_added=0.0,
        dt=1.0
    )
    
    # Array should fault
    assert array.status == PowerSystemStatus.FAULT
    assert "1 components faulted" in array.fault_condition 