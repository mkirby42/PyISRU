"""
Tests for the power transmission system.
"""
import pytest

from py_isru.lib.power_system.base import PowerPriority, PowerSystemStatus
from py_isru.lib.power_system.transmission import (
    BusType,
    BusSpecification,
    PowerBus,
    TransmissionSystem
)

@pytest.fixture
def transmission_system():
    """Create a test transmission system"""
    return TransmissionSystem()

def test_bus_initialization(transmission_system):
    """Test that buses are initialized correctly"""
    assert len(transmission_system.buses) == 3
    assert 'MAIN' in transmission_system.buses
    assert 'CRITICAL' in transmission_system.buses
    assert 'SECONDARY' in transmission_system.buses
    
    assert transmission_system.buses['MAIN'].spec.type == BusType.MAIN
    assert transmission_system.buses['CRITICAL'].spec.type == BusType.CRITICAL
    assert transmission_system.buses['SECONDARY'].spec.type == BusType.SECONDARY

def test_add_load(transmission_system):
    """Test adding loads to buses"""
    # Add valid load
    assert transmission_system.add_load('MAIN', 'load1', 1000.0)
    assert transmission_system.buses['MAIN'].current_power == 1000.0
    
    # Add load exceeding capacity
    assert not transmission_system.add_load('MAIN', 'load2', 200_000.0)
    
    # Add to non-existent bus
    assert not transmission_system.add_load('NONEXISTENT', 'load3', 100.0)

def test_remove_load(transmission_system):
    """Test removing loads from buses"""
    transmission_system.add_load('MAIN', 'load1', 1000.0)
    transmission_system.add_load('MAIN', 'load2', 2000.0)
    
    transmission_system.remove_load('MAIN', 'load1')
    assert transmission_system.buses['MAIN'].current_power == 2000.0
    
    # Remove non-existent load
    transmission_system.remove_load('MAIN', 'nonexistent')
    assert transmission_system.buses['MAIN'].current_power == 2000.0

def test_bus_connections(transmission_system):
    """Test bus connection management"""
    assert transmission_system.connect_buses('MAIN', 'CRITICAL')
    assert 'CRITICAL' in transmission_system.bus_connections['MAIN']
    assert 'MAIN' in transmission_system.bus_connections['CRITICAL']
    
    # Test invalid connections
    assert not transmission_system.connect_buses('MAIN', 'MAIN')
    assert not transmission_system.connect_buses('MAIN', 'NONEXISTENT')
    
    transmission_system.disconnect_buses('MAIN', 'CRITICAL')
    assert 'CRITICAL' not in transmission_system.bus_connections['MAIN']

def test_power_calculation(transmission_system):
    """Test power calculations"""
    transmission_system.add_load('MAIN', 'load1', 1000.0)
    transmission_system.add_load('CRITICAL', 'load2', 2000.0)
    
    total_power = transmission_system.calculate_output()
    assert total_power > 3000.0  # Account for losses
    assert total_power < 3200.0  # Reasonable loss limit

def test_protection_system(transmission_system):
    """Test protection system operation"""
    # Test overcurrent protection
    transmission_system.add_load('MAIN', 'load1', 98_000.0)  # Just under max power
    transmission_system.step(1.0)
    assert transmission_system.status == PowerSystemStatus.FAULT
    
    # Test overvoltage protection with a fresh system
    system2 = TransmissionSystem()
    system2.voltage = 140.0  # Above 1.1 pu
    system2.step(1.0)  # Should trip on voltage without needing load
    assert system2.status == PowerSystemStatus.FAULT

def test_fault_isolation(transmission_system):
    """Test fault isolation functionality"""
    transmission_system.connect_buses('MAIN', 'CRITICAL')
    transmission_system.add_load('MAIN', 'load1', 1000.0)
    
    transmission_system.isolate_fault('MAIN')
    assert not transmission_system.buses['MAIN'].is_active
    assert transmission_system.buses['MAIN'].has_fault
    assert 'CRITICAL' not in transmission_system.bus_connections['MAIN']

def test_power_bus():
    """Test PowerBus class functionality"""
    spec = BusSpecification(
        type=BusType.MAIN,
        voltage=120.0,
        max_power=10000.0,
        priority=PowerPriority.HIGH
    )
    bus = PowerBus(spec)
    
    assert bus.add_load('load1', 1000.0)
    assert bus.current_power == 1000.0
    
    losses = bus.calculate_losses()
    assert losses > 0
    assert losses < 100.0  # Reasonable loss limit 