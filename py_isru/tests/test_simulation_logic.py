import pytest
import logging
from py_isru.lib.isru_plant import (
    ISRUPlant, PlantSpecification, ResourceType,
    SabatierSpecification, ElectrolysisSpecification,
    TankSpecification,
)
from py_isru.lib.reactor import OperationalStatus
from py_isru.lib.power_system.solar import (
    SolarPanelSpecification,
    SolarArraySpecification,
    TrackerSpecification,
    TrackingType
)
from py_isru.lib.power_system.battery import BatterySpecification
from py_isru.lib.power_system.krusty import KrustySpecification
from py_isru.lib.thermodynamics import ReactionKinetics

logging.basicConfig(level=logging.INFO)

@pytest.fixture
def mock_spec():
    # Create a mock specification similar to our dashboard setup
    return PlantSpecification(
        sabatier_spec=SabatierSpecification(
            volume_m3=0.5,
            max_temperature_K=1000.0,
            max_pressure_Pa=2e6,
            thermal_mass_J_per_K=5e4,
            heat_loss_coefficient_W_per_m2K=10.0,
            surface_area_m2=3.0,
            catalyst_type="Ru/Al2O3",
            catalyst_loading_kg_per_m3=50.0,
            catalyst_surface_area_m2_per_kg=100.0,
            catalyst_porosity=0.4,
        ),
        electrolysis_spec=ElectrolysisSpecification(
            volume_m3=0.2,
            max_temperature_K=360.0,
            max_pressure_Pa=3e6,
            thermal_mass_J_per_K=2e4,
            heat_loss_coefficient_W_per_m2K=15.0,
            surface_area_m2=2.0,
            membrane_type="Nafion",
            membrane_thickness_m=180e-6,
            membrane_conductivity_S_per_m=10.0,
            electrode_area_m2=1.0,
            max_current_density_A_per_m2=2000.0,
            max_power_W=5000.0,
        ),
        tank_specs={
            ResourceType.CO2: TankSpecification(
                volume_m3=2.0,
                max_pressure_Pa=2e6,
                max_temperature_K=400.0,
                material="Stainless Steel 316",
                wall_thickness_m=0.01,
                thermal_conductivity_W_per_mK=16.3,
                safety_factor=2.0
            ),
            ResourceType.H2: TankSpecification(
                volume_m3=1.0,
                max_pressure_Pa=3e6,
                max_temperature_K=400.0,
                material="Inconel 718",
                wall_thickness_m=0.015,
                thermal_conductivity_W_per_mK=11.4,
                safety_factor=2.5
            ),
            ResourceType.O2: TankSpecification(
                volume_m3=1.0,
                max_pressure_Pa=3e6,
                max_temperature_K=400.0,
                material="Stainless Steel 316",
                wall_thickness_m=0.012,
                thermal_conductivity_W_per_mK=16.3,
                safety_factor=2.0
            ),
            ResourceType.CH4: TankSpecification(
                volume_m3=2.0,
                max_pressure_Pa=2e6,
                max_temperature_K=400.0,
                material="Stainless Steel 316",
                wall_thickness_m=0.01,
                thermal_conductivity_W_per_mK=16.3,
                safety_factor=2.0
            ),
            ResourceType.H2O: TankSpecification(
                volume_m3=1.0,
                max_pressure_Pa=1e6,
                max_temperature_K=400.0,
                material="Stainless Steel 316",
                wall_thickness_m=0.008,
                thermal_conductivity_W_per_mK=16.3,
                safety_factor=1.8
            ),
        },
        solar_spec=SolarArraySpecification(
            n_panels=20,
            panel_spec=SolarPanelSpecification(
                area=2.0,
                base_efficiency=0.3,
                max_temp=85.0,
                min_temp=-125.0,
                mass=10.0,
                dust_tolerance=0.1
            ),
            tracker_spec=TrackerSpecification(
                type=TrackingType.DUAL_AXIS,
                power_consumption=10.0,
                max_slew_rate=5.0,
            )
        ),
        battery_spec=BatterySpecification(
            capacity_wh=50000.0,
            max_power=10000.0
        ),
        krusty_spec=KrustySpecification(
            nominal_power=10000.0,
            max_power=12000.0,
            startup_time=3600.0,
            cooldown_time=7200.0,
            burn_in_time=86400.0
        ),
        min_tank_levels_mol={res: 50.0 for res in list(ResourceType)},
        max_tank_levels_mol={res: 1000.0 for res in list(ResourceType)},
        emergency_power_threshold_W=1000.0,
        maintenance_interval_s=604800.0
    )


@pytest.fixture
def plant(mock_spec):
    p = ISRUPlant(mock_spec)
    # Add initial resources as in the dashboard app
    initial_resources = {
        ResourceType.CO2: 500.0,
        ResourceType.H2O: 500.0,
        ResourceType.H2: 100.0,
        ResourceType.O2: 0.0,
        ResourceType.CH4: 0.0
    }
    for resource, amount in initial_resources.items():
        logging.info(f"Adding {amount} {resource} to tank")
        p.tanks[resource].add_resource(amount, 298.15)
        logging.info(f"Tank {resource} has {p.tanks[resource].moles} moles")
    return p


