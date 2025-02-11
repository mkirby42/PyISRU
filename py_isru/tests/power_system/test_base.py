"""
Tests for base power system functionality.
"""
import numpy as np
import pytest

from py_isru.lib.power_system import (
    PowerSystem,
    PowerSystemStatus,
    PowerPriority,
    PowerQuality,
    ThermalManagement,
    LoadProfile,
)

class TestPowerSystem(PowerSystem):
    """Test implementation of PowerSystem"""
    def calculate_output(self) -> float:
        return self.current_output or 1000.0  # Allow output override for testing

@pytest.fixture
def basic_power_system():
    """Basic power system for testing"""
    return TestPowerSystem()

def test_load_management(basic_power_system):
    """Test load management functionality"""
    system = basic_power_system
    
    # Add loads of different priorities
    critical_load = LoadProfile(
        priority=PowerPriority.CRITICAL,
        min_power=100.0,
        nominal_power=200.0,
        max_power=300.0
    )
    high_load = LoadProfile(
        priority=PowerPriority.HIGH,
        min_power=200.0,
        nominal_power=300.0,
        max_power=400.0
    )
    low_load = LoadProfile(
        priority=PowerPriority.LOW,
        min_power=300.0,
        nominal_power=400.0,
        max_power=500.0
    )
    
    # Add loads
    system.add_load("critical", critical_load)
    system.add_load("high", high_load)
    system.add_load("low", low_load)
    
    # Activate all loads
    assert system.activate_load("critical")
    assert system.activate_load("high")
    assert system.activate_load("low")
    
    print("\nBefore load shedding:")
    print(f"Available power: {system.calculate_output()}")
    print(f"Active loads: {system.active_loads}")
    print(f"Load powers: {system.load_power}")
    
    # Reduce available power to force load shedding
    system.current_output = 400.0  # Only enough for critical + high
    
    print("\nAfter reducing power:")
    print(f"Available power: {system.calculate_output()}")
    print(f"Total load power: {sum(system.load_power.values())}")
    
    # Test load shedding
    system.perform_load_shedding()
    
    print("\nAfter load shedding:")
    print(f"Active loads: {system.active_loads}")
    print(f"Load powers: {system.load_power}")
    print(f"Total load power: {sum(system.load_power.values())}")
    
    # Critical load should remain active
    assert system.active_loads["critical"]
    assert system.load_power["critical"] > 0
    
    # Lower priority loads should be shed
    assert not system.active_loads["low"]
    assert system.load_power["low"] == 0.0

def test_thermal_management(basic_power_system):
    """Test thermal management functionality"""
    system = basic_power_system
    
    # Test overheating
    system.temperature = system.thermal_management.max_temp + 10.0
    system.manage_thermal(1.0)
    
    # Should activate cooling
    assert system.thermal_power < 0
    assert abs(system.thermal_power) == pytest.approx(
        system.thermal_management.cooling_power * 10.0,
        rel=0.01
    )
    
    # Test overcooling
    system.temperature = system.thermal_management.min_temp - 10.0
    system.manage_thermal(1.0)
    
    # Should activate heating
    assert system.thermal_power > 0
    assert system.thermal_power == pytest.approx(
        system.thermal_management.heating_power * 10.0,
        rel=0.01
    )
    
    # Test nominal temperature
    system.temperature = (
        system.thermal_management.min_temp + 
        system.thermal_management.max_temp
    ) / 2.0
    system.manage_thermal(1.0)
    
    # Should not need thermal control
    assert system.thermal_power == 0.0

def test_power_quality(basic_power_system):
    """Test power quality monitoring"""
    system = basic_power_system
    
    # Test nominal conditions
    assert system.check_power_quality()
    
    # Test voltage deviation
    system.current_voltage = (
        system.power_quality.voltage_nominal * 
        (1.0 + 2.0 * system.power_quality.voltage_tolerance)
    )
    assert not system.check_power_quality()
    
    # Test frequency deviation
    system.current_voltage = system.power_quality.voltage_nominal
    system.current_frequency = system.power_quality.frequency_nominal * 1.5
    assert not system.check_power_quality()
    
    # Test THD
    system.current_frequency = system.power_quality.frequency_nominal
    system.current_thd = system.power_quality.thd_limit * 1.5
    assert not system.check_power_quality()

