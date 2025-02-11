"""
Tests for storage tank implementation.
"""
import pytest
import numpy as np
from scipy import constants

from py_isru.lib.reactor import ResourceType
from py_isru.lib.storage_tank import StorageTank, TankSpecification, PhaseType
from py_isru.lib.thermodynamics import ThermodynamicState

@pytest.fixture
def basic_storage_tank():
    """Create a basic storage tank for testing"""
    spec = TankSpecification(
        volume=1.0,  # m³
        max_pressure=10e6,  # Pa
        max_temperature=500.0,  # K
        material="Stainless Steel 316",
        wall_thickness=0.01,  # m
        thermal_conductivity=16.3,  # W/(m⋅K)
        safety_factor=1.5
    )
    
    initial_state = ThermodynamicState.from_temperature_pressure(298.15, 101325.0)
    
    return StorageTank(spec, ResourceType.H2, initial_state)

def test_tank_initialization(basic_storage_tank):
    """Test tank initialization"""
    tank = basic_storage_tank
    assert tank.moles == 0.0
    assert tank.leak_rate == 0.0
    assert tank.phase == PhaseType.GAS
    assert tank.state.temperature == 298.15
    assert tank.state.pressure == 101325.0

def test_phase_determination():
    """Test phase determination for different conditions"""
    spec = TankSpecification(
        volume=1.0, max_pressure=20e6, max_temperature=700.0,
        material="Stainless Steel 316", wall_thickness=0.01,
        thermal_conductivity=16.3, safety_factor=1.5
    )
    
    # Test CO₂ phase transitions
    T_crit, P_crit = StorageTank.CRITICAL_POINTS[ResourceType.CO2]
    
    # Subcritical gas
    state_gas = ThermodynamicState.from_temperature_pressure(T_crit - 10, P_crit / 2)
    tank_gas = StorageTank(spec, ResourceType.CO2, state_gas)
    assert tank_gas.phase == PhaseType.GAS
    
    # Supercritical fluid
    state_super = ThermodynamicState.from_temperature_pressure(T_crit + 10, P_crit * 2)
    tank_super = StorageTank(spec, ResourceType.CO2, state_super)
    assert tank_super.phase == PhaseType.SUPERCRITICAL
    
    # Test water phase
    state_liquid = ThermodynamicState.from_temperature_pressure(353.15, 101325.0)
    tank_water = StorageTank(spec, ResourceType.H2O, state_liquid)
    assert tank_water.phase == PhaseType.LIQUID

def test_compressibility_factor():
    """Test gas compressibility calculations"""
    spec = TankSpecification(
        volume=1.0, max_pressure=20e6, max_temperature=700.0,
        material="Stainless Steel 316", wall_thickness=0.01,
        thermal_conductivity=16.3, safety_factor=1.5
    )
    
    state = ThermodynamicState.from_temperature_pressure(298.15, 10e6)  # High pressure
    tank = StorageTank(spec, ResourceType.H2, state)
    tank.moles = 100.0
    
    Z = tank._calculate_compressibility()
    
    # At high pressure, Z should deviate from 1.0
    assert Z != 1.0
    # Z should be greater than 1.0 for H₂ (repulsive forces dominate)
    assert Z > 1.0

def test_density_calculations(basic_storage_tank):
    """Test density calculations for different phases"""
    tank = basic_storage_tank
    
    # Test gas phase density
    tank.moles = 10.0
    gas_density = tank.calculate_density()
    
    # Compare with ideal gas law (should be close at low pressure)
    ideal_density = (tank.state.pressure * tank.MOLAR_MASSES[ResourceType.H2] / 
                    (constants.R * tank.state.temperature))
    assert np.isclose(gas_density, ideal_density, rtol=1e-2)
    
    # Test liquid phase density
    spec = TankSpecification(
        volume=1.0, max_pressure=20e6, max_temperature=700.0,
        material="Stainless Steel 316", wall_thickness=0.01,
        thermal_conductivity=16.3, safety_factor=1.5
    )
    state = ThermodynamicState.from_temperature_pressure(298.15, 101325.0)
    water_tank = StorageTank(spec, ResourceType.H2O, state)
    
    assert np.isclose(water_tank.calculate_density(), 1000.0, rtol=1e-2)

def test_add_remove_resource(basic_storage_tank):
    """Test adding and removing resources"""
    tank = basic_storage_tank
    
    # Add resource
    added = tank.add_resource(10.0, 298.15)
    assert added == 10.0
    assert tank.moles == 10.0
    
    # Try to add beyond pressure limit
    large_amount = tank.spec.max_pressure * tank.spec.volume / \
                  (constants.R * tank.state.temperature)
    added = tank.add_resource(large_amount, 298.15)
    assert added == 0.0  # Should not add any
    
    # Remove resource
    removed = tank.remove_resource(5.0)
    assert removed == 5.0
    assert tank.moles == 5.0
    
    # Try to remove more than available
    removed = tank.remove_resource(10.0)
    assert removed == 5.0
    assert tank.moles == 0.0

def test_thermal_behavior(basic_storage_tank):
    """Test thermal behavior and heat transfer"""
    tank = basic_storage_tank
    
    # Add some gas
    tank.add_resource(10.0, 350.0)  # Add hot gas
    initial_temp = tank.state.temperature
    
    # Let it cool
    for _ in range(100):
        tank.step(1.0)
        if abs(tank.state.temperature - 210.0) < 1.0:  # Mars ambient temp
            break
    
    assert tank.state.temperature < initial_temp
    
    # Check pressure change with temperature
    assert tank.state.pressure < tank.moles * constants.R * initial_temp / tank.spec.volume

def test_leaks(basic_storage_tank):
    """Test leak behavior"""
    tank = basic_storage_tank
    
    # Add gas and set leak rate
    tank.add_resource(10.0, 298.15)
    tank.leak_rate = 0.1  # mol/s
    
    # Run for 10 seconds
    tank.step(10.0)
    
    assert tank.moles == pytest.approx(9.0, rel=1e-10)

def test_mixing(basic_storage_tank):
    """Test temperature mixing when adding resources"""
    tank = basic_storage_tank
    
    # Add cold gas
    tank.add_resource(5.0, 250.0)
    cold_temp = tank.state.temperature
    
    # Add hot gas
    tank.add_resource(5.0, 350.0)
    
    # Final temperature should be between cold and hot
    assert 250.0 < tank.state.temperature < 350.0
    
    # Should be closer to average (weighted by amount)
    expected_temp = (5.0 * 250.0 + 5.0 * 350.0) / 10.0
    assert np.isclose(tank.state.temperature, expected_temp, rtol=1e-10)

def test_edge_cases(basic_storage_tank):
    """Test edge cases and error conditions"""
    tank = basic_storage_tank
    
    # Test adding negative amount
    assert tank.add_resource(-1.0, 298.15) == 0.0
    
    # Test removing negative amount
    assert tank.remove_resource(-1.0) == 0.0
    
    # Test adding with invalid temperature
    with pytest.raises(ValueError):
        tank.add_resource(1.0, -1.0)
    
    # Test behavior with zero moles
    assert tank.calculate_density() == 0.0
    assert tank.calculate_available_volume() == tank.spec.volume 