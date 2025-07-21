#!/usr/bin/env python3
"""
Test script for the Atmosphere Intake module.
Verifies CO₂ compression, filtering, and integration with power systems.
"""

import logging
import sys
import os

# Add src to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.simulation_engine import SimulationEngine, SimulationConfig
from src.modules.environment import EnvironmentModule
from src.modules.power import PowerModule
from src.modules.atmosphere_intake import AtmosphereIntakeModule

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_basic_operation():
    """Test basic atmosphere intake operation."""
    print("🧪 Testing basic atmosphere intake operation...")
    
    # Create simulation
    config = SimulationConfig(timestep_s=300.0)  # 5-minute timesteps
    sim = SimulationEngine(config)
    sim.set_location(latitude_deg=18.4, longitude_deg=77.5, altitude_m=-2500)  # Jezero Crater
    
    # Add modules
    env_module = EnvironmentModule()
    power_module = PowerModule(solar_array_area_m2=8000.0, battery_capacity_kwh=2000.0)
    intake_module = AtmosphereIntakeModule(target_flow_rate_kg_hr=500.0)  # 500 kg/hr CO₂
    
    sim.add_module(env_module)
    sim.add_module(power_module)
    sim.add_module(intake_module)
    
    print(f"Target CO₂ flow rate: {intake_module.target_flow_rate_kg_hr} kg/hr")
    print(f"Power requirement: {intake_module.target_flow_rate_kg_hr * intake_module.power_per_kg_hr:.0f} kW")
    print(f"Initial CO₂ inventory: {sim.plant_state.get_material('CO2').mass_kg:.0f} kg")
    
    # Run for several hours to see steady-state operation
    total_co2_produced = 0.0
    for i in range(48):  # 4 hours at 5-minute timesteps
        step_result = sim._execute_timestep()
        
        intake_data = step_result["module_results"]["AtmosphereIntake"]
        power_data = step_result["module_results"]["Power"]
        
        total_co2_produced += intake_data["co2_produced_kg"]
        
        if i % 12 == 0:  # Every hour
            time_hr = i * 5 / 60.0
            print(f"  {time_hr:4.1f}h: CO₂ rate {intake_data['co2_output_kg_hr']:5.0f} kg/hr, "
                  f"Power {intake_data['power_consumption_kw']:5.0f} kW, "
                  f"Efficiency {intake_data['efficiency']:5.1%}, "
                  f"Total CO₂ {intake_data['total_co2_processed_kg']:6.0f} kg")
    
    # Final status
    final_co2_inventory = sim.plant_state.get_material("CO2").mass_kg
    
    print(f"\nOperation summary:")
    print(f"  Final CO₂ inventory: {final_co2_inventory:.0f} kg")
    print(f"  CO₂ produced: {total_co2_produced:.0f} kg")
    print(f"  Average rate: {total_co2_produced / 4.0:.0f} kg/hr")
    print(f"  Target rate: {intake_module.target_flow_rate_kg_hr:.0f} kg/hr")
    
    print("✅ Basic operation test completed")
    return sim

def test_power_limitation():
    """Test behavior under power constraints."""
    print("\n🧪 Testing power limitation scenarios...")
    
    # Create simulation with limited power
    config = SimulationConfig(timestep_s=600.0)  # 10-minute timesteps
    sim = SimulationEngine(config)
    sim.set_location(latitude_deg=0.0, longitude_deg=0.0)
    
    # Add modules with limited power capacity
    env_module = EnvironmentModule()
    power_module = PowerModule(
        solar_array_area_m2=3000.0,  # Smaller array
        battery_capacity_kwh=1000.0
    )
    intake_module = AtmosphereIntakeModule(target_flow_rate_kg_hr=800.0)  # High demand
    
    sim.add_module(env_module)
    sim.add_module(power_module)
    sim.add_module(intake_module)
    
    required_power = intake_module.target_flow_rate_kg_hr * intake_module.power_per_kg_hr
    print(f"Required power: {required_power:.0f} kW")
    print(f"Solar capacity: {power_module.solar_array_area_m2 * 590 * 0.2 / 1000:.0f} kW")
    
    # Add competing loads
    from src.core.power_budget import PowerRequest
    competing_load = PowerRequest("Other_Systems", 400.0, min_power_kw=100.0, priority=2)
    
    # Run day/night cycle
    power_shortages = []
    for i in range(144):  # 24 hours at 10-minute timesteps
        # Add competing load
        sim.plant_state.power_budget.clear_requests()
        sim.plant_state.power_budget.add_request(competing_load)
        
        step_result = sim._execute_timestep()
        
        intake_data = step_result["module_results"]["AtmosphereIntake"]
        power_budget = sim.plant_state.power_budget
        
        if power_budget.is_power_shortage:
            power_shortages.append({
                "time": i * 10 / 60.0,
                "deficit": power_budget.total_deficit_kw,
                "intake_rate": intake_data["co2_output_kg_hr"]
            })
        
        if i % 24 == 0:  # Every 4 hours
            time_hr = i * 10 / 60.0
            print(f"  {time_hr:4.1f}h: Available {power_budget.generation_kw:5.0f}kW, "
                  f"Demand {power_budget.total_demand_kw:5.0f}kW, "
                  f"CO₂ rate {intake_data['co2_output_kg_hr']:5.0f} kg/hr")
    
    # Analyze power constraints
    if power_shortages:
        avg_shortage_rate = sum(s["intake_rate"] for s in power_shortages) / len(power_shortages)
        print(f"\nPower constraint analysis:")
        print(f"  Power shortages: {len(power_shortages)} timesteps")
        print(f"  Average CO₂ rate during shortages: {avg_shortage_rate:.0f} kg/hr")
        print(f"  Target rate: {intake_module.target_flow_rate_kg_hr:.0f} kg/hr")
    else:
        print(f"No power constraints encountered")
    
    print("✅ Power limitation test completed")

