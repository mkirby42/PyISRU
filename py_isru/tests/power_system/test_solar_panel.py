"""
Tests for solar panel implementation.
"""
import math
import pytest
import numpy as np

from py_isru.lib.power_system.solar.panel import SolarPanel, SolarPanelSpecification
from py_isru.lib.power_system.base import PowerSystemStatus


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

def test_panel_spec_validation():
    """Test panel specification validation"""
    # Valid spec should work
    spec = SolarPanelSpecification(
        area=2.0,
        base_efficiency=0.20,
        max_temp=100.0,
        min_temp=-100.0,
        mass=10.0,
        dust_tolerance=0.30
    )
    assert spec.area == 2.0
    assert spec.base_efficiency == 0.20
    
    # Invalid specs should raise
    with pytest.raises(ValueError):
        SolarPanelSpecification(
            area=-1.0,
            base_efficiency=0.20,
            max_temp=100.0,
            min_temp=-100.0,
            mass=10.0,
            dust_tolerance=0.30
        )
    
    with pytest.raises(ValueError):
        SolarPanelSpecification(
            area=2.0,
            base_efficiency=1.5,  # Over 100%
            max_temp=100.0,
            min_temp=-100.0,
            mass=10.0,
            dust_tolerance=0.30
        )

def test_panel_initial_state(basic_panel_spec):
    """Test initial panel state"""
    panel = SolarPanel(basic_panel_spec)
    assert panel.status == PowerSystemStatus.ONLINE
    assert panel.temperature == 20.0
    assert panel.dust_coverage == 0.0
    assert panel.incident_power == 0.0
    assert panel.angle_of_incidence == 0.0
    assert panel.fault_condition is None

def test_panel_basic_output(basic_panel_spec):
    """Test basic power output calculation"""
    panel = SolarPanel(basic_panel_spec)
    
    # Update with standard test conditions
    panel.update_environment(
        incident_power=1000.0,  # 1000 W/m²
        temperature=25.0,       # 25°C
        angle_of_incidence=0.0, # Direct sunlight
        dust_added=0.0          # Clean panel
    )
    
    # Expected: 1000 W/m² * 2 m² * 0.20 efficiency = 400W
    assert np.isclose(panel.calculate_output(), 400.0, rtol=1e-10)
    
    # Test with 45° angle
    panel.update_environment(
        incident_power=1000.0,
        temperature=25.0,
        angle_of_incidence=math.pi/4,  # 45°
        dust_added=0.0
    )
    
    # Expected: 400W * cos(45°) ≈ 282.84W
    assert np.isclose(panel.calculate_output(), 400.0 * math.cos(math.pi/4), rtol=1e-10)

def test_panel_dust_impact(basic_panel_spec):
    """Test dust impact on power output"""
    panel = SolarPanel(basic_panel_spec)
    
    # Set standard conditions
    panel.update_environment(
        incident_power=1000.0,
        temperature=25.0,
        angle_of_incidence=0.0,
        dust_added=0.0
    )
    initial_power = panel.calculate_output()
    
    # Add 20% dust
    panel.update_environment(
        incident_power=1000.0,
        temperature=25.0,
        angle_of_incidence=0.0,
        dust_added=0.20
    )
    
    # Power should be reduced by 20%
    assert np.isclose(panel.calculate_output(), initial_power * 0.8, rtol=1e-10)
    assert panel.status == PowerSystemStatus.ONLINE  # Still under tolerance
    
    # Add more dust to exceed tolerance
    panel.update_environment(
        incident_power=1000.0,
        temperature=25.0,
        angle_of_incidence=0.0,
        dust_added=0.20
    )
    
    # Should be in degraded state
    assert panel.status == PowerSystemStatus.DEGRADED
    
    # Clean panel
    panel.clean()
    assert panel.dust_coverage == 0.0
    assert panel.status == PowerSystemStatus.ONLINE
    assert np.isclose(panel.calculate_output(), initial_power, rtol=1e-10)

def test_panel_temperature_limits(basic_panel_spec):
    """Test temperature protection"""
    panel = SolarPanel(basic_panel_spec)
    
    # Set standard conditions
    panel.update_environment(
        incident_power=1000.0,
        temperature=25.0,
        angle_of_incidence=0.0,
        dust_added=0.0
    )
    initial_power = panel.calculate_output()
    
    # Test high temperature
    panel.update_environment(
        incident_power=1000.0,
        temperature=150.0,  # Above max
        angle_of_incidence=0.0,
        dust_added=0.0
    )
    assert panel.calculate_output() == 0.0
    assert panel.status == PowerSystemStatus.FAULT
    assert "Temperature" in panel.fault_condition
    
    # Return to normal
    panel.update_environment(
        incident_power=1000.0,
        temperature=25.0,
        angle_of_incidence=0.0,
        dust_added=0.0
    )
    assert np.isclose(panel.calculate_output(), initial_power, rtol=1e-10)
    assert panel.status == PowerSystemStatus.ONLINE
    
    # Test low temperature
    panel.update_environment(
        incident_power=1000.0,
        temperature=-150.0,  # Below min
        angle_of_incidence=0.0,
        dust_added=0.0
    )
    assert panel.calculate_output() == 0.0
    assert panel.status == PowerSystemStatus.FAULT
    assert "Temperature" in panel.fault_condition

def test_panel_input_validation(basic_panel_spec):
    """Test input validation"""
    panel = SolarPanel(basic_panel_spec)
    
    # Test negative power
    panel.update_environment(
        incident_power=-1000.0,
        temperature=25.0,
        angle_of_incidence=0.0,
        dust_added=0.0
    )
    assert panel.incident_power == 0.0  # Should clamp to zero
    
    # Test excessive dust
    panel.update_environment(
        incident_power=1000.0,
        temperature=25.0,
        angle_of_incidence=0.0,
        dust_added=2.0  # Over 100%
    )
    assert panel.dust_coverage == 1.0  # Should clamp to one 