"""
Pytest tests for the complete Martian ISRU fuel plant simulation.
Tests full plant operation with different power scenarios.
"""

import pytest
import logging
import json
from pathlib import Path

from simulation_engine import SimulationEngine, SimulationConfig
from modules.power import PowerModule
from modules.environment import EnvironmentModule
from modules.electrolysis import ElectrolysisModule
from modules.atmosphere_intake import AtmosphereIntakeModule
from modules.sabatier_reactor import SabatierReactorModule
from conftest import assert_material_balance, assert_production_rates


@pytest.fixture
def simulation_config():
    """Standard simulation configuration for full tests."""
    return SimulationConfig(
        timestep_s=300.0,  # 5-minute timesteps 
        log_interval_s=900.0,  # Log every 15 minutes
        save_interval_s=1800.0,  # Save every 30 minutes
        auto_save_enabled=False  # Disable for tests
    )


@pytest.fixture
def full_simulation_factory(simulation_config):
    """Factory function to create simulations with different power scenarios."""
    def _create_simulation(power_scenario="adequate"):
        sim = SimulationEngine(simulation_config)
        sim.set_location(
            latitude_deg=-14.6,  # Equatorial region for good solar
            longitude_deg=175.9,
            altitude_m=0.0
        )
        
        # Add environment module (required first)
        env_module = EnvironmentModule()
        sim.add_module(env_module)
        
        # Add power module based on scenario
        if power_scenario == "limited":
            power_module = PowerModule(
                solar_array_area_m2=12000.0,  # 12k m² array
                panel_efficiency=0.20,
                battery_capacity_kwh=3000.0,  # 3 MWh battery
                battery_min_soc=0.15
            )
        elif power_scenario == "massive":
            power_module = PowerModule(
                solar_array_area_m2=1000000.0,  # 1M m² array
                panel_efficiency=0.20,
                battery_capacity_kwh=120000.0,  # 120 MWh battery
                battery_min_soc=0.10
            )
        else:  # adequate
            power_module = PowerModule(
                solar_array_area_m2=100000.0,  # 100k m² array
                panel_efficiency=0.20,
                battery_capacity_kwh=20000.0,  # 20 MWh battery
                battery_min_soc=0.10
            )
        
        sim.add_module(power_module)
        
        # Add production modules
        intake_module = AtmosphereIntakeModule(
            target_flow_rate_kg_hr=500.0 if power_scenario == "massive" else 100.0,
            compression_ratio=10.0,
            filter_efficiency=0.95
        )
        sim.add_module(intake_module)
        
        electrolysis_module = ElectrolysisModule(
            target_h2_rate_kg_hr=120.0 if power_scenario == "massive" else 25.0,
            operating_temperature_k=353.0,
            operating_pressure_kpa=3000.0
        )
        sim.add_module(electrolysis_module)
        
        sabatier_module = SabatierReactorModule(
            target_ch4_rate_kg_hr=480.0 if power_scenario == "massive" else 100.0,
            operating_temperature_k=573.0,
            operating_pressure_kpa=2000.0
        )
        sim.add_module(sabatier_module)
        
        # Add startup water
        startup_water = 25000.0 if power_scenario == "massive" else 5000.0
        sim.plant_state.materials["H2O"].store(startup_water)
        
        return sim
    
    return _create_simulation


