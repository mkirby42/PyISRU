"""
Tests for solar panel implementation.
"""
import math
import pytest
import numpy as np

from py_isru.lib.power_system import (
    SolarPanel,
    SolarPanelSpecification,
    PowerSystemStatus,
    ThermalPowerSystem
)


@pytest.fixture
def basic_panel_spec():
    """Basic solar panel specification"""
    return SolarPanelSpecification(
        area=1.0,                # 1 m²
        base_efficiency=0.2,     # 20% efficient
        max_temp=100.0,          # 100°C max
        min_temp=-100.0,         # -100°C min
        mass=10.0,               # 10 kg
        dust_tolerance=0.5       # 50% dust coverage before degraded
    )

def test_panel_inheritance(basic_panel_spec):
    """Test panel inherits from ThermalPowerSystem"""
    panel = SolarPanel(basic_panel_spec)
    assert isinstance(panel, ThermalPowerSystem)
    assert hasattr(panel, 'temperature')
    assert hasattr(panel, 'max_temp')
    assert hasattr(panel, 'min_temp')
    assert hasattr(panel, 'manage_thermal')
    
    # Check temperature conversion from °C to K
    assert panel.max_temp == basic_panel_spec.max_temp + 273.15
    assert panel.min_temp == basic_panel_spec.min_temp + 273.15

def test_panel_spec_validation():
    """Test panel specification validation"""
    # Valid spec should work
    spec = SolarPanelSpecification(
        area=1.0,
        base_efficiency=0.2,
        max_temp=100.0,
        min_temp=-100.0,
        mass=10.0,
        dust_tolerance=0.5
    )
    assert spec.area == 1.0
    assert spec.base_efficiency == 0.2
    
    # Test invalid specs
    with pytest.raises(ValueError):
        SolarPanelSpecification(
            area=-1.0,
            base_efficiency=0.2,
            max_temp=100.0,
            min_temp=-100.0,
            mass=10.0,
            dust_tolerance=0.5
        )
        
    with pytest.raises(ValueError):
        SolarPanelSpecification(
            area=1.0,
            base_efficiency=1.5,  # > 100%
            max_temp=100.0,
            min_temp=-100.0,
            mass=10.0,
            dust_tolerance=0.5
        )

def test_panel_initial_state(basic_panel_spec):
    """Test initial panel state"""
    panel = SolarPanel(basic_panel_spec)
    assert panel.status == PowerSystemStatus.ONLINE
    assert panel.dust_coverage == 0.0
    assert panel.incident_power == 0.0
    assert panel.angle_of_incidence == 0.0
    assert panel.temperature == 298.15  # Default from ThermalPowerSystem

def test_panel_power_calculation(basic_panel_spec):
    """Test panel power output calculation"""
    panel = SolarPanel(basic_panel_spec)
    
    # Update with standard test conditions
    panel.update_environment(
        incident_power=1000.0,  # 1 kW/m²
        temperature=25.0,       # 25°C
        angle_of_incidence=0.0, # Direct sunlight
        dust_added=0.0
    )
    
    # Power should be area * incident_power * efficiency
    expected_power = 1000.0 * 1.0 * 0.2
    assert panel.calculate_output() == pytest.approx(expected_power, rel=1e-10)
    
    # Test with angle
    panel.update_environment(
        incident_power=1000.0,
        temperature=25.0,
        angle_of_incidence=np.pi/4,  # 45 degrees
        dust_added=0.0
    )
    
    # Power should be reduced by cos(angle)
    expected_power = 1000.0 * 1.0 * 0.2 * np.cos(np.pi/4)
    assert panel.calculate_output() == pytest.approx(expected_power, rel=1e-10)

def test_panel_dust_effects(basic_panel_spec):
    """Test dust accumulation effects"""
    panel = SolarPanel(basic_panel_spec)
    
    # Set baseline conditions
    panel.update_environment(
        incident_power=1000.0,
        temperature=25.0,
        angle_of_incidence=0.0,
        dust_added=0.0
    )
    baseline_power = panel.calculate_output()
    
    # Add some dust
    panel.update_environment(
        incident_power=1000.0,
        temperature=25.0,
        angle_of_incidence=0.0,
        dust_added=0.2  # 20% coverage
    )
    
    # Power should be reduced by dust factor
    expected_power = baseline_power * 0.8  # 20% reduction
    assert panel.calculate_output() == pytest.approx(expected_power, rel=1e-10)
    
    # Add more dust to trigger degraded state
    panel.update_environment(
        incident_power=1000.0,
        temperature=25.0,
        angle_of_incidence=0.0,
        dust_added=0.4  # Total 60% coverage
    )
    assert panel.status == PowerSystemStatus.DEGRADED

def test_panel_thermal_management(basic_panel_spec):
    """Test panel thermal management"""
    panel = SolarPanel(basic_panel_spec)
    
    # Test normal temperature
    panel.update_environment(
        incident_power=1000.0,
        temperature=25.0,
        angle_of_incidence=0.0,
        dust_added=0.0
    )
    panel.step(1.0)
    assert panel.status == PowerSystemStatus.ONLINE
    
    # Test overheating
    panel.update_environment(
        incident_power=1000.0,
        temperature=150.0,  # Above max_temp
        angle_of_incidence=0.0,
        dust_added=0.0
    )
    panel.step(1.0)
    assert panel.status == PowerSystemStatus.FAULT
    assert "Temperature" in panel.fault_condition
    
    # Test overcooling
    panel.update_environment(
        incident_power=1000.0,
        temperature=-150.0,  # Below min_temp
        angle_of_incidence=0.0,
        dust_added=0.0
    )
    panel.step(1.0)
    assert panel.status == PowerSystemStatus.FAULT
    assert "Temperature" in panel.fault_condition
    
    # Test recovery
    panel.update_environment(
        incident_power=1000.0,
        temperature=25.0,
        angle_of_incidence=0.0,
        dust_added=0.0
    )
    panel.step(1.0)
    assert panel.status == PowerSystemStatus.ONLINE

def test_panel_cleaning(basic_panel_spec):
    """Test panel cleaning"""
    panel = SolarPanel(basic_panel_spec)
    
    # Add dust until degraded
    panel.update_environment(
        incident_power=1000.0,
        temperature=25.0,
        angle_of_incidence=0.0,
        dust_added=0.6
    )
    assert panel.status == PowerSystemStatus.DEGRADED
    
    # Clean panel
    panel.clean()
    assert panel.dust_coverage == 0.0
    assert panel.status == PowerSystemStatus.ONLINE

def test_panel_fault_handling(basic_panel_spec):
    """Test panel fault handling"""
    panel = SolarPanel(basic_panel_spec)
    
    # Force invalid angle
    panel.angle_of_incidence = float('inf')
    assert panel.calculate_output() == 0.0
    assert panel.status == PowerSystemStatus.FAULT
    assert panel.fault_condition is not None 