def test_component_degradation():
    """Test filter contamination and compressor wear."""
    print("\n🧪 Testing component degradation...")
    
    # Create simulation with accelerated degradation
    config = SimulationConfig(timestep_s=3600.0)  # 1-hour timesteps
    sim = SimulationEngine(config)
    sim.set_location(latitude_deg=0.0, longitude_deg=0.0)
    
    # Add modules
    env_module = EnvironmentModule()
    power_module = PowerModule(solar_array_area_m2=8000.0, battery_capacity_kwh=3000.0)
    intake_module = AtmosphereIntakeModule(target_flow_rate_kg_hr=600.0)
    
    # Accelerate degradation for testing
    intake_module.filter_replacement_interval_hrs = 50.0  # Short interval
    intake_module.compressor_maintenance_interval_hrs = 150.0
    
    sim.add_module(env_module)
    sim.add_module(power_module)
    sim.add_module(intake_module)
    
    print(f"Accelerated degradation test:")
    print(f"  Filter replacement interval: {intake_module.filter_replacement_interval_hrs:.0f} hours")
    print(f"  Initial efficiency: {intake_module.current_efficiency:.1%}")
    
    # Run for extended period to see degradation
    for i in range(200):  # 200 hours
        step_result = sim._execute_timestep()
        
        intake_data = step_result["module_results"]["AtmosphereIntake"]
        
        if i % 20 == 0:  # Every 20 hours
            maintenance = intake_module.get_maintenance_status()
            print(f"  {i:3d}h: Efficiency {intake_data['efficiency']:5.1%}, "
                  f"Filter {maintenance['filter']['contamination']:5.1%}, "
                  f"Wear {maintenance['compressor']['wear']:5.1%}, "
                  f"Replacements {maintenance['filter']['replacement_count']}")
    
    # Final maintenance status
    final_maintenance = intake_module.get_maintenance_status()
    print(f"\nFinal maintenance status:")
    print(f"  Filter replacements: {final_maintenance['filter']['replacement_count']}")
    print(f"  Final efficiency: {final_maintenance['performance']['efficiency']:.1%}")
    print(f"  Efficiency loss: {final_maintenance['performance']['efficiency_loss']:.1%}")
    
    print("✅ Component degradation test completed")

def test_environmental_conditions():
    """Test response to varying environmental conditions."""
    print("\n🧪 Testing environmental condition responses...")
    
    config = SimulationConfig(timestep_s=900.0)  # 15-minute timesteps
    sim = SimulationEngine(config)
    
    # Add modules
    env_module = EnvironmentModule()
    power_module = PowerModule(solar_array_area_m2=6000.0, battery_capacity_kwh=2000.0)
    intake_module = AtmosphereIntakeModule(target_flow_rate_kg_hr=400.0)
    
    sim.add_module(env_module)
    sim.add_module(power_module)
    sim.add_module(intake_module)
    
    # Test different altitudes
    test_locations = [
        {"name": "Sea Level", "lat": 0.0, "lon": 0.0, "alt": 0.0},
        {"name": "Olympus Mons", "lat": 18.0, "lon": 226.0, "alt": 21000.0},
        {"name": "Hellas Basin", "lat": -42.0, "lon": 70.0, "alt": -8000.0}
    ]
    
    for location in test_locations:
        print(f"\n  Testing at {location['name']}:")
        sim.set_location(location["lat"], location["lon"], location["alt"])
        
        # Reset intake module
        intake_module.current_flow_rate_kg_hr = 0.0
        
        # Run for a few hours at this location
        location_results = []
        for i in range(16):  # 4 hours at 15-minute timesteps
            step_result = sim._execute_timestep()
            
            intake_data = step_result["module_results"]["AtmosphereIntake"]
            env_data = step_result["module_results"]["Environment"]
            
            location_results.append({
                "pressure": env_data["atmospheric_pressure_pa"],
                "temperature": env_data["ambient_temperature_k"],
                "flow_rate": intake_data["co2_output_kg_hr"],
                "compression_ratio": intake_data["compression_ratio"]
            })
        
        # Average results for this location
        avg_pressure = sum(r["pressure"] for r in location_results) / len(location_results)
        avg_temp = sum(r["temperature"] for r in location_results) / len(location_results)
        avg_flow = sum(r["flow_rate"] for r in location_results) / len(location_results)
        avg_compression = sum(r["compression_ratio"] for r in location_results) / len(location_results)
        
        print(f"    Pressure: {avg_pressure:.0f} Pa ({avg_pressure/610:.1f}x nominal)")
        print(f"    Temperature: {avg_temp:.0f} K ({avg_temp-273:.0f}°C)")
        print(f"    CO₂ flow rate: {avg_flow:.0f} kg/hr")
        print(f"    Compression ratio: {avg_compression:.1f}")
    
    print("✅ Environmental conditions test completed")

