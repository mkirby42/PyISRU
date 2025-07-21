#!/usr/bin/env python3
"""
Debug script to test simulation engine and see what data it produces
"""

import sys
import os
sys.path.append('src')

def test_simulation_engine():
    print("🔍 Testing SimulationEngine directly...")
    
    try:
        from simulation_engine import SimulationEngine
        print("✓ SimulationEngine imported successfully")
        
        # Create engine
        engine = SimulationEngine()
        print(f"✓ Engine created: {engine}")
        print(f"  - Timestep minutes: {engine.timestep_minutes}")
        print(f"  - Modules: {len(engine.modules)}")
        print(f"  - Plant state: {engine.plant_state}")
        
        # Check plant state structure
        print("\n🏭 Plant State Structure:")
        print(f"  - Current time: {engine.plant_state.current_time}")
        print(f"  - Has material_stores? {hasattr(engine.plant_state, 'material_stores')}")
        print(f"  - Has power_budget? {hasattr(engine.plant_state, 'power_budget')}")
        
        if hasattr(engine.plant_state, 'material_stores'):
            print(f"  - Material stores: {engine.plant_state.material_stores}")
        
        if hasattr(engine.plant_state, 'power_budget'):
            print(f"  - Power budget: {engine.plant_state.power_budget}")
        
        # Check if engine has a step method
        print(f"\n⚙️ Engine Methods:")
        print(f"  - Has step()? {hasattr(engine, 'step')}")
        print(f"  - Has _execute_timestep()? {hasattr(engine, '_execute_timestep')}")
        
        # Try to run one timestep
        print("\n🚀 Attempting one timestep...")
        
        if hasattr(engine, 'step'):
            try:
                engine.step()
                print("✓ engine.step() worked")
            except Exception as e:
                print(f"✗ engine.step() failed: {e}")
        
        if hasattr(engine, '_execute_timestep'):
            try:
                result = engine._execute_timestep()
                print("✓ engine._execute_timestep() worked")
                print(f"  Result keys: {list(result.keys()) if isinstance(result, dict) else type(result)}")
            except Exception as e:
                print(f"✗ engine._execute_timestep() failed: {e}")
        
        # Check what data we can extract
        print("\n📊 Available Data:")
        try:
            state_data = {
                'time': getattr(engine.plant_state, 'current_time', None),
                'modules_count': len(getattr(engine, 'modules', [])),
            }
            
            # Try to access power budget data
            if hasattr(engine.plant_state, 'power_budget'):
                pb = engine.plant_state.power_budget
                state_data['power_available'] = getattr(pb, 'available_power', None)
                state_data['power_allocated'] = getattr(pb, 'allocated_power', None)
            
            # Try to access material stores
            if hasattr(engine.plant_state, 'material_stores'):
                ms = engine.plant_state.material_stores
                state_data['material_stores'] = {k: getattr(v, 'current_mass', None) for k, v in ms.items()}
            
            print(f"  Extractable data: {state_data}")
            
        except Exception as e:
            print(f"✗ Data extraction failed: {e}")
            
    except ImportError as e:
        print(f"✗ Import failed: {e}")
    except Exception as e:
        print(f"✗ Unexpected error: {e}")

def test_with_modules():
    print("\n\n🧩 Testing with modules (like test file)...")
    
    try:
        from simulation_engine import SimulationEngine, SimulationConfig
        from modules.environment import EnvironmentModule
        from modules.power import PowerModule
        from modules.atmosphere_intake import AtmosphereIntakeModule
        from modules.sabatier_reactor import SabatierReactorModule
        from modules.electrolysis import ElectrolysisModule
        
        print("✓ All modules imported successfully")
        
        # Create simulation like in test file
        config = SimulationConfig(timestep_s=600.0)
        sim = SimulationEngine(config)
        sim.set_location(latitude_deg=18.4, longitude_deg=77.5, altitude_m=-2500)
        
        # Add modules
        env_module = EnvironmentModule()
        power_module = PowerModule(solar_array_area_m2=1000.0, battery_capacity_kwh=500.0)
        intake_module = AtmosphereIntakeModule(target_flow_rate_kg_hr=10.0)
        sabatier_module = SabatierReactorModule(target_ch4_rate_kg_hr=2.0)
        electrolysis_module = ElectrolysisModule(target_h2_rate_kg_hr=1.0)
        
        sim.add_module(env_module)
        sim.add_module(power_module)
        sim.add_module(intake_module)
        sim.add_module(sabatier_module)
        sim.add_module(electrolysis_module)
        
        print(f"✓ Setup complete - {len(sim.modules)} modules")
        
        # Try one timestep
        print("\n🚀 Running one timestep...")
        step_result = sim._execute_timestep()
        print("✓ Timestep successful!")
        print(f"  Result type: {type(step_result)}")
        if isinstance(step_result, dict):
            print(f"  Keys: {list(step_result.keys())}")
            
            # Extract module results
            if 'module_results' in step_result:
                module_results = step_result['module_results']
                print(f"  Module results: {list(module_results.keys())}")
                for module_name, result in module_results.items():
                    print(f"    {module_name}: {list(result.keys()) if isinstance(result, dict) else type(result)}")
        
        # Extract data for dashboard
        print("\n📊 Extracting dashboard data...")
        module_results = step_result.get("module_results", {})
        env_data = module_results.get("Environment", {})
        power_data = module_results.get("Power", {})
        
        dashboard_data = {
            'time': sim.plant_state.current_time,
            'power_available': step_result.get("power_generation_kw", 0),
            'power_allocated': step_result.get("power_allocated_kw", 0),
            'battery_level': power_data.get("battery_soc", 0) * power_module.battery_capacity_kwh,
            'ch4_stored': sim.plant_state.material_stores.get('CH4', {}).get('current_mass', 0) if hasattr(sim.plant_state, 'material_stores') else 0,
            'o2_stored': sim.plant_state.material_stores.get('O2', {}).get('current_mass', 0) if hasattr(sim.plant_state, 'material_stores') else 0,
            'solar_irradiance': env_data.get("solar_irradiance_w_m2", 0),
            'temperature': env_data.get("ambient_temperature_k", 220),
        }
        
        print(f"✓ Dashboard data: {dashboard_data}")
        
        # Run a few more timesteps
        print("\n🔄 Running 5 more timesteps...")
        for i in range(5):
            step_result = sim._execute_timestep()
            dashboard_data = {
                'time': sim.plant_state.current_time,
                'power_available': step_result.get("power_generation_kw", 0),
                'power_allocated': step_result.get("power_allocated_kw", 0),
                'ch4_stored': sim.plant_state.material_stores.get('CH4', {}).get('current_mass', 0) if hasattr(sim.plant_state, 'material_stores') else 0,
                'o2_stored': sim.plant_state.material_stores.get('O2', {}).get('current_mass', 0) if hasattr(sim.plant_state, 'material_stores') else 0,
            }
            print(f"  Step {i+1}: Power: {dashboard_data['power_available']:.1f}kW, CH4: {dashboard_data['ch4_stored']:.1f}kg, O2: {dashboard_data['o2_stored']:.1f}kg")
        
    except Exception as e:
        print(f"✗ Module test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_simulation_engine()
    test_with_modules() 