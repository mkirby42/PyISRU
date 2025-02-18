"""
Tests for storage tank implementation.
"""
import pytest
from math import isclose
import logging

from py_isru.lib.reactor import ResourceType
from py_isru.lib.storage_tank import StorageTank, TankSpecification, PhaseType
from py_isru.lib.thermodynamics import ThermodynamicState

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Fixtures for StorageTank
# ---------------------------------------------------------------------------

@pytest.fixture
def water_tank_spec():
    """Fixture for a water storage tank specification."""
    return TankSpecification(
        volume_m3=1.0,
        max_pressure_Pa=2e5,
        max_temperature_K=350,
        material="Stainless Steel 316",
        wall_thickness_m=0.01,
        thermal_conductivity_W_per_mK=15.0,
        safety_factor=2.0
    )

@pytest.fixture
def water_initial_state():
    """Fixture for a water ThermodynamicState at 300 K and 101325 Pa."""
    return ThermodynamicState.from_temperature_pressure(300.0, 101325, substance="H2O")

@pytest.fixture
def water_storage_tank(water_tank_spec, water_initial_state):
    """Create a StorageTank for water (H2O)."""
    return StorageTank(water_tank_spec, ResourceType.H2O, water_initial_state)

# ---------------------------------------------------------------------------
# Tests for StorageTank
# ---------------------------------------------------------------------------

def test_add_remove_resource(water_storage_tank):
    """Test adding and removing resource from the tank."""
    # Add 10 mol of water at 300 K.
    added = water_storage_tank.add_resource(10.0, 300.0)
    assert added == 10.0
    assert water_storage_tank.moles == 10.0
    # New pressure should not exceed maximum.
    assert water_storage_tank.state.pressure_Pa <= water_storage_tank.spec.max_pressure_Pa

    # Remove 5 mol of water.
    removed = water_storage_tank.remove_resource(5.0)
    assert removed == 5.0
    assert isclose(water_storage_tank.moles, 5.0, rel_tol=1e-3)

def test_calculate_density(water_storage_tank):
    """Test that the density calculation returns reasonable values."""
    water_storage_tank.add_resource(10.0, 300.0)
    density = water_storage_tank.calculate_density()
    # For water (assumed liquid below 373.15 K), density ~1000 kg/m³.
    if water_storage_tank.phase == PhaseType.LIQUID:
        assert 900.0 <= density <= 1100.0
    else:
        # If somehow in gas phase, density should be much lower.
        assert density < 10.0

def test_storage_tank_step_updates(water_storage_tank):
    """Test that the tank's step method updates thermal state and handles leaks."""
    water_storage_tank.add_resource(10.0, 300.0)
    initial_temp = water_storage_tank.state.temperature_K
    # Set a nonzero leak rate.
    water_storage_tank.leak_rate_mol_per_s = 0.001
    # Simulate one hour.
    water_storage_tank.step(3600)
    # Temperature should change due to ambient heat transfer.
    assert not isclose(water_storage_tank.state.temperature_K, initial_temp, rel_tol=1e-3)

def test_available_volume(water_storage_tank):
    """Test that the available volume in the tank is computed correctly."""
    water_storage_tank.add_resource(10.0, 300.0)
    avail_vol = water_storage_tank.calculate_available_volume_m3()
    # Since the tank has 1 m³ total, available volume must be between 0 and 1.
    assert 0.0 <= avail_vol <= 1.0

def test_liquid_default_pressure(water_storage_tank):
    """Test that adding resource to an empty liquid tank sets the pressure to 101325 Pa."""
    # Ensure storage tank is initially empty
    assert water_storage_tank.moles == 0
    # Initial pressure should be 101325 from the ThermodynamicState
    initial_pressure = water_storage_tank.state.pressure_Pa
    assert initial_pressure == 101325

    added = water_storage_tank.add_resource(15.0, 300.0)
    assert added == 15.0
    # For liquids, pressure remains at default value if tank was empty
    assert water_storage_tank.state.pressure_Pa == 101325

def test_o2_tank_stability():
    """Test O2 tank maintains reasonable temperature and pressure values."""
    # Create a realistic O2 tank specification
    spec = TankSpecification(
        volume_m3=1.0,
        max_pressure_Pa=3e6,  # 30 bar
        max_temperature_K=400.0,
        material="Stainless Steel 316",
        wall_thickness_m=0.012,
        thermal_conductivity_W_per_mK=16.3,
        safety_factor=2.0
    )
    
    # Initialize tank with reasonable state
    initial_state = ThermodynamicState.from_temperature_pressure(298.15, 101325, "O2")
    tank = StorageTank(spec, ResourceType.O2, initial_state)
    
    # Test adding O2 in small increments
    for _ in range(10):
        # Add 1 mol of O2 at room temperature
        added = tank.add_resource(1.0, 298.15)
        assert added > 0, "Should be able to add O2"
        assert 273.15 <= tank.state.temperature_K <= 400.0, f"Temperature out of bounds: {tank.state.temperature_K}"
        assert 1e3 <= tank.state.pressure_Pa <= 3e6, f"Pressure out of bounds: {tank.state.pressure_Pa}"
    
    # Test tank behavior over time
    for _ in range(100):
        tank.step(1.0)  # Step for 1 second
        assert 273.15 <= tank.state.temperature_K <= 400.0, f"Temperature out of bounds: {tank.state.temperature_K}"
        assert 1e3 <= tank.state.pressure_Pa <= 3e6, f"Pressure out of bounds: {tank.state.pressure_Pa}"
    
    # Test rapid addition
    added = tank.add_resource(50.0, 350.0)  # Add 50 mol at elevated temperature
    assert added > 0, "Should be able to add O2"
    assert 273.15 <= tank.state.temperature_K <= 400.0, f"Temperature out of bounds: {tank.state.temperature_K}"
    assert 1e3 <= tank.state.pressure_Pa <= 3e6, f"Pressure out of bounds: {tank.state.pressure_Pa}"
    
    # Test behavior at high pressure
    while tank.state.pressure_Pa < 2.5e6:  # Fill until near max pressure
        added = tank.add_resource(1.0, 298.15)
        if added == 0:  # Tank is full or at max pressure
            break
        assert 273.15 <= tank.state.temperature_K <= 400.0, f"Temperature out of bounds: {tank.state.temperature_K}"
        assert 1e3 <= tank.state.pressure_Pa <= 3e6, f"Pressure out of bounds: {tank.state.pressure_Pa}"