"""
Tests for solar array implementation.
"""
import numpy as np
import pytest

from py_isru.lib.power_system import (
    SolarArray,
    SolarArraySpecification,
    SolarPanelSpecification,
    TrackerSpecification,
    TrackingType,
    PowerSystemStatus,
    ThermalPowerSystem
)

@pytest.fixture
def basic_array_spec():
    """Basic solar array specification"""
    return SolarArraySpecification(
        n_panels=4,
        panel_spec=SolarPanelSpecification(
            area=1.0,                # 1 m²
            base_efficiency=0.2,     # 20% efficient
            max_temp=100.0,          # 100°C max
            min_temp=-100.0,         # -100°C min
            mass=10.0,               # 10 kg
            dust_tolerance=0.5       # 50% dust coverage before degraded
        ),
        tracker_spec=TrackerSpecification(
            type=TrackingType.DUAL_AXIS,
            power_consumption=10.0,  # 10W per tracker
            max_slew_rate=1.0       # 1 deg/s
        )
    )

def test_array_inheritance(basic_array_spec):
    """Test array inherits from ThermalPowerSystem"""
    array = SolarArray(basic_array_spec)
    assert isinstance(array, ThermalPowerSystem)
    assert hasattr(array, 'temperature')
    assert hasattr(array, 'max_temp')
    assert hasattr(array, 'min_temp')
    assert hasattr(array, 'manage_thermal')
    
    # Check temperature conversion from °C to K
    assert array.max_temp == basic_array_spec.panel_spec.max_temp + 273.15
    assert array.min_temp == basic_array_spec.panel_spec.min_temp + 273.15

def test_array_spec_validation():
    """Test array specification validation"""
    # Valid spec should work
    spec = SolarArraySpecification(
        n_panels=4,
        panel_spec=SolarPanelSpecification(
            area=1.0,
            base_efficiency=0.2,
            max_temp=100.0,
            min_temp=-100.0,
            mass=10.0,
            dust_tolerance=0.5
        )
    )
    assert spec.n_panels == 4
    
    # Test invalid specs
    with pytest.raises(ValueError):
        SolarArraySpecification(
            n_panels=0,  # Must be positive
            panel_spec=SolarPanelSpecification(
                area=1.0,
                base_efficiency=0.2,
                max_temp=100.0,
                min_temp=-100.0,
                mass=10.0,
                dust_tolerance=0.5
            )
        )

def test_array_initial_state(basic_array_spec):
    """Test initial array state"""
    array = SolarArray(basic_array_spec)
    assert array.status == PowerSystemStatus.ONLINE
    assert len(array.panels) == basic_array_spec.n_panels
    assert len(array.trackers) == basic_array_spec.n_panels
    assert array.temperature == 298.15  # Default from ThermalPowerSystem
    
    # Check all components
    for panel in array.panels:
        assert panel.status == PowerSystemStatus.ONLINE
        assert panel.dust_coverage == 0.0
        
    for tracker in array.trackers:
        assert tracker.status == PowerSystemStatus.ONLINE

def test_array_power_calculation(basic_array_spec):
    """Test array power output calculation"""
    array = SolarArray(basic_array_spec)
    
    # Update with standard test conditions
    array.update_environment(
        incident_power=1000.0,  # 1 kW/m²
        temperature=25.0,       # 25°C
        sun_azimuth=180.0,     # South
        sun_elevation=45.0,     # 45° elevation
        dust_added=0.0,
        dt=1.0
    )
    
    # Calculate expected power
    n_panels = basic_array_spec.n_panels
    panel_power = 1000.0 * 1.0 * 0.2  # incident_power * area * efficiency
    tracker_power = -10.0  # Each tracker consumes 10W
    expected_power = n_panels * panel_power + n_panels * tracker_power
    
    assert array.calculate_output() == pytest.approx(expected_power, rel=1e-10)

