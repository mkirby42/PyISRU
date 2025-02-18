"""
Tests for battery implementation.
"""
import pytest

from py_isru.lib.power_system import StoragePowerSystem, PowerSystemStatus
from py_isru.lib.power_system.battery import Battery, BatterySpecification

@pytest.fixture
def basic_battery():
    """Basic battery fixture"""
    return Battery(BatterySpecification(
        capacity_wh=1000.0,  # 1 kWh
        max_power=500.0,     # 500 W
    ))

def test_battery_spec_validation():
    """Test battery specification validation"""
    # Valid spec should work
    spec = BatterySpecification(capacity_wh=1000.0, max_power=500.0)
    assert spec.capacity_wh == 1000.0
    assert spec.max_power == 500.0
    
    # Invalid specs should raise
    with pytest.raises(ValueError):
        BatterySpecification(capacity_wh=-1000.0, max_power=500.0)
    with pytest.raises(ValueError):
        BatterySpecification(capacity_wh=1000.0, max_power=-500.0)

def test_battery_initial_state(basic_battery):
    """Test initial battery state"""
    assert basic_battery.status == PowerSystemStatus.ONLINE
    assert basic_battery.energy_wh == 0.0
    assert basic_battery.state_of_charge == 0.0
    assert not basic_battery.charging  # From StoragePowerSystem

def test_battery_charging(basic_battery):
    """Test battery charging"""
    # Charge for 1 hour at max power
    actual_power = basic_battery.update(500.0, 3600.0)
    assert actual_power == 500.0
    assert basic_battery.energy_wh == 500.0
    assert basic_battery.state_of_charge == 0.5
    assert basic_battery.charging  # From StoragePowerSystem
    
    # Try to charge beyond capacity
    actual_power = basic_battery.update(500.0, 3600.0)
    assert actual_power == 500.0  # Should use full power since we have exactly enough room
    assert basic_battery.energy_wh == 1000.0
    assert basic_battery.state_of_charge == 1.0
    assert basic_battery.charging

    # Now try to charge when already full
    actual_power = basic_battery.update(500.0, 3600.0)
    assert actual_power == 0.0  # No room left, so no power used
    assert basic_battery.energy_wh == 1000.0
    assert basic_battery.state_of_charge == 1.0
    assert not basic_battery.charging  # No power flow

def test_battery_discharging(basic_battery):
    """Test battery discharging"""
    # First charge fully
    basic_battery.update(500.0, 7200.0)  # Charge for 2 hours
    assert basic_battery.state_of_charge == 1.0
    assert basic_battery.charging
    
    # Discharge for 1 hour at max power
    actual_power = basic_battery.update(-500.0, 3600.0)
    assert actual_power == -500.0
    assert basic_battery.energy_wh == 500.0
    assert basic_battery.state_of_charge == 0.5
    assert not basic_battery.charging
    
    # Try to discharge beyond empty
    actual_power = basic_battery.update(-500.0, 3600.0)
    assert actual_power == -500.0
    actual_power = basic_battery.update(-500.0, 3600.0)
    assert actual_power > -500.0  # Should be limited
    assert basic_battery.energy_wh == 0.0
    assert basic_battery.state_of_charge == 0.0
    assert not basic_battery.charging

def test_battery_power_limits(basic_battery):
    """Test power limits are enforced"""
    # Try to charge at higher than max power
    actual_power = basic_battery.update(1000.0, 3600.0)
    assert actual_power == 500.0  # Limited to max
    assert basic_battery.charging
    
    # Charge fully then try to discharge at higher than max power
    basic_battery.update(500.0, 7200.0)
    actual_power = basic_battery.update(-1000.0, 3600.0)
    assert actual_power == -500.0  # Limited to max
    assert not basic_battery.charging

def test_battery_timestep_validation(basic_battery):
    """Test timestep validation from StoragePowerSystem"""
    with pytest.raises(ValueError):
        basic_battery.update(500.0, 0.0)
    with pytest.raises(ValueError):
        basic_battery.update(500.0, -1.0)

def test_battery_output_calculation(basic_battery):
    """Test power output calculation"""
    # Empty battery
    assert basic_battery.calculate_output() == 0.0
    
    # Partially charged
    basic_battery.update(500.0, 3600.0)
    assert basic_battery.calculate_output() == 500.0
    
    # Faulted battery
    basic_battery.status = PowerSystemStatus.FAULT
    assert basic_battery.calculate_output() == 0.0

def test_battery_fault_handling(basic_battery):
    """Test fault handling"""
    # Invalid power input
    actual_power = basic_battery.update("not a number", 3600.0)
    assert actual_power == 0.0
    assert basic_battery.status == PowerSystemStatus.FAULT
    
    # Invalid power type
    actual_power = basic_battery.update(None, 3600.0)
    assert actual_power == 0.0
    assert basic_battery.status == PowerSystemStatus.FAULT 