def test_emergency_mode(basic_power_system):
    """Test emergency mode transitions"""
    system = basic_power_system
    
    # Store original thermal values
    original_cooling = system._base_thermal.cooling_power
    original_heating = system._base_thermal.heating_power
    
    # Add loads of different priorities
    system.add_load("critical", LoadProfile(
        priority=PowerPriority.CRITICAL,
        min_power=100.0,
        nominal_power=200.0,
        max_power=300.0
    ))
    system.add_load("low", LoadProfile(
        priority=PowerPriority.LOW,
        min_power=100.0,
        nominal_power=200.0,
        max_power=300.0
    ))
    
    # Activate all loads
    system.activate_load("critical")
    system.activate_load("low")
    
    # Enter emergency mode
    system.enter_emergency_mode()
    assert system.status == PowerSystemStatus.DEGRADED
    
    # Check load shedding
    assert system.active_loads["critical"]  # Critical load should remain
    assert not system.active_loads["low"]  # Low priority load should be shed
    
    # Check thermal management reduction
    assert system.thermal_management.cooling_power == original_cooling * 0.5
    assert system.thermal_management.heating_power == original_heating * 0.5
    
    # Exit emergency mode
    system.exit_emergency_mode()
    assert system.status == PowerSystemStatus.ONLINE
    
    # Check thermal management restoration
    assert system.thermal_management.cooling_power == original_cooling
    assert system.thermal_management.heating_power == original_heating

def test_step_function(basic_power_system):
    """Test step function behavior"""
    system = basic_power_system
    
    # Add a load
    system.add_load("test", LoadProfile(
        priority=PowerPriority.HIGH,
        min_power=100.0,
        nominal_power=200.0,
        max_power=300.0
    ))
    system.activate_load("test")
    
    # Force power quality issue
    system.current_thd = system.power_quality.thd_limit * 2.0
    
    # Step should trigger emergency mode
    system.step(1.0)
    assert system.status == PowerSystemStatus.DEGRADED
    
    # Fix power quality
    system.current_thd = 0.0
    
    # Step should exit emergency mode
    system.step(1.0)
    assert system.status == PowerSystemStatus.ONLINE

def test_available_power(basic_power_system):
    """Test available power calculation"""
    system = basic_power_system
    
    # No loads or thermal power
    assert system.calculate_available_power() == 1000.0
    
    # Add thermal load
    system.thermal_power = 200.0
    assert system.calculate_available_power() == 800.0
    
    # Add power load
    system.add_load("test", LoadProfile(
        priority=PowerPriority.HIGH,
        min_power=300.0,
        nominal_power=400.0,
        max_power=500.0
    ))
    system.activate_load("test")
    
    # Available power should account for both thermal and load power
    assert system.calculate_available_power() == 500.0

def test_load_activation_limits(basic_power_system):
    """Test load activation with power limits"""
    system = basic_power_system
    
    # Add load requiring more power than available
    system.add_load("heavy", LoadProfile(
        priority=PowerPriority.HIGH,
        min_power=2000.0,  # More than system output
        nominal_power=2500.0,
        max_power=3000.0
    ))
    
    # Should fail to activate
    assert not system.activate_load("heavy")
    assert not system.active_loads.get("heavy", False)
    
    # Add critical load requiring more power than available
    system.add_load("critical_heavy", LoadProfile(
        priority=PowerPriority.CRITICAL,
        min_power=2000.0,
        nominal_power=2500.0,
        max_power=3000.0
    ))
    
    # Should activate in emergency mode with reduced power
    assert system.activate_load("critical_heavy")
    assert system.active_loads["critical_heavy"]
    assert system.load_power["critical_heavy"] == 1000.0  # Limited to available power
    assert system.status == PowerSystemStatus.DEGRADED  # Should be in emergency mode 