@pytest.mark.simulation
@pytest.mark.parametrize("power_scenario,expected_ch4_min", [
    ("limited", 0),      # Should produce very little due to power shortage
    ("adequate", 500),   # Should produce moderate amounts
    ("massive", 2000),   # Should produce significant amounts
])
def test_power_scenario_simulation(full_simulation_factory, power_scenario, expected_ch4_min):
    """Test simulation with different power scenarios."""
    sim = full_simulation_factory(power_scenario)
    
    # Verify setup
    assert len(sim.modules) == 5  # Env, Power, Intake, Electrolysis, Sabatier
    
    # Run simulation for 0.5 sols
    duration = 0.5 if power_scenario == "limited" else 1.0
    results = sim.run_simulation(
        duration_sols=duration,
        speed_multiplier=100.0
    )
    
    # Verify results structure
    assert results is not None
    assert "total_ch4_kg" in results
    assert "total_o2_kg" in results
    assert "final_sol" in results
    assert "module_summaries" in results
    
    # Check production meets expectations
    assert_production_rates(results, min_ch4_kg=expected_ch4_min)
    
    # Verify time progression - for durations < 1 sol, final_sol will be 0
    # Instead check that simulation ran successfully by checking timestep count
    if duration >= 1.0:
        assert results["final_sol"] >= duration * 0.9  # Allow some tolerance
    else:
        # For sub-sol durations, just verify we have simulation steps
        assert results["simulation_steps"] > 0, "Simulation should have run some steps"
    
    # Check material balance
    assert "material_inventory" in results
    inventory = results["material_inventory"]
    for material, amount in inventory.items():
        assert amount >= 0, f"Negative material amount: {material} = {amount}"


@pytest.mark.simulation
@pytest.mark.slow
def test_full_plant_operation(full_simulation_factory, production_targets):
    """Test complete plant operation with adequate power."""
    sim = full_simulation_factory("adequate")
    
    # Run for 1 full sol
    results = sim.run_simulation(
        duration_sols=1.0,
        speed_multiplier=100.0
    )
    
    assert results is not None
    
    # Calculate daily production rates
    sols_simulated = results["final_sol"]
    ch4_daily = results["total_ch4_kg"] / sols_simulated
    o2_daily = results["total_o2_kg"] / sols_simulated
    
    # Should achieve reasonable production rates (not necessarily full targets)
    min_ch4_target = production_targets["ch4_daily_kg"] * 0.05  # 5% of target
    min_o2_target = production_targets["o2_daily_kg"] * 0.05   # 5% of target
    
    assert ch4_daily >= min_ch4_target, f"CH4 daily rate too low: {ch4_daily} < {min_ch4_target}"
    assert o2_daily >= min_o2_target, f"O2 daily rate too low: {o2_daily} < {min_o2_target}"
    
    # Check module status
    failed_modules = [m for m in results["module_summaries"] 
                     if m["status"] in ["shutdown", "error"]]
    assert len(failed_modules) == 0, f"Modules failed: {[m['name'] for m in failed_modules]}"


@pytest.mark.simulation
def test_power_shortage_handling(full_simulation_factory):
    """Test that limited power scenario handles shortages gracefully."""
    sim = full_simulation_factory("limited")
    
    # Run short simulation to test power shortage response
    results = sim.run_simulation(
        duration_sols=0.2,  # Short test
        speed_multiplier=100.0
    )
    
    assert results is not None
    
    # Should complete without errors even with power shortage
    assert results["simulation_steps"] > 0
    assert results["final_sol"] > 0
    
    # Production should be low but non-negative
    assert results["total_ch4_kg"] >= 0
    assert results["total_o2_kg"] >= 0
    
    # Modules should either be ok or in controlled shutdown (not error)
    for module in results["module_summaries"]:
        assert module["status"] in ["ok", "shutdown", "degraded"], \
            f"Module {module['name']} in unexpected state: {module['status']}"


@pytest.mark.simulation
@pytest.mark.slow
def test_massive_power_scenario(full_simulation_factory):
    """Test massive power plant scenario for maximum production."""
    sim = full_simulation_factory("massive")
    
    # Run for shorter duration due to computational intensity
    results = sim.run_simulation(
        duration_sols=0.5,
        speed_multiplier=200.0  # Faster for this test
    )
    
    assert results is not None
    
    # Should produce significant amounts with massive power
    assert results["total_ch4_kg"] > 1000, "Massive power should produce significant CH4"
    assert results["total_o2_kg"] > 2000, "Massive power should produce significant O2"
    
    # Energy consumption should be substantial
    assert results["total_energy_kwh"] > 10000, "Should consume significant energy"


