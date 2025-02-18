"""
Tests for base power system functionality.
"""
import pytest
import numpy as np

from py_isru.lib.power_system.base import (
    PowerSystem,
    PowerSystemStatus,
    ThermalPowerSystem,
    StoragePowerSystem
)

class TestPowerSystem(PowerSystem):
    """Test implementation of PowerSystem"""
    def __init__(self, output: float = 1000.0):
        super().__init__()
        self._output = output
        
    def calculate_output(self) -> float:
        return self._output

class TestThermalSystem(ThermalPowerSystem):
    """Test implementation of ThermalPowerSystem"""
    def __init__(self):
        super().__init__()
        self.thermal_power = 0.0
        
    def calculate_output(self) -> float:
        return 1000.0
        
    def manage_thermal(self, dt: float) -> None:
        if self.temperature > self.max_temp:
            self.thermal_power = -100.0  # Cooling
        elif self.temperature < self.min_temp:
            self.thermal_power = 100.0   # Heating
        else:
            self.thermal_power = 0.0

class TestStorageSystem(StoragePowerSystem):
    """Test implementation of StoragePowerSystem"""
    def __init__(self):
        super().__init__()
        self.energy = 0.0
        self.max_energy = 1000.0
        
    def calculate_output(self) -> float:
        return 1000.0 if self.energy > 0 else 0.0
        
    def update(self, power: float, dt: float) -> float:
        super().update(power, dt)
        energy_change = power * dt / 3600.0  # W*s to Wh
        new_energy = self.energy + energy_change
        
        if new_energy > self.max_energy:
            power = (self.max_energy - self.energy) * 3600.0 / dt
        elif new_energy < 0:
            power = -self.energy * 3600.0 / dt
            
        self.energy += power * dt / 3600.0
        self.charging = power > 0
        return power

@pytest.fixture
def basic_power_system():
    """Basic power system for testing"""
    return TestPowerSystem()

@pytest.fixture
def thermal_system():
    """Thermal power system for testing"""
    return TestThermalSystem()

@pytest.fixture
def storage_system():
    """Storage power system for testing"""
    return TestStorageSystem()

def test_power_system_initialization(basic_power_system):
    """Test basic power system initialization"""
    assert basic_power_system.status == PowerSystemStatus.OFFLINE
    assert basic_power_system.fault_condition is None
    assert basic_power_system.calculate_output() == 1000.0

def test_power_system_step(basic_power_system):
    """Test power system step function"""
    # Valid step
    basic_power_system.step(1.0)
    
    # Invalid step
    with pytest.raises(ValueError):
        basic_power_system.step(0.0)
    with pytest.raises(ValueError):
        basic_power_system.step(-1.0)

def test_thermal_system(thermal_system):
    """Test thermal power system functionality"""
    # Test overheating
    thermal_system.temperature = thermal_system.max_temp + 10.0
    thermal_system.step(1.0)
    assert thermal_system.thermal_power < 0
    
    # Test overcooling
    thermal_system.temperature = thermal_system.min_temp - 10.0
    thermal_system.step(1.0)
    assert thermal_system.thermal_power > 0
    
    # Test nominal temperature
    thermal_system.temperature = (thermal_system.max_temp + thermal_system.min_temp) / 2.0
    thermal_system.step(1.0)
    assert thermal_system.thermal_power == 0.0

def test_storage_system(storage_system):
    """Test storage power system functionality"""
    # Test charging
    actual_power = storage_system.update(100.0, 3600.0)  # 100W for 1 hour
    assert actual_power == 100.0
    assert storage_system.charging
    assert storage_system.energy == 100.0
    
    # Test overcharging
    storage_system.energy = storage_system.max_energy - 10.0
    actual_power = storage_system.update(100.0, 3600.0)
    assert actual_power == 10.0  # Limited to remaining capacity
    assert storage_system.energy == storage_system.max_energy
    
    # Test discharging
    actual_power = storage_system.update(-200.0, 3600.0)
    assert actual_power == -200.0
    assert not storage_system.charging
    assert storage_system.energy == 800.0
    
    # Test over-discharging
    storage_system.energy = 50.0
    actual_power = storage_system.update(-100.0, 3600.0)
    assert actual_power == -50.0  # Limited to remaining energy
    assert storage_system.energy == 0.0
    
    # Test invalid time step
    with pytest.raises(ValueError):
        storage_system.update(100.0, 0.0)
    with pytest.raises(ValueError):
        storage_system.update(100.0, -1.0) 