import pytest
import logging
from math import isclose, radians

from py_isru.lib.storage_tank import TankSpecification
from py_isru.lib.reactor import ResourceType, OperationalStatus
from py_isru.lib.isru_plant import ISRUPlant, PlantSpecification, ISRUPlantError, ISRUPlantErrorCode
from py_isru.lib.sabatier_reactor import SabatierSpecification
from py_isru.lib.electrolysis_reactor import ElectrolysisSpecification
from py_isru.lib.power_system import SolarArraySpecification, SolarPanelSpecification, BatterySpecification, KrustySpecification
from py_isru.lib.environment import MarsEnvironment, MarsEnvironmentSpecification

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Fixtures for ISRUPlant
# ---------------------------------------------------------------------------

@pytest.fixture
def dummy_plant_spec():
    """Create a dummy PlantSpecification for the ISRU plant."""
    # Create dummy Sabatier and Electrolysis reactor specifications with revised keyword names.
    sabatier_spec = SabatierSpecification(
        volume_m3=1.0,
        max_temperature_K=1000.0,
        max_pressure_Pa=5e6,
        thermal_mass_J_per_K=1e4,
        heat_loss_coefficient_W_per_m2K=10.0,
        surface_area_m2=5.0,
        catalyst_type="Ru/Al2O3",
        catalyst_loading_kg_per_m3=50.0,
        catalyst_surface_area_m2_per_kg=100.0,
        catalyst_porosity=0.4
    )
    electrolysis_spec = ElectrolysisSpecification(
        volume_m3=1.0,
        max_temperature_K=1000.0,
        max_pressure_Pa=5e6,
        thermal_mass_J_per_K=1e4,
        heat_loss_coefficient_W_per_m2K=10.0,
        surface_area_m2=5.0,
        membrane_type="Nafion",
        membrane_thickness_m=0.0002,
        membrane_conductivity_S_per_m=10.0,
        electrode_area_m2=1.0,
        max_current_density_A_per_m2=1000.0,
        max_power_W=10000.0
    )
    # Create dummy tank specifications for each resource.
    tank_specs = {
        ResourceType.CO2: TankSpecification(
            volume_m3=2.0,
            max_pressure_Pa=5e6,
            max_temperature_K=1000.0,
            material="Stainless Steel 316",
            wall_thickness_m=0.01,
            thermal_conductivity_W_per_mK=15.0,
            safety_factor=2.0
        ),
        ResourceType.H2: TankSpecification(
            volume_m3=2.0,
            max_pressure_Pa=5e6,
            max_temperature_K=1000.0,
            material="Stainless Steel 316",
            wall_thickness_m=0.01,
            thermal_conductivity_W_per_mK=15.0,
            safety_factor=2.0
        ),
        ResourceType.O2: TankSpecification(
            volume_m3=2.0,
            max_pressure_Pa=5e6,
            max_temperature_K=1000.0,
            material="Stainless Steel 316",
            wall_thickness_m=0.01,
            thermal_conductivity_W_per_mK=15.0,
            safety_factor=2.0
        ),
        ResourceType.CH4: TankSpecification(
            volume_m3=2.0,
            max_pressure_Pa=5e6,
            max_temperature_K=1000.0,
            material="Stainless Steel 316",
            wall_thickness_m=0.01,
            thermal_conductivity_W_per_mK=15.0,
            safety_factor=2.0
        ),
        ResourceType.H2O: TankSpecification(
            volume_m3=2.0,
            max_pressure_Pa=5e6,
            max_temperature_K=1000.0,
            material="Stainless Steel 316",
            wall_thickness_m=0.01,
            thermal_conductivity_W_per_mK=15.0,
            safety_factor=2.0
        )
    }
    # Dummy power system specifications.
    solar_spec = SolarArraySpecification(
        n_panels=10,
        panel_spec=SolarPanelSpecification(
            area=5.0,
            base_efficiency=0.2,
            max_temp=100.0,
            min_temp=-100.0,
            mass=10.0,
            dust_tolerance=0.5
        )
    )
    battery_spec = BatterySpecification(
        capacity_wh=1000.0, 
        max_power=500.0,
        initial_state_of_charge=1.0  # 100% charged
    )
    krusty_spec = KrustySpecification(
        nominal_power=2500.0,  # 2.5 kW nominal electrical
        max_power=3000.0,     # 3 kW max electrical
        startup_time=200.0,  # 200 seconds startup (not realistic)
        cooldown_time=200.0, # 200 seconds cooldown (not realistic)
        burn_in_time=200.0  # 200 seconds burn-in (not realistic)
    )
    # Control parameters.
    min_tank_levels_mol = {res: 1.0 for res in tank_specs.keys()}
    max_tank_levels_mol = {res: 100.0 for res in tank_specs.keys()}
    emergency_power_threshold_W = 500.0  # W
    maintenance_interval_s = 3600.0  # 1 hour

    return PlantSpecification(
        sabatier_spec=sabatier_spec,
        electrolysis_spec=electrolysis_spec,
        tank_specs=tank_specs,
        solar_spec=solar_spec,
        battery_spec=battery_spec,
        krusty_spec=krusty_spec,
        min_tank_levels_mol=min_tank_levels_mol,
        max_tank_levels_mol=max_tank_levels_mol,
        emergency_power_threshold_W=emergency_power_threshold_W,
        maintenance_interval_s=maintenance_interval_s
    )

