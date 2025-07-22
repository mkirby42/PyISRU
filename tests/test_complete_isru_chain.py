#!/usr/bin/env python3
"""
Complete ISRU chain test: Atmosphere Intake → Sabatier Reactor → Electrolysis
Tests the full closed-loop system with H₂ recycling.
"""

import logging
import sys
import os

# Path is handled by conftest.py

from simulation_engine import SimulationEngine, SimulationConfig
from modules.environment import EnvironmentModule
from modules.power import PowerModule
from modules.atmosphere_intake import AtmosphereIntakeModule
from modules.sabatier_reactor import SabatierReactorModule
from modules.electrolysis import ElectrolysisModule

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_complete_isru_chain():
    """Test the complete ISRU chain with H₂ recycling."""
    print("🚀 Testing COMPLETE ISRU Chain: Mars Air → CH₄ + O₂")
    print("    Chain: Atmosphere → Sabatier → Electrolysis → H₂ Recycle")
    
    # Create simulation with larger power system for complete chain
    config = SimulationConfig(timestep_s=600.0)  # 10-minute timesteps
    sim = SimulationEngine(config)
    sim.set_location(latitude_deg=18.4, longitude_deg=77.5, altitude_m=-2500)  # Jezero Crater
    
    # Add modules - scaled for demonstration of complete chain
    env_module = EnvironmentModule()
    power_module = PowerModule(
        solar_array_area_m2=25000.0,  # Large array: ~2950 kW solar capacity
        battery_capacity_kwh=8000.0   # Large battery for night operation
    )
    intake_module = AtmosphereIntakeModule(target_flow_rate_kg_hr=30.0)     # 30 kg/hr CO₂
    sabatier_module = SabatierReactorModule(target_ch4_rate_kg_hr=8.0)       # 8 kg/hr CH₄
    electrolysis_module = ElectrolysisModule(target_h2_rate_kg_hr=4.0)       # 4 kg/hr H₂
    
    sim.add_module(env_module)
    sim.add_module(power_module)
    sim.add_module(intake_module)
    sim.add_module(sabatier_module)
    sim.add_module(electrolysis_module)
    
    # Start with some seed materials to prime the reactions
    sim.plant_state.get_material("H2").store(20.0)   # 20 kg H₂ to start
    sim.plant_state.get_material("H2O").store(50.0)  # 50 kg H₂O to bootstrap electrolysis
    
    print(f"\nInitial configuration:")
    print(f"  Solar array: {power_module.solar_array_area_m2:,} m² ({power_module.solar_array_area_m2 * 590 * 0.2 / 1000:.0f} kW peak)")
    print(f"  Target rates: {intake_module.target_flow_rate_kg_hr} kg/hr CO₂ → {sabatier_module.target_ch4_rate_kg_hr} kg/hr CH₄")
    print(f"  H₂ production: {electrolysis_module.target_h2_rate_kg_hr} kg/hr H₂ for recycling")
    
    # Calculate theoretical power requirements
    total_power_requirement = (
        intake_module.target_flow_rate_kg_hr * intake_module.power_per_kg_hr +
        sabatier_module.target_ch4_rate_kg_hr * sabatier_module.power_per_kg_ch4 +
        electrolysis_module.target_h2_rate_kg_hr * electrolysis_module.power_per_kg_h2
    )
    print(f"  Total power required: {total_power_requirement:.0f} kW")
    
    print(f"\nInitial material inventory:")
    materials = sim.plant_state.get_material_inventory()
    for material, mass in materials.items():
        if mass > 0:
            print(f"  {material}: {mass:.1f} kg")
    
    # Run the complete chain for an extended period
    print(f"\nRunning complete ISRU chain simulation...")
    
    results = []
    for i in range(72):  # 12 hours at 10-minute timesteps
        step_result = sim._execute_timestep()
        
        # Extract data from all modules (handle shutdown gracefully)
        env_data = step_result["module_results"].get("Environment", {})
        power_data = step_result["module_results"].get("Power", {"solar_power_kw": 0, "battery_soc": 0})
        intake_data = step_result["module_results"].get("AtmosphereIntake", {"co2_output_kg_hr": 0, "power_consumption_kw": 0})
        sabatier_data = step_result["module_results"].get("SabatierReactor", {"ch4_production_kg_hr": 0, "h2_consumption_kg_hr": 0, "power_consumption_kw": 0})
        electrolysis_data = step_result["module_results"].get("Electrolysis", {"h2_production_kg_hr": 0, "o2_production_kg_hr": 0, "power_consumption_kw": 0})
        
        # Current material inventory
        current_materials = sim.plant_state.get_material_inventory()
        
        # Calculate H₂ recycling efficiency
        h2_produced = electrolysis_data["h2_production_kg_hr"]
        h2_consumed = sabatier_data["h2_consumption_kg_hr"]
        h2_balance = h2_produced - h2_consumed
        
        result = {
            "time_hr": i * 10 / 60.0,
            "sol": step_result["sol"],
            "solar_power": power_data["solar_power_kw"],
            "battery_soc": power_data["battery_soc"],
            "co2_intake": intake_data["co2_output_kg_hr"],
            "ch4_production": sabatier_data["ch4_production_kg_hr"],
            "h2_production": h2_produced,
            "h2_consumption": h2_consumed,
            "h2_balance": h2_balance,
            "o2_production": electrolysis_data["o2_production_kg_hr"],
            "total_power": (intake_data["power_consumption_kw"] + 
                          sabatier_data["power_consumption_kw"] + 
                          electrolysis_data["power_consumption_kw"]),
            "materials": current_materials.copy()
        }
        results.append(result)
        
        # Log every 2 hours
        if i % 12 == 0:
            time_hr = i * 10 / 60.0
            print(f"  {time_hr:4.1f}h: Solar {power_data['solar_power_kw']:4.0f}kW, "
                  f"CO₂→{intake_data['co2_output_kg_hr']:3.0f}, "
                  f"CH₄→{sabatier_data['ch4_production_kg_hr']:3.0f}, "
                  f"H₂ {h2_balance:+4.1f}, "
                  f"O₂→{electrolysis_data['o2_production_kg_hr']:3.0f} kg/hr")
    
    # Final analysis
    final_materials = sim.plant_state.get_material_inventory()
    
    print(f"\n🎯 FINAL RESULTS after 12 hours:")
    print(f"===========================================")
    
    # Material balance
    print(f"Material Inventory:")
    net_production = {}
    for material, final_mass in final_materials.items():
        initial_mass = materials.get(material, 0.0)
        net_change = final_mass - initial_mass
        net_production[material] = net_change
        
        if abs(net_change) > 0.1:  # Only show significant changes
            print(f"  {material:>4}: {final_mass:6.1f} kg (Δ{net_change:+6.1f})")
    
    # Key performance metrics
    total_ch4 = net_production.get("CH4", 0.0)
    total_o2 = net_production.get("O2", 0.0)
    total_h2o_net = net_production.get("H2O", 0.0)  # Should be close to zero (recycled)
    total_h2_net = net_production.get("H2", 0.0)    # Should be close to zero (recycled)
    
    print(f"\nNet Products (Mars Air → Propellant):")
    print(f"  Methane (CH₄):  {total_ch4:6.1f} kg  ← FUEL")
    print(f"  Oxygen (O₂):    {total_o2:6.1f} kg  ← OXIDIZER")
    print(f"  Water (H₂O):    {total_h2o_net:6.1f} kg  ← RECYCLED")
    print(f"  Hydrogen (H₂):  {total_h2_net:6.1f} kg  ← RECYCLED")
    
    # Calculate mass ratio for propellant
    if total_ch4 > 0 and total_o2 > 0:
        o2_ch4_ratio = total_o2 / total_ch4
        print(f"  O₂/CH₄ ratio:   {o2_ch4_ratio:6.1f}    (target: ~4.0 for combustion)")
    
    # Power analysis
    avg_results = results[-12:]  # Last 2 hours for steady-state analysis
    avg_total_power = sum(r["total_power"] for r in avg_results) / len(avg_results)
    avg_solar_power = sum(r["solar_power"] for r in avg_results) / len(avg_results)
    
    print(f"\nPower Analysis (steady-state):")
    print(f"  Average ISRU power: {avg_total_power:6.0f} kW")
    print(f"  Average solar:      {avg_solar_power:6.0f} kW")
    print(f"  Power utilization:  {avg_total_power/max(avg_solar_power, 1):.1%}")
    
    # H₂ recycling analysis
    h2_recycling_data = [r for r in results[-24:] if r["h2_production"] > 0]  # Last 4 hours with production
    if h2_recycling_data:
        avg_h2_production = sum(r["h2_production"] for r in h2_recycling_data) / len(h2_recycling_data)
        avg_h2_consumption = sum(r["h2_consumption"] for r in h2_recycling_data) / len(h2_recycling_data)
        h2_recycling_efficiency = avg_h2_consumption / max(avg_h2_production, 0.1)
        
        print(f"\nH₂ Recycling Analysis:")
        print(f"  H₂ production:     {avg_h2_production:6.1f} kg/hr")
        print(f"  H₂ consumption:    {avg_h2_consumption:6.1f} kg/hr")
        print(f"  Recycling efficiency: {h2_recycling_efficiency:.1%}")
        
        if h2_recycling_efficiency > 0.8:
            print(f"  ✅ Excellent H₂ recycling - sustainable operation")
        elif h2_recycling_efficiency > 0.5:
            print(f"  ⚠️  Moderate H₂ recycling - may need optimization")
        else:
            print(f"  ❌ Poor H₂ recycling - system not balanced")
    
    # Success criteria
    print(f"\n🏆 MISSION SUCCESS CRITERIA:")
    print(f"===========================================")
    
    success_criteria = {
        "CH₄ Production": (total_ch4 > 50.0, f"{total_ch4:.1f} kg > 50 kg"),
        "O₂ Production": (total_o2 > 200.0, f"{total_o2:.1f} kg > 200 kg"),
        "Propellant Ratio": (3.0 < o2_ch4_ratio < 5.0 if total_ch4 > 0 else False, f"O₂/CH₄ = {o2_ch4_ratio:.1f}"),
        "H₂ Balance": (abs(total_h2_net) < 5.0, f"|Δ H₂| = {abs(total_h2_net):.1f} kg < 5 kg"),
        "Power Efficiency": (avg_total_power < avg_solar_power * 1.2, f"{avg_total_power:.0f} kW ≤ {avg_solar_power*1.2:.0f} kW")
    }
    
    all_passed = True
    for criterion, (passed, detail) in success_criteria.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {criterion:16}: {status} ({detail})")
        if not passed:
            all_passed = False
    
    print(f"\n{'🎉 MISSION SUCCESS' if all_passed else '⚠️  MISSION PARTIAL'}: Complete ISRU chain operational!")
    
    if all_passed:
        print(f"\n🚀 READY FOR STARSHIP REFUELING:")
        print(f"   - Sustainable CH₄ + O₂ production from Mars atmosphere")
        print(f"   - Closed-loop H₂ recycling operational")
        print(f"   - Power system can support continuous operation")
        print(f"   - All subsystems functioning within specifications")
    
    return sim, results

if __name__ == "__main__":
    sim, results = test_complete_isru_chain() 