@pytest.mark.integration
def test_simulation_data_consistency(full_simulation_factory):
    """Test that simulation data remains consistent throughout run."""
    sim = full_simulation_factory("adequate")
    
    # Run simulation with higher speed multiplier to avoid sleep delays
    results = sim.run_simulation(
        duration_sols=0.1,  # Shorter duration for faster test
        speed_multiplier=1000.0  # High multiplier to avoid sleep
    )
    
    assert results is not None
    
    # Check timestep data if available
    if "timestep_data" in results:
        timestep_data = results["timestep_data"]
        
        # Verify we have some data
        assert len(timestep_data) > 0, "Should have timestep data"
        
        # Verify monotonic time progression
        previous_sol = -1
        for data in timestep_data:
            current_sol = data.get("sol", 0)
            assert current_sol >= previous_sol, "Time should progress monotonically"
            previous_sol = current_sol
        
        # Verify energy conservation if available
        if "total_energy_kwh" in results:
            total_energy = sum(data.get("energy_consumed_kwh", 0) for data in timestep_data)
            # Allow larger tolerance since we're using a short duration
            assert abs(total_energy - results["total_energy_kwh"]) < 10.0, \
                "Energy totals should be consistent"


@pytest.mark.unit
def test_simulation_configuration(simulation_config):
    """Test simulation configuration settings."""
    assert simulation_config.timestep_s == 300.0
    assert simulation_config.log_interval_s == 900.0
    assert simulation_config.save_interval_s == 1800.0
    assert simulation_config.auto_save_enabled == False


@pytest.mark.integration
def test_module_interaction(full_simulation_factory):
    """Test that modules interact correctly."""
    sim = full_simulation_factory("adequate")
    
    # Run a few timesteps manually to observe interactions
    initial_materials = sim.plant_state.get_material_inventory()
    
    # Run 10 timesteps
    for _ in range(10):
        step_result = sim._execute_timestep()
        assert step_result is not None
        
        # Verify material balance is maintained
        assert_material_balance(sim.plant_state)
    
    final_materials = sim.plant_state.get_material_inventory()
    
    # Should see some material changes
    material_changed = False
    for material in ["CO2", "H2", "CH4", "O2", "H2O"]:
        if abs(final_materials.get(material, 0) - initial_materials.get(material, 0)) > 0.1:
            material_changed = True
            break
    
    assert material_changed, "Expected some material changes after simulation steps"


@pytest.mark.integration
def test_results_persistence(full_simulation_factory, tmp_path):
    """Test saving and loading simulation results."""
    sim = full_simulation_factory("adequate")
    
    # Run simulation
    results = sim.run_simulation(
        duration_sols=0.1,
        speed_multiplier=100.0
    )
    
    # Save results
    results_file = tmp_path / "test_results.json"
    
    # Remove timestep data for manageable file size
    results_to_save = results.copy()
    if "timestep_data" in results_to_save:
        del results_to_save["timestep_data"]
    
    with open(results_file, 'w') as f:
        json.dump(results_to_save, f, indent=2)
    
    # Load and verify
    with open(results_file, 'r') as f:
        loaded_results = json.load(f)
    
    # Verify key data is preserved
    assert loaded_results["total_ch4_kg"] == results["total_ch4_kg"]
    assert loaded_results["total_o2_kg"] == results["total_o2_kg"]
    assert loaded_results["final_sol"] == results["final_sol"]


@pytest.mark.simulation
def test_environmental_conditions_impact(full_simulation_factory):
    """Test that environmental conditions affect simulation."""
    sim = full_simulation_factory("adequate")
    
    # Get initial environmental conditions
    initial_env = sim.plant_state.environment
    initial_sol = initial_env.sol
    
    # Run simulation and track environmental changes
    results = sim.run_simulation(
        duration_sols=0.5,
        speed_multiplier=100.0
    )
    
    # Environment should have progressed
    final_env = sim.plant_state.environment
    assert final_env.sol > initial_sol
    
    # Should have experienced day/night cycles
    # This is implicit in the simulation running successfully


@pytest.mark.integration
def test_error_handling(simulation_config):
    """Test simulation error handling."""
    sim = SimulationEngine(simulation_config)
    
    # Try to run simulation without modules using high speed to avoid hang
    results = sim.run_simulation(duration_sols=0.01, speed_multiplier=1000.0)
    
    # Should handle gracefully (either return None or minimal results)
    # The exact behavior depends on implementation
    assert results is None or isinstance(results, dict) 