@pytest.fixture
def mars_environment():
    """Create a realistic Mars environment at Jezero Crater."""
    return MarsEnvironment(
        MarsEnvironmentSpecification(
            # Jezero Crater coordinates: 18.4447°N, 77.4508°E
            latitude_rad=radians(18.4447),
            longitude_rad=radians(77.4508),
            altitude_m=-2.5e3,  # Jezero is about 2.5km below Mars reference
        )
    )

@pytest.fixture
def isru_plant(dummy_plant_spec, mars_environment):
    """Create an ISRUPlant instance using the dummy specification and Mars environment."""
    return ISRUPlant(dummy_plant_spec, mars_environment)

def initialize_tanks(plant: ISRUPlant, moles: float = 10.0) -> None:
    """Helper function to initialize all tanks with resources.
    
    Args:
        plant: The ISRU plant instance
        moles: Amount of moles to add to each tank (default: 10.0)
    """
    for resource_type in ResourceType:
        if resource_type in plant.tanks:
            plant.tanks[resource_type].moles = moles

# ---------------------------------------------------------------------------
# Tests for ISRUPlant
# ---------------------------------------------------------------------------
def test_plant_init(isru_plant):
    """Test that the plant initializes correctly."""
    logger.info(f"Plant state: {isru_plant.get_state()}")
    assert isru_plant.get_status() == OperationalStatus.STANDBY

def test_plant_start_stop(isru_plant):
    """Test that the plant can start and then shutdown correctly."""
    initialize_tanks(isru_plant)
    assert isru_plant.get_status() == OperationalStatus.STANDBY
    isru_plant.start()
    assert isru_plant.get_status() == OperationalStatus.RUNNING
    isru_plant.shutdown()
    assert isru_plant.get_status() == OperationalStatus.STANDBY

def test_plant_step(isru_plant):
    """Test that after a simulation step, the plant time and metrics update."""
    initialize_tanks(isru_plant)
    isru_plant.start()
    
    initial_time_s = isru_plant.get_state().time_elapsed_s
    isru_plant.step(60.0)  # 60 s step
    assert isru_plant.get_state().time_elapsed_s > initial_time_s

def test_plant_insufficient_power_emergency(isru_plant):
    """
    Test that if available power is insufficient, the plant transitions to EMERGENCY mode.
    For testing purposes, we monkey-patch the solar array output to return 0 W.
    """
    initialize_tanks(isru_plant)
    # Start plant
    isru_plant.start()
    
    # Overrides
    isru_plant.solar_array.calculate_output = lambda: 0.0
    isru_plant.krusty.calculate_output = lambda: 0.0
    isru_plant.battery.calculate_output = lambda: 0.0
    
    # Run plant
    isru_plant.step(60.0)
    
    # Verify plant has correct error and is in EMERGENCY mode
    assert isru_plant.get_state().error.error_code == ISRUPlantErrorCode.INSUFFICIENT_POWER
    assert isru_plant.get_status() == OperationalStatus.EMERGENCY

def test_reactor_temperatures_update(isru_plant):
    """Test that reactor temperatures are properly updated in the plant state."""
    # Add resources with 4:1 H2:CO2 ratio for Sabatier reaction
    initialize_tanks(isru_plant)
    isru_plant.tanks[ResourceType.H2].moles = 40.0  # 4:1 ratio with CO2
    
    # Start plant and run for a bit
    isru_plant.start()
    isru_plant.step(60.0)
    
    # Get state and verify temperatures
    state = isru_plant.get_state()
    assert state.sabatier_temperature_K == isru_plant.sabatier.thermodynamic_state.temperature_K
    assert state.electrolysis_temperature_K == isru_plant.electrolysis.thermodynamic_state.temperature_K
    
    # Verify temperatures are non-zero (reactors should be running)
    assert state.sabatier_temperature_K > 0
    assert state.electrolysis_temperature_K > 0