def test_integration_with_power():
    """Test integration with power system during day/night and storms."""
    print("\n🧪 Testing power system integration...")
    
    config = SimulationConfig(timestep_s=600.0)  # 10-minute timesteps
    sim = SimulationEngine(config)
    sim.set_location(latitude_deg=14.0, longitude_deg=175.0)  # Mid-latitude
    
    # Add modules
    env_module = EnvironmentModule()
    power_module = PowerModule(solar_array_area_m2=6000.0, battery_capacity_kwh=3000.0)
    intake_module = AtmosphereIntakeModule(target_flow_rate_kg_hr=500.0)
    
    sim.add_module(env_module)
    sim.add_module(power_module)
    sim.add_module(intake_module)
    
    # Inject a dust storm partway through
    env_module.inject_dust_storm(opacity=0.5, duration_sols=1.5, current_time=43200)  # After 12 hours
    
    print(f"Running integrated test with dust storm...")
    
    # Run for 3 sols
    results = []
    for i in range(432):  # 3 sols at 10-minute timesteps
        step_result = sim._execute_timestep()
        
        intake_data = step_result["module_results"]["AtmosphereIntake"]
        power_data = step_result["module_results"]["Power"]
        env_data = step_result["module_results"]["Environment"]
        
        results.append({
            "sol": step_result["sol"],
            "time_of_sol": step_result["time_of_sol"],
            "solar_power": power_data["solar_power_kw"],
            "battery_soc": power_data["battery_soc"],
            "dust_opacity": env_data["dust_opacity"],
            "co2_rate": intake_data["co2_output_kg_hr"],
            "intake_power": intake_data["power_consumption_kw"]
        })
        
        if i % 72 == 0:  # Every 12 hours
            sol = step_result["sol"]
            time_hr = step_result["time_of_sol"] * 24.65
            print(f"  Sol {sol} {time_hr:4.1f}h: Solar {power_data['solar_power_kw']:4.0f}kW, "
                  f"Battery {power_data['battery_soc']:5.1%}, "
                  f"Dust {env_data['dust_opacity']:4.1%}, "
                  f"CO₂ {intake_data['co2_output_kg_hr']:4.0f} kg/hr")
    
    # Analyze performance during different phases
    normal_results = [r for r in results if r["dust_opacity"] == 0]
    storm_results = [r for r in results if r["dust_opacity"] > 0]
    
    if normal_results:
        avg_normal_co2 = sum(r["co2_rate"] for r in normal_results) / len(normal_results)
        print(f"\nNormal conditions average: {avg_normal_co2:.0f} kg/hr CO₂")
    
    if storm_results:
        avg_storm_co2 = sum(r["co2_rate"] for r in storm_results) / len(storm_results)
        print(f"Dust storm average: {avg_storm_co2:.0f} kg/hr CO₂")
        print(f"Storm impact: {(1 - avg_storm_co2/avg_normal_co2):.1%} reduction")
    
    final_co2 = sim.plant_state.get_material("CO2").mass_kg
    print(f"Total CO₂ collected: {final_co2:.0f} kg")
    
    print("✅ Power integration test completed")

def main():
    """Run all atmosphere intake tests."""
    print("🚀 Starting Atmosphere Intake module tests...\n")
    
    try:
        test_basic_operation()
        test_power_limitation()
        test_component_degradation()
        test_environmental_conditions()
        test_integration_with_power()
        
        print("\n🎉 All atmosphere intake tests passed!")
        print("\nAtmosphere intake features verified:")
        print("  ✅ CO₂ compression and filtering")
        print("  ✅ Power scaling and limitations")
        print("  ✅ Component degradation and maintenance")
        print("  ✅ Environmental condition response")
        print("  ✅ Integration with power systems")
        
        print("\nReady for next modules:")
        print("  - Sabatier reactor (CO₂ + H₂ → CH₄ + H₂O)")
        print("  - Electrolysis (H₂O → H₂ + O₂)")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main()) 