def test_array_thermal_management(basic_array_spec):
    """Test array thermal management"""
    array = SolarArray(basic_array_spec)
    
    # Test normal temperature
    array.update_environment(
        incident_power=1000.0,
        temperature=25.0,
        sun_azimuth=180.0,
        sun_elevation=45.0,
        dust_added=0.0,
        dt=1.0
    )
    array.step(1.0)
    assert array.status == PowerSystemStatus.ONLINE
    
    # Test overheating
    array.update_environment(
        incident_power=1000.0,
        temperature=150.0,  # Above max_temp
        sun_azimuth=180.0,
        sun_elevation=45.0,
        dust_added=0.0,
        dt=1.0
    )
    array.step(1.0)
    assert array.status == PowerSystemStatus.FAULT
    assert "Temperature" in array.fault_condition
    
    # Test overcooling
    array.update_environment(
        incident_power=1000.0,
        temperature=-150.0,  # Below min_temp
        sun_azimuth=180.0,
        sun_elevation=45.0,
        dust_added=0.0,
        dt=1.0
    )
    array.step(1.0)
    assert array.status == PowerSystemStatus.FAULT
    assert "Temperature" in array.fault_condition
    
    # Test recovery
    array.update_environment(
        incident_power=1000.0,
        temperature=25.0,
        sun_azimuth=180.0,
        sun_elevation=45.0,
        dust_added=0.0,
        dt=1.0
    )
    array.step(1.0)
    assert array.status == PowerSystemStatus.ONLINE

def test_array_dust_effects(basic_array_spec):
    """Test array dust accumulation effects"""
    array = SolarArray(basic_array_spec)
    
    # Set baseline conditions
    array.update_environment(
        incident_power=1000.0,
        temperature=25.0,
        sun_azimuth=180.0,
        sun_elevation=45.0,
        dust_added=0.0,
        dt=1.0
    )
    baseline_power = array.calculate_output()
    
    # Add dust to degrade performance
    array.update_environment(
        incident_power=1000.0,
        temperature=25.0,
        sun_azimuth=180.0,
        sun_elevation=45.0,
        dust_added=0.6,  # Above dust_tolerance
        dt=1.0
    )
    
    # Array should be degraded
    assert array.status == PowerSystemStatus.DEGRADED
    assert array.calculate_output() < baseline_power
    
    # Clean array
    array.clean()
    array.update_environment(
        incident_power=1000.0,
        temperature=25.0,
        sun_azimuth=180.0,
        sun_elevation=45.0,
        dust_added=0.0,
        dt=1.0
    )
    assert array.status == PowerSystemStatus.ONLINE
    assert array.calculate_output() == pytest.approx(baseline_power, rel=1e-10)

def test_array_component_faults(basic_array_spec):
    """Test array handling of component faults"""
    array = SolarArray(basic_array_spec)
    
    # Fault a panel
    array.panels[0].status = PowerSystemStatus.FAULT
    array._update_status()
    assert array.status == PowerSystemStatus.FAULT
    assert "components faulted" in array.fault_condition
    
    # Fault a tracker
    array.panels[0].status = PowerSystemStatus.ONLINE
    array.trackers[0].status = PowerSystemStatus.FAULT
    array._update_status()
    assert array.status == PowerSystemStatus.FAULT
    
    # Degrade multiple components
    array.trackers[0].status = PowerSystemStatus.ONLINE
    array.panels[0].status = PowerSystemStatus.DEGRADED
    array.panels[1].status = PowerSystemStatus.DEGRADED
    array._update_status()
    assert array.status == PowerSystemStatus.DEGRADED

def test_array_temperature_reporting(basic_array_spec):
    """Test array temperature reporting"""
    array = SolarArray(basic_array_spec)
    
    # Set temperature
    array.update_environment(
        incident_power=1000.0,
        temperature=25.0,
        sun_azimuth=180.0,
        sun_elevation=45.0,
        dust_added=0.0,
        dt=1.0
    )
    
    # Check temperature reporting
    temps = array.get_panel_temperatures()
    assert len(temps) == basic_array_spec.n_panels
    for temp in temps:
        assert temp == pytest.approx(25.0, rel=1e-10)  # Should be in °C 