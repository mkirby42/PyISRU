"""
ISRU (In-Situ Resource Utilization) Simulation Module
Extracted from the main Flask app for better organization
"""

import threading
import time
import logging
from datetime import datetime

# Import our simulation modules
import sys
sys.path.append('src')
from simulation_engine import SimulationEngine
from core.plant_state import PlantState
from modules.environment import EnvironmentModule
from modules.power import PowerModule
from modules.atmosphere_intake import AtmosphereIntakeModule
from modules.electrolysis import ElectrolysisModule
from modules.sabatier_reactor import SabatierReactorModule

class ISRUSimulationManager:
    """Manages the ISRU simulation state and execution"""
    
    def __init__(self):
        self.current_simulation = None
        self.simulation_thread = None
        self.simulation_data = []
        self.simulation_running = False
    
    def run_simulation(self, params):
        """
        Start a new ISRU simulation with given parameters
        
        Args:
            params (dict): Simulation parameters including:
                - speed: simulation speed multiplier
                - duration: duration in years
                - solar_array_area: solar array area in m²
                - battery_capacity: battery capacity in kWh
                - co2_intake_rate: CO₂ intake rate in kg/hr
                - h2_production_rate: H₂ production rate in kg/hr
                - ch4_production_rate: CH₄ production rate in kg/hr
                - ignore_temp_overage: whether to ignore temperature limits
        
        Returns:
            dict: Status response
        """
        if self.simulation_running:
            return {"error": "Simulation already running"}
        
        # Reset simulation data
        self.simulation_data = []
        self.simulation_running = True
        
        def run_sim():
            try:
                # Create new simulation with configurable modules
                engine = SimulationEngine()
                
                # Add all required modules with user-configured parameters
                logging.info(f"Initializing simulation with config: Solar={params['solar_array_area']}m², Battery={params['battery_capacity']}kWh")
                logging.info(f"Production targets: CO₂={params['co2_intake_rate']}, H₂={params['h2_production_rate']}, CH₄={params['ch4_production_rate']} kg/hr")
                
                engine.add_module(EnvironmentModule(ignore_temp_overage=params['ignore_temp_overage']))
                engine.add_module(PowerModule(
                    solar_array_area_m2=params['solar_array_area'],
                    battery_capacity_kwh=params['battery_capacity'],
                    ignore_temp_overage=params['ignore_temp_overage']
                ))
                engine.add_module(AtmosphereIntakeModule(
                    target_flow_rate_kg_hr=params['co2_intake_rate'],
                    ignore_temp_overage=params['ignore_temp_overage']
                ))
                engine.add_module(ElectrolysisModule(
                    target_h2_rate_kg_hr=params['h2_production_rate'],
                    ignore_temp_overage=params['ignore_temp_overage']
                )) 
                engine.add_module(SabatierReactorModule(
                    target_ch4_rate_kg_hr=params['ch4_production_rate'],
                    ignore_temp_overage=params['ignore_temp_overage']
                ))
                
                logging.info(f"All modules initialized. Beginning simulation with {len(engine.modules)} active modules")
                
                # Run simulation and collect data
                timesteps = int(params['duration'] * 365 * 24 * 60 / engine.timestep_minutes)
                logging.info(f"Simulation will run for {timesteps} timesteps ({params['duration']} Mars years)")
                
                step_count = 0
                for i in range(timesteps):
                    if not self.simulation_running:  # Check for pause/stop
                        logging.info(f"Simulation stopped by user after {step_count} steps")
                        break
                        
                    step_result = engine.step()
                    step_count += 1
                    
                    # Get modules by name (since modules is a list)
                    modules_dict = {m.name: m for m in engine.modules}
                    power_module = modules_dict.get('Power')
                    environment_module = modules_dict.get('Environment')
                    
                    # Collect data for visualization with correct property names
                    state_data = {
                        'time': engine.plant_state.current_time,
                        'power_available': engine.plant_state.power_budget.generation_kw,
                        'power_allocated': engine.plant_state.power_budget.total_allocated_kw,
                        'battery_level': getattr(power_module, 'battery_soc', 0) * getattr(power_module, 'battery_capacity_kwh', 0) if power_module else 0,
                        'ch4_stored': engine.plant_state.materials['CH4'].mass_kg,
                        'o2_stored': engine.plant_state.materials['O2'].mass_kg,
                        'h2_stored': engine.plant_state.materials['H2'].mass_kg,
                        'co2_stored': engine.plant_state.materials['CO2'].mass_kg,
                        'h2o_stored': engine.plant_state.materials['H2O'].mass_kg,
                        'solar_irradiance': engine.plant_state.environment.solar_irradiance_w_m2,
                        'temperature': engine.plant_state.environment.ambient_temperature_k,
                    }
                    
                    self.simulation_data.append(state_data)
                    
                    # Log periodic status for debugging
                    if step_count % 3600 == 0:  # Every hour of simulation time
                        logging.info(f"Step {step_count}: CH₄={state_data['ch4_stored']:.1f}kg, Power={state_data['power_available']:.1f}kW")
                    
                    # Sleep based on speed
                    time.sleep(0.01 / params['speed'])
                
                logging.info(f"Simulation completed after {step_count} steps. Final data points: {len(self.simulation_data)}")
                
            except Exception as e:
                logging.error(f"Simulation error after {len(self.simulation_data)} steps: {e}")
                logging.error(f"Error type: {type(e).__name__}")
                import traceback
                logging.error(f"Traceback: {traceback.format_exc()}")
            finally:
                self.simulation_running = False
                logging.info("Simulation thread terminated")
        
        self.simulation_thread = threading.Thread(target=run_sim)
        self.simulation_thread.start()
        
        return {"status": "started"}
    
    def pause_simulation(self):
        """Pause the running simulation"""
        self.simulation_running = False
        return {"status": "paused"}
    
    def reset_simulation(self):
        """Reset all simulation state"""
        # Stop any running simulation
        self.simulation_running = False
        
        # Wait for simulation thread to finish if it's running
        if self.simulation_thread and self.simulation_thread.is_alive():
            self.simulation_thread.join(timeout=2.0)  # Wait up to 2 seconds
        
        # Reset all simulation state
        self.current_simulation = None
        self.simulation_thread = None
        self.simulation_data = []
        self.simulation_running = False
        
        return {"status": "reset"}
    
    def get_simulation_data(self):
        """Get current simulation data and status"""
        return {
            "data": self.simulation_data,
            "running": self.simulation_running
        }

# Global instance for the Flask app to use
isru_manager = ISRUSimulationManager() 