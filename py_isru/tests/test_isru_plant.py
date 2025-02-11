"""
Tests for main ISRU plant implementation.
"""
import pytest
import numpy as np

from py_isru.lib.reactor import ResourceType, OperationalStatus
from py_isru.lib.sabatier_reactor import SabatierSpecification
from py_isru.lib.electrolysis_reactor import ElectrolysisSpecification
from py_isru.lib.storage_tank import TankSpecification
from py_isru.lib.power_system import (
    PowerSystemStatus,
    SolarArraySpecification,
    BatterySpecification,
    KrustySpecification
)
from py_isru.lib.isru_plant import ISRUPlant, PlantSpecification, PlantStatus

@pytest.fixture
def basic_plant_spec():
    """Create a basic plant specification for testing"""
    return PlantSpecification(
        # Sabatier reactor
        sabatier_spec=SabatierSpecification(
            volume=0.1,
            max_temperature=900.0,
            max_pressure=2e6,
            thermal_mass=500.0,
            heat_loss_coefficient=10.0,
            surface_area=1.0,
            catalyst_type="Ru/Al₂O₃",
            catalyst_loading=100.0,
            catalyst_surface_area=200.0,
            catalyst_porosity=0.4
        ),
        
        # Electrolysis reactor
        electrolysis_spec=ElectrolysisSpecification(
            volume=0.05,
            max_temperature=400.0,
            max_pressure=3e6,
            thermal_mass=200.0,
            heat_loss_coefficient=5.0,
            surface_area=0.5,
            membrane_type="Nafion",
            membrane_thickness=1.27e-4,
            membrane_conductivity=10.0,
            electrode_area=0.1,
            max_current_density=2000.0,
            max_power=5000.0
        ),
        
        # Storage tanks
        tank_specs={
            ResourceType.CO2: TankSpecification(
                volume=5.0,
                max_pressure=10e6,
                max_temperature=500.0,
                material="Stainless Steel 316",
                wall_thickness=0.01,
                thermal_conductivity=16.3,
                safety_factor=1.5
            ),
            ResourceType.H2: TankSpecification(
                volume=5.0,
                max_pressure=10e6,
                max_temperature=500.0,
                material="Stainless Steel 316",
                wall_thickness=0.01,
                thermal_conductivity=16.3,
                safety_factor=1.5
            ),
            ResourceType.O2: TankSpecification(
                volume=5.0,
                max_pressure=10e6,
                max_temperature=500.0,
                material="Stainless Steel 316",
                wall_thickness=0.01,
                thermal_conductivity=16.3,
                safety_factor=1.5
            ),
            ResourceType.CH4: TankSpecification(
                volume=5.0,
                max_pressure=10e6,
                max_temperature=500.0,
                material="Stainless Steel 316",
                wall_thickness=0.01,
                thermal_conductivity=16.3,
                safety_factor=1.5
            ),
            ResourceType.H2O: TankSpecification(
                volume=5.0,
                max_pressure=10e6,
                max_temperature=500.0,
                material="Stainless Steel 316",
                wall_thickness=0.01,
                thermal_conductivity=16.3,
                safety_factor=1.5
            )
        },
        
        # Power systems
        solar_spec=SolarArraySpecification(
            area=100.0,
            efficiency=0.3,
            temperature_coefficient=-0.004,
            dust_coefficient=0.8
        ),
        
        battery_spec=BatterySpecification(
            capacity=50e3,
            max_charge_rate=10e3,
            max_discharge_rate=10e3,
            charge_efficiency=0.95,
            discharge_efficiency=0.95,
            depth_of_discharge=0.8
        ),
        
        krusty_spec=KrustySpecification(
            thermal_power=10e3,
            electrical_efficiency=0.08,
            startup_time=3600.0,
            cooldown_time=7200.0,
            minimum_power=1e3
        ),
        
        # Control parameters
        min_tank_levels={
            ResourceType.CO2: 100.0,
            ResourceType.H2: 100.0,
            ResourceType.O2: 100.0,
            ResourceType.CH4: 100.0,
            ResourceType.H2O: 100.0
        },
        
        max_tank_levels={
            ResourceType.CO2: 1000.0,
            ResourceType.H2: 1000.0,
            ResourceType.O2: 1000.0,
            ResourceType.CH4: 1000.0,
            ResourceType.H2O: 1000.0
        },
        
        emergency_power_threshold=1000.0,  # W
        maintenance_interval=30 * 24 * 3600.0  # 30 days
    )

@pytest.fixture
def basic_plant(basic_plant_spec):
    """Create a basic ISRU plant for testing"""
    return ISRUPlant(basic_plant_spec)

def test_plant_initialization(basic_plant):
    """Test plant initialization"""
    plant = basic_plant
    assert plant.status == PlantStatus.STANDBY
    assert plant.time == 0.0
    assert plant.fault_condition is None
    
    # Check subsystem initialization
    assert plant.sabatier.operational_status == OperationalStatus.STANDBY
    assert plant.electrolysis.operational_status == OperationalStatus.STANDBY
    assert plant.solar_array.status == PowerSystemStatus.ONLINE
    assert plant.battery.status == PowerSystemStatus.ONLINE
    assert plant.krusty.status == PowerSystemStatus.OFFLINE