def test_initialization(plant):
    # Check that tanks have the expected values after initialization
    for resource, tank in plant.tanks.items():
        expected_amount = {
            ResourceType.CO2: 500.0,
            ResourceType.H2O: 500.0,
            ResourceType.H2: 100.0,
            ResourceType.O2: 0.0,
            ResourceType.CH4: 0.0
        }
        logging.info(f"Checking {resource} tank: {tank.moles} expected: {expected_amount[resource]}")
        assert tank.moles == expected_amount[resource]


def test_start_shutdown(plant):
    plant.start()
    # Check that the plant status reflects a running state using enum
    assert hasattr(plant, 'status')
    assert plant.status == OperationalStatus.RUNNING
    plant.shutdown()
    # After shutdown, the plant returns to STANDBY
    assert plant.status == OperationalStatus.STANDBY


def test_resource_addition(plant):
    initial = plant.tanks[ResourceType.H2O].moles
    add_amount = 50.0
    plant.tanks[ResourceType.H2O].add_resource(add_amount, 298.15)
    assert plant.tanks[ResourceType.H2O].moles == initial + add_amount


def test_update_behavior(plant):
    # Monkey patch solar array to provide sufficient power
    plant.solar_array.calculate_output = lambda: 3000.0

    pre = {res: tank.moles for res, tank in plant.tanks.items()}
    plant.start()
    for _ in range(1):
        plant.step(1.0)
    post = {res: tank.moles for res, tank in plant.tanks.items()}
    logging.info(f"Pre: {pre}")
    logging.info(f"Post: {post}")
    assert pre != post


def test_reaction_stoichiometry(plant):
    """Test that reactants are consumed and products produced in correct ratios"""
    # Ensure sufficient power
    plant.solar_array.calculate_output = lambda: 15000.0
    
    # Record initial state (only for tracked resources)
    tracked_resources = set(plant.tanks.keys())
    initial = {res: tank.moles for res, tank in plant.tanks.items()}
    logging.info(f"Initial state: {initial}")
    
    # Run plant for several steps
    plant.start()
    for step in range(10):  # Run for 10 steps to get measurable changes
        plant.step(1.0)
        logging.info(f"Step {step + 1}: { {res: tank.moles for res, tank in plant.tanks.items()} }")
    
    # Record final state
    final = {res: tank.moles for res, tank in plant.tanks.items()}
    logging.info(f"Final state: {final}")
    
    # Calculate changes (only for tracked resources)
    delta = {res: final[res] - initial[res] for res in tracked_resources}
    logging.info(f"Resource changes after 10 steps: {delta}")
    
    # Test Sabatier reaction stoichiometry: CO2 + 4H2 → CH4 + 2H2O
    if abs(delta[ResourceType.CH4]) > 0.001:  # If methane was produced
        co2_consumed = -delta[ResourceType.CO2]
        ch4_produced = delta[ResourceType.CH4]
        h2o_produced_sabatier = 2 * ch4_produced  # 2 H2O produced per CH4
        h2_consumed_sabatier = 4 * ch4_produced   # 4 H2 consumed per CH4
        
        logging.info(f"Sabatier: CO2 consumed: {co2_consumed}, CH4 produced: {ch4_produced}, "
                     f"H2O produced: {h2o_produced_sabatier}, H2 consumed: {h2_consumed_sabatier}")
        
        # Check ratios (allowing for some numerical error)
        assert abs(co2_consumed - ch4_produced) < 0.1, "CO2 consumed should equal CH4 produced"
    
    # Test Electrolysis reaction stoichiometry: 2H2O → 2H2 + O2
    if abs(delta[ResourceType.O2]) > 0.001:  # If oxygen was produced
        o2_produced = delta[ResourceType.O2]
        h2_produced_electrolysis = 2 * o2_produced  # 2 H2 produced per O2
        h2o_consumed_electrolysis = 2 * o2_produced  # 2 H2O consumed per O2
        
        # Total H2 change = H2 produced from electrolysis - H2 consumed by Sabatier
        h2_net_change = delta[ResourceType.H2]
        h2_consumed_sabatier = 4 * delta[ResourceType.CH4] if abs(delta[ResourceType.CH4]) > 0.001 else 0
        h2_produced_actual = h2_net_change + h2_consumed_sabatier
        
        logging.info(f"Electrolysis: O2 produced: {o2_produced}, H2 produced: {h2_produced_electrolysis}, "
                     f"H2O consumed: {h2o_consumed_electrolysis}, H2 net change: {h2_net_change}, "
                     f"H2 produced actual: {h2_produced_actual}")
        
        # Check ratios
        assert abs(h2_produced_actual - h2_produced_electrolysis) < 0.1, "H2 produced should match electrolysis stoichiometry" 