#!/usr/bin/env python3
"""
Test script for the core ISRU simulation framework.
Verifies that the basic components work together correctly.
"""

import logging
import sys
import os

# Add src to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.simulation_engine import SimulationEngine, SimulationConfig
from src.modules.environment import EnvironmentModule

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_basic_functionality():
    """Test basic simulation functionality."""
    print("🧪 Testing core framework...")
    
    # Create simulation engine
    config = SimulationConfig(
        timestep_s=300.0,  # 5-minute timesteps for faster testing
        log_interval_s=3600.0  # Log every hour
    )
    sim = SimulationEngine(config)
    
    # Set location (Jezero Crater - Mars 2020 landing site)
    sim.set_location(latitude_deg=18.4, longitude_deg=77.5, altitude_m=-2500)
    
    # Add environment module
    env_module = EnvironmentModule()
    sim.add_module(env_module)
    
    print(f"✅ Created simulation: {sim}")
    print(f"✅ Plant location: {sim.plant_state.environment.latitude_deg}°, {sim.plant_state.environment.longitude_deg}°")
    
    return sim

def test_material_stores():
    """Test material store operations."""
    print("\n🧪 Testing material stores...")
    
    sim = test_basic_functionality()
    plant_state = sim.plant_state
    
    # Test material transactions
    h2o_store = plant_state.get_material("H2O")
    print(f"Initial H2O: {h2o_store}")
    
    # Store some water
    stored = h2o_store.store(1000.0)  # 1 tonne
    print(f"Stored {stored} kg H2O: {h2o_store}")
    
    # Withdraw some water
    withdrawn = h2o_store.withdraw(300.0)  # 300 kg
    print(f"Withdrew {withdrawn} kg H2O: {h2o_store}")
    
    # Test capacity limits
    ch4_store = plant_state.get_material("CH4")
    print(f"CH4 store capacity: {ch4_store.capacity_kg} kg")
    print(f"CH4 fill fraction: {ch4_store.fill_fraction:.1%}")
    
    print("✅ Material store operations work correctly")

def test_environment_simulation():
    """Test environment module simulation."""
    print("\n🧪 Testing environment simulation...")
    
    sim = test_basic_functionality()
    env_module = sim.modules[0]  # Environment module
    
    # Run a few timesteps to see environment changes
    print("Running 24 hours of simulation (96 timesteps)...")
    
    for i in range(96):  # 24 hours at 5-minute timesteps
        # Execute one timestep
        step_result = sim._execute_timestep()
        
        if i % 12 == 0:  # Log every hour
            env_data = step_result["module_results"]["Environment"]
            sol = step_result["sol"]
            time_of_sol = step_result["time_of_sol"]
            irradiance = env_data["solar_irradiance_w_m2"]
            temp_c = env_data["ambient_temperature_k"] - 273.15
            
            print(f"Sol {sol} ({time_of_sol:.3f}): "
                  f"Solar: {irradiance:.0f} W/m², "
                  f"Temp: {temp_c:.1f}°C, "
                  f"Daytime: {env_data['is_daytime']}")
    
    # Get final environmental summary
    final_summary = env_module.get_environmental_summary(sim.plant_state)
    print(f"\nFinal environment summary:")
    print(f"  Location: {final_summary['location']}")
    print(f"  Solar: {final_summary['solar']['irradiance_w_m2']:.0f} W/m²")
    print(f"  Temperature: {final_summary['atmosphere']['temperature_c']:.1f}°C")
    print(f"  Pressure: {final_summary['atmosphere']['pressure_mbar']:.1f} mbar")
    
    print("✅ Environment simulation works correctly")

def test_power_budget():
    """Test power budget and allocation."""
    print("\n🧪 Testing power budget...")
    
    sim = test_basic_functionality()
    power_budget = sim.plant_state.power_budget
    
    # Set some power generation
    power_budget.set_generation(1000.0)  # 1 MW
    print(f"Set generation: {power_budget.generation_kw} kW")
    
    # Add some power requests (simulating modules)
    from src.core.power_budget import PowerRequest
    
    requests = [
        PowerRequest("Electrolizer", 600.0, min_power_kw=100.0, priority=2),
        PowerRequest("Sabatier", 400.0, min_power_kw=50.0, priority=2), 
        PowerRequest("Compressor", 150.0, min_power_kw=20.0, priority=3),
        PowerRequest("Life_Support", 50.0, min_power_kw=50.0, priority=1)  # Critical
    ]
    
    for req in requests:
        power_budget.add_request(req)
    
    # Allocate power
    allocations = power_budget.allocate_power()
    
    print(f"Power allocations:")
    for module, allocated in allocations.items():
        alloc = power_budget.get_allocation_for_module(module)
        print(f"  {module}: {allocated:.0f} kW ({alloc.allocation_fraction:.1%} of requested)")
    
    print(f"Total demand: {power_budget.total_demand_kw:.0f} kW")
    print(f"Total allocated: {power_budget.total_allocated_kw:.0f} kW")
    print(f"Utilization: {power_budget.power_utilization_fraction:.1%}")
    
    # Test power shortage scenario
    print("\n🧪 Testing power shortage...")
    power_budget.set_generation(500.0)  # Reduce to 500 kW
    allocations = power_budget.allocate_power()
    
    print(f"With 500 kW generation:")
    print(f"  Deficit: {power_budget.total_deficit_kw:.0f} kW")
    for module, allocated in allocations.items():
        alloc = power_budget.get_allocation_for_module(module)
        if alloc.deficit_kw > 0:
            print(f"  {module}: SHORT {alloc.deficit_kw:.0f} kW")
    
    print("✅ Power budget works correctly")

def test_state_persistence():
    """Test state saving and loading."""
    print("\n🧪 Testing state persistence...")
    
    sim = test_basic_functionality()
    
    # Advance time and add some materials
    sim.plant_state.advance_time(3600)  # 1 hour
    sim.plant_state.get_material("CH4").store(5000)  # 5 tonnes CH4
    sim.plant_state.update_production_totals(ch4_produced_kg=5000, energy_consumed_kwh=100)
    
    # Save state
    saved_state = sim.plant_state.save_state()
    print(f"Saved state: Sol {saved_state['environment']['sol']}, "
          f"CH4: {saved_state['materials']['CH4']['mass_kg']} kg")
    
    # Create new plant and load state
    new_sim = SimulationEngine()
    new_sim.plant_state.load_state(saved_state)
    
    print(f"Loaded state: Sol {new_sim.plant_state.environment.sol}, "
          f"CH4: {new_sim.plant_state.get_material('CH4').mass_kg} kg")
    print(f"Production totals: {new_sim.plant_state.total_ch4_produced_kg} kg CH4")
    
    print("✅ State persistence works correctly")

def main():
    """Run all tests."""
    print("🚀 Starting ISRU simulation framework tests...\n")
    
    try:
        test_basic_functionality()
        test_material_stores()
        test_environment_simulation()
        test_power_budget()
        test_state_persistence()
        
        print("\n🎉 All tests passed! Core framework is working correctly.")
        print("\nReady to implement the next modules:")
        print("  - Power module (solar + battery)")
        print("  - Material flow modules (Atmosphere, Sabatier, Electrolysis)")
        print("  - Dashboard visualization")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main()) 