def test_plant_startup_shutdown(basic_plant):
    """Test plant startup and shutdown sequences"""
    plant = basic_plant
    
    # Test startup
    assert plant.start()
    assert plant.status == PlantStatus.RUNNING
    assert plant.sabatier.operational_status == OperationalStatus.RUNNING
    assert plant.electrolysis.operational_status == OperationalStatus.RUNNING
    
    # Test shutdown
    assert plant.shutdown()
    assert plant.status == PlantStatus.STANDBY
    assert plant.sabatier.operational_status == OperationalStatus.STANDBY
    assert plant.electrolysis.operational_status == OperationalStatus.STANDBY

def test_power_management(basic_plant):
    """Test power management and distribution"""
    plant = basic_plant
    plant.start()
    
    # Set solar array to produce power
    plant.solar_array.time_of_day = plant.solar_array.day_length / 4  # Noon
    
    # Step the plant
    plant.step(1.0)
    
    # Check power distribution
    available_power = plant._calculate_available_power()
    required_power = plant._calculate_required_power()
    
    assert available_power > 0.0
    assert required_power > 0.0
    
    # Excess power should go to battery
    if available_power > required_power:
        assert plant.battery.charging
        assert plant.battery.charge_level > 0.0

def test_resource_flow(basic_plant):
    """Test resource flow through the system"""
    plant = basic_plant
    plant.start()
    
    # Add some initial resources
    plant.tanks[ResourceType.CO2].add_resource(10.0, 298.15)
    plant.tanks[ResourceType.H2].add_resource(40.0, 298.15)
    plant.tanks[ResourceType.H2O].add_resource(10.0, 298.15)
    
    # Run for a while
    for _ in range(100):
        plant.step(1.0)
    
    # Should have produced some CH4 and O2
    assert plant.total_ch4_produced > 0.0
    assert plant.total_o2_produced > 0.0
    
    # Check mass balance
    initial_carbon = 10.0  # moles of CO2
    final_carbon = (plant.tanks[ResourceType.CO2].moles + 
                   plant.tanks[ResourceType.CH4].moles)
    assert np.isclose(initial_carbon, final_carbon, rtol=1e-10)

def test_emergency_handling(basic_plant):
    """Test emergency condition handling"""
    plant = basic_plant
    plant.start()
    
    # Force low power condition
    plant.solar_array.time_of_day = plant.solar_array.day_length * 0.75  # Night
    plant.battery.charge_level = 0.0
    
    # Step the plant
    plant.step(1.0)
    
    # Should enter emergency mode
    assert plant.status == PlantStatus.EMERGENCY
    assert plant.fault_condition == "Insufficient power"

def test_maintenance_scheduling(basic_plant):
    """Test maintenance scheduling"""
    plant = basic_plant
    plant.start()
    
    # Run until maintenance interval
    plant.step(plant.spec.maintenance_interval + 1.0)
    
    assert plant.status == PlantStatus.MAINTENANCE

def test_status_reporting(basic_plant):
    """Test status reporting functionality"""
    plant = basic_plant
    plant.start()
    
    # Add some resources and run
    plant.tanks[ResourceType.CO2].add_resource(10.0, 298.15)
    plant.tanks[ResourceType.H2].add_resource(40.0, 298.15)
    plant.step(3600.0)
    
    report = plant.get_status_report()
    
    # Check report contents
    assert "plant_status" in report
    assert "fault_condition" in report
    assert "total_ch4_produced" in report
    assert "total_o2_produced" in report
    assert "tank_levels" in report
    assert "power_systems" in report
    assert "reactors" in report
    
    # Check specific values
    assert report["plant_status"] == plant.status
    assert report["total_ch4_produced"] == plant.total_ch4_produced
    assert report["total_o2_produced"] == plant.total_o2_produced
    
    # Check subsystem reporting
    assert "solar" in report["power_systems"]
    assert "battery" in report["power_systems"]
    assert "krusty" in report["power_systems"]
    assert "sabatier" in report["reactors"]
    assert "electrolysis" in report["reactors"]

def test_edge_cases(basic_plant):
    """Test edge cases and error conditions"""
    plant = basic_plant
    
    # Test starting from wrong state
    plant.status = PlantStatus.RUNNING
    assert not plant.start()
    
    # Test shutdown from wrong state
    plant.status = PlantStatus.MAINTENANCE
    assert not plant.shutdown()
    
    # Test step with zero dt
    plant.status = PlantStatus.RUNNING
    initial_time = plant.time
    plant.step(0.0)
    assert plant.time == initial_time
    
    # Test with negative dt
    with pytest.raises(ValueError):
        plant.step(-1.0) 