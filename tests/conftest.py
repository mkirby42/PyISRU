"""
Pytest configuration and shared fixtures for ISRU simulation tests.
"""

import pytest
import sys
import logging
from pathlib import Path

# Add src to path for all tests
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from simulation_engine import SimulationEngine, SimulationConfig
from modules.environment import EnvironmentModule
from modules.power import PowerModule
from modules.electrolysis import ElectrolysisModule
from modules.atmosphere_intake import AtmosphereIntakeModule
from modules.sabatier_reactor import SabatierReactorModule


@pytest.fixture
def basic_sim_config():
    """Basic simulation configuration for testing."""
    return SimulationConfig(
        timestep_s=300.0,  # 5-minute timesteps
        log_interval_s=3600.0,  # Log every hour
        save_interval_s=1800.0,  # Save every 30 minutes
        auto_save_enabled=False  # Disable auto-save for tests
    )


@pytest.fixture
def basic_simulation(basic_sim_config):
    """Create a basic simulation engine with environment module."""
    sim = SimulationEngine(basic_sim_config)
    sim.set_location(
        latitude_deg=-14.6,  # Equatorial region for good solar
        longitude_deg=175.9,
        altitude_m=0.0
    )
    
    # Add environment module (required by other modules)
    env_module = EnvironmentModule()
    sim.add_module(env_module)
    
    return sim


@pytest.fixture
def power_simulation(basic_simulation):
    """Simulation with power module added."""
    power_module = PowerModule(
        solar_array_area_m2=10000.0,  # 10k m² for testing
        panel_efficiency=0.20,
        battery_capacity_kwh=2000.0,
        battery_min_soc=0.10
    )
    basic_simulation.add_module(power_module)
    return basic_simulation


@pytest.fixture
def full_isru_simulation(basic_simulation):
    """Complete ISRU simulation with all modules."""
    # Power module
    power_module = PowerModule(
        solar_array_area_m2=100000.0,  # Large array for full operation
        panel_efficiency=0.20,
        battery_capacity_kwh=20000.0,
        battery_min_soc=0.10
    )
    basic_simulation.add_module(power_module)
    
    # Atmosphere intake
    intake_module = AtmosphereIntakeModule(
        target_flow_rate_kg_hr=100.0,
        compression_ratio=10.0,
        filter_efficiency=0.95
    )
    basic_simulation.add_module(intake_module)
    
    # Electrolysis
    electrolysis_module = ElectrolysisModule(
        target_h2_rate_kg_hr=25.0,
        operating_temperature_k=353.0,
        operating_pressure_kpa=3000.0
    )
    basic_simulation.add_module(electrolysis_module)
    
    # Sabatier reactor
    sabatier_module = SabatierReactorModule(
        target_ch4_rate_kg_hr=100.0,
        operating_temperature_k=573.0,
        operating_pressure_kpa=2000.0
    )
    basic_simulation.add_module(sabatier_module)
    
    # Add startup water for electrolysis
    basic_simulation.plant_state.materials["H2O"].store(5000.0)
    
    return basic_simulation


@pytest.fixture
def capture_logs():
    """Fixture to capture logs during tests."""
    import logging
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    return logger


@pytest.fixture(scope="session")
def test_data_dir():
    """Directory for test data files."""
    return Path(__file__).parent / "test_data"


@pytest.fixture
def power_scenarios():
    """Different power configuration scenarios for parametrized tests."""
    return {
        "limited": {
            "solar_array_area_m2": 12000.0,
            "battery_capacity_kwh": 3000.0,
            "description": "Limited power for shortage testing"
        },
        "adequate": {
            "solar_array_area_m2": 100000.0,
            "battery_capacity_kwh": 20000.0,
            "description": "Adequate power for normal operation"
        },
        "massive": {
            "solar_array_area_m2": 1000000.0,
            "battery_capacity_kwh": 120000.0,
            "description": "Massive power plant for maximum production"
        }
    }


@pytest.fixture
def production_targets():
    """Production targets from PRD for validation."""
    return {
        "ch4_daily_kg": 11000,  # kg/sol
        "o2_daily_kg": 29000,   # kg/sol
        "total_propellant_daily_kg": 40000,  # kg/sol
        "energy_efficiency_target": 0.75  # Target efficiency
    }


# Helper functions that can be used in tests
def assert_material_balance(plant_state, tolerance_kg=0.1):
    """Assert that material conservation is maintained."""
    # Check that stored materials don't exceed capacity
    for name, store in plant_state.materials.items():
        assert store.mass_kg <= store.capacity_kg, f"{name} exceeds capacity: {store.mass_kg} > {store.capacity_kg}"
        assert store.mass_kg >= 0, f"{name} has negative mass: {store.mass_kg}"


def assert_power_balance(power_budget, tolerance_kw=0.1):
    """Assert that power allocation is reasonable."""
    assert power_budget.total_allocated_kw <= power_budget.generation_kw + tolerance_kw, \
        f"Power overallocated: {power_budget.total_allocated_kw} > {power_budget.generation_kw}"
    assert power_budget.total_allocated_kw >= 0, \
        f"Negative power allocation: {power_budget.total_allocated_kw}"


def assert_production_rates(results, min_ch4_kg=0, min_o2_kg=0):
    """Assert minimum production rates are met."""
    assert results.get('total_ch4_kg', 0) >= min_ch4_kg, \
        f"CH4 production too low: {results.get('total_ch4_kg', 0)} < {min_ch4_kg}"
    assert results.get('total_o2_kg', 0) >= min_o2_kg, \
        f"O2 production too low: {results.get('total_o2_kg', 0)} < {min_o2_kg}" 