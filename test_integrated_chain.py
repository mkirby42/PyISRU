#!/usr/bin/env python3
"""
Quick test to verify atmosphere intake + Sabatier reactor integration.
Tests CO₂ flow from intake to reactor.
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
from src.modules.sabatier_reactor import SabatierReactorModule

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_integrated_chain():
    """Test atmosphere intake + Sabatier reactor integration."""
    print("🧪 Testing integrated ISRU chain (Atmosphere → Sabatier)...")
    
    # Create simulation
    config = SimulationConfig(timestep_s=300.0)  # 5-minute timesteps
    sim = SimulationEngine(config)
    sim.set_location(latitude_deg=18.4, longitude_deg=77.5, altitude_m=-2500)  # Jezero Crater
    
    # Add modules - scaled for realistic power demonstration
    env_module = EnvironmentModule()
    power_module = PowerModule(solar_array_area_m2=15000.0, battery_capacity_kwh=5000.0)  # ~1770 kW solar
    intake_module = AtmosphereIntakeModule(target_flow_rate_kg_hr=20.0)  # 20 kg/hr CO₂
    sabatier_module = SabatierReactorModule(target_ch4_rate_kg_hr=5.0)  # 5 kg/hr CH₄ (scaled demo)
    
    sim.add_module(env_module)
    sim.add_module(power_module)
    sim.add_module(intake_module)
    sim.add_module(sabatier_module)
    
    # Add some initial H₂ for the Sabatier reaction
    sim.plant_state.get_material("H2").store(50.0)  # 50 kg H₂ to start (scaled)
    
    print(f"Initial state:")
    print(f"  CO₂: {sim.plant_state.get_material('CO2').mass_kg:.0f} kg")
    print(f"  H₂: {sim.plant_state.get_material('H2').mass_kg:.0f} kg")
    print(f"  CH₄: {sim.plant_state.get_material('CH4').mass_kg:.0f} kg")
    print(f"  H₂O: {sim.plant_state.get_material('H2O').mass_kg:.0f} kg")
    
    # Run for several hours
    print(f"\nRunning integrated chain test...")
    for i in range(24):  # 2 hours at 5-minute timesteps
        step_result = sim._execute_timestep()
        
        intake_data = step_result["module_results"]["AtmosphereIntake"]
        sabatier_data = step_result["module_results"]["SabatierReactor"]
        
        if i % 6 == 0:  # Every 30 minutes
            time_min = i * 5
            materials = sim.plant_state.get_material_inventory()
            
            print(f"  {time_min:3d}min: CO₂ in {intake_data['co2_output_kg_hr']:4.0f} kg/hr, "
                  f"CH₄ out {sabatier_data['ch4_production_kg_hr']:4.0f} kg/hr, "
                  f"Stores: CO₂ {materials['CO2']:5.0f} kg, "
                  f"H₂ {materials['H2']:4.0f} kg, "
                  f"CH₄ {materials['CH4']:4.0f} kg")
    
    # Final summary
    final_materials = sim.plant_state.get_material_inventory()
    print(f"\nFinal state after 2 hours:")
    print(f"  CO₂: {final_materials['CO2']:.0f} kg")
    print(f"  H₂: {final_materials['H2']:.0f} kg")
    print(f"  CH₄: {final_materials['CH4']:.0f} kg")
    print(f"  H₂O: {final_materials['H2O']:.0f} kg")
    
    # Check if the chain is working
    ch4_produced = final_materials['CH4']
    h2o_produced = final_materials['H2O']
    
    if ch4_produced > 5 and h2o_produced > 10:  # Should produce some CH₄ and H₂O (scaled)
        print("✅ Integrated chain working: CO₂ → CH₄ + H₂O")
    else:
        print("❌ Chain not working as expected")
        print(f"   Expected: CH₄ > 5 kg, H₂O > 10 kg (scaled demo)")
        print(f"   Actual: CH₄ = {ch4_produced:.1f} kg, H₂O = {h2o_produced:.1f} kg")
    
    # Show power consumption
    total_power = (intake_data['power_consumption_kw'] + 
                  sabatier_data['power_consumption_kw'])
    print(f"\nPower consumption:")
    print(f"  Atmosphere Intake: {intake_data['power_consumption_kw']:.0f} kW")
    print(f"  Sabatier Reactor: {sabatier_data['power_consumption_kw']:.0f} kW")
    print(f"  Total ISRU: {total_power:.0f} kW")
    print(f"  Solar capacity: {power_module.solar_array_area_m2 * 590 * 0.2 / 1000:.0f} kW")
    
    return sim

if __name__ == "__main__":
    test_integrated_chain() 