from typing import List, Dict, Any, Optional
import logging
import time
from dataclasses import dataclass

from core import PlantState, BaseModule

logger = logging.getLogger(__name__)

@dataclass
class SimulationConfig:
    """Configuration for simulation engine."""
    timestep_s: float = 60.0           # Default 1-minute timesteps
    max_sim_time_s: float = 2_592_000  # 30 sols = ~30 * 24.65 * 3600 seconds
    save_interval_s: float = 3600.0    # Save state every hour
    log_interval_s: float = 300.0      # Log status every 5 minutes
    auto_save_enabled: bool = True
    
class SimulationEngine:
    """
    Main simulation engine that orchestrates the ISRU plant operation.
    Manages module updates, power allocation, and state persistence.
    """
    
    def __init__(self, config: Optional[SimulationConfig] = None):
        self.config = config or SimulationConfig()
        self.plant_state = PlantState()
        self.modules: List[BaseModule] = []
        
        # Simulation control
        self.is_running: bool = False
        self.is_paused: bool = False
        self.target_end_time: float = 0.0
        
        # Statistics tracking
        self.simulation_steps: int = 0
        self.real_time_start: float = 0.0
        self.last_save_time: float = 0.0
        self.last_log_time: float = 0.0
        
        # Results storage
        self.timestep_results: List[Dict[str, Any]] = []
        
        # Configure timestep
        self.plant_state.timestep_s = self.config.timestep_s
    
    @property
    def timestep_minutes(self) -> float:
        """Get timestep in minutes for backward compatibility."""
        return self.config.timestep_s / 60.0
        
    def add_module(self, module: BaseModule):
        """Add a module to the simulation."""
        if module.name in [m.name for m in self.modules]:
            raise ValueError(f"Module with name '{module.name}' already exists")
        
        self.modules.append(module)
        logger.info(f"Added module: {module.name}")
    
    def remove_module(self, module_name: str) -> bool:
        """Remove a module by name. Returns True if found and removed."""
        for i, module in enumerate(self.modules):
            if module.name == module_name:
                del self.modules[i]
                logger.info(f"Removed module: {module_name}")
                return True
        return False
    
    def set_location(self, latitude_deg: float, longitude_deg: float, altitude_m: float = 0.0):
        """Set the plant location on Mars."""
        self.plant_state.set_location(latitude_deg, longitude_deg, altitude_m)
    
    def run_simulation(self, duration_sols: float = 30.0, speed_multiplier: float = 1.0) -> Dict[str, Any]:
        """
        Run the complete simulation for specified duration.
        
        Args:
            duration_sols: Simulation duration in Mars sols
            speed_multiplier: Speed multiplier (1.0 = real-time, 10.0 = 10x faster)
            
        Returns:
            Dictionary with simulation results and statistics
        """
        # Calculate target end time 
        sols_to_seconds = 88775.0  # Mars sol ≈ 24.65 Earth hours
        duration_seconds = duration_sols * sols_to_seconds
        self.target_end_time = self.plant_state.current_time + duration_seconds
        
        # Reset statistics
        self.simulation_steps = 0
        self.real_time_start = time.time()
        self.last_save_time = self.plant_state.current_time
        self.last_log_time = self.plant_state.current_time
        self.timestep_results.clear()
        
        logger.info(f"Starting simulation: {duration_sols:.1f} sols ({duration_seconds/3600:.1f} hours)")
        logger.info(f"Timestep: {self.config.timestep_s}s, Speed: {speed_multiplier:.1f}x")
        logger.info(f"Modules: {[m.name for m in self.modules]}")
        
        self.is_running = True
        
        try:
            while (self.plant_state.current_time < self.target_end_time and 
                   self.is_running):
                
                # Execute one simulation step
                step_result = self._execute_timestep()
                self.timestep_results.append(step_result)
                
                # Periodic logging
                if (self.plant_state.current_time - self.last_log_time >= 
                    self.config.log_interval_s):
                    self._log_status()
                    self.last_log_time = self.plant_state.current_time
                
                # Periodic saving
                if (self.config.auto_save_enabled and 
                    self.plant_state.current_time - self.last_save_time >= 
                    self.config.save_interval_s):
                    self._auto_save()
                    self.last_save_time = self.plant_state.current_time
                
                # Handle pausing
                while self.is_paused and self.is_running:
                    time.sleep(0.1)
                
                # Real-time pacing (if speed_multiplier < very large)
                if speed_multiplier < 100.0:
                    target_wall_time = self.config.timestep_s / speed_multiplier
                    time.sleep(max(0, target_wall_time - 0.001))  # Small buffer
        
        except KeyboardInterrupt:
            logger.info("Simulation interrupted by user")
        except Exception as e:
            logger.error(f"Simulation error: {e}")
            raise
        finally:
            self.is_running = False
        
        # Final statistics
        real_time_elapsed = time.time() - self.real_time_start
        sim_time_elapsed = self.plant_state.current_time - (self.target_end_time - duration_seconds)
        
        results = {
            "simulation_steps": self.simulation_steps,
            "sim_time_elapsed_s": sim_time_elapsed,
            "real_time_elapsed_s": real_time_elapsed,
            "speed_achieved": sim_time_elapsed / real_time_elapsed if real_time_elapsed > 0 else 0,
            "final_sol": self.plant_state.environment.sol,
            "total_ch4_kg": self.plant_state.total_ch4_produced_kg,
            "total_o2_kg": self.plant_state.total_o2_produced_kg,
            "total_energy_kwh": self.plant_state.total_energy_consumed_kwh,
            "material_inventory": self.plant_state.get_material_inventory(),
            "module_summaries": [m.get_status_summary() for m in self.modules],
            "timestep_data": self.timestep_results
        }
        
        logger.info(f"Simulation completed: {results['final_sol']} sols, "
                   f"{results['total_ch4_kg']:.1f} kg CH4, "
                   f"{results['total_o2_kg']:.1f} kg O2")
        
        return results
    
    def _execute_timestep(self) -> Dict[str, Any]:
        """Execute one simulation timestep."""
        dt = self.config.timestep_s
        
        # Clear previous power requests
        self.plant_state.power_budget.clear_requests()
        
        # 1. Update all modules (they submit power requests)
        module_results = {}
        for module in self.modules:
            try:
                # Attempt restart if shutdown
                module.attempt_restart(self.plant_state.current_time)
                
                # Run module simulation
                if not module.is_shutdown:
                    result = module.simulate(self.plant_state, dt)
                    module_results[module.name] = result
                    
                    # Check operating limits
                    module.check_operating_limits(self.plant_state)
                    
                    # Update statistics
                    module.update_statistics(dt)
                
            except Exception as e:
                logger.error(f"Error in module {module.name}: {e}")
                module_results[module.name] = {"error": str(e)}
        
        # 2. Allocate power based on all requests
        power_allocations = self.plant_state.power_budget.allocate_power()
        
        # 3. Apply power allocations to modules
        for module in self.modules:
            allocated = power_allocations.get(module.name, 0.0)
            module.apply_power_allocation(allocated)
        
        # 4. Advance simulation time
        self.plant_state.advance_time(dt)
        self.simulation_steps += 1
        
        # Compile timestep results
        timestep_result = {
            "sim_time_s": self.plant_state.current_time,
            "sol": self.plant_state.environment.sol,
            "time_of_sol": self.plant_state.environment.time_of_sol,
            "power_generation_kw": self.plant_state.power_budget.generation_kw,
            "power_demand_kw": self.plant_state.power_budget.total_demand_kw,
            "power_allocated_kw": self.plant_state.power_budget.total_allocated_kw,
            "power_deficit_kw": self.plant_state.power_budget.total_deficit_kw,
            "material_inventory": self.plant_state.get_material_inventory(),
            "module_results": module_results,
            "module_status": {m.name: m.status.value for m in self.modules}
        }
        
        return timestep_result
    
    def _log_status(self):
        """Log current simulation status."""
        sol = self.plant_state.environment.sol
        time_of_sol = self.plant_state.environment.time_of_sol
        
        # Power summary
        power = self.plant_state.power_budget
        power_summary = f"{power.total_allocated_kw:.0f}/{power.generation_kw:.0f} kW"
        if power.is_power_shortage:
            power_summary += f" (DEFICIT: {power.total_deficit_kw:.0f} kW)"
        
        # Material summary
        materials = self.plant_state.get_material_inventory()
        material_summary = f"CH4: {materials.get('CH4', 0):.0f}kg, O2: {materials.get('O2', 0):.0f}kg"
        
        # Module status
        active_modules = sum(1 for m in self.modules if m.status.value in ['ok', 'degraded'])
        
        logger.info(f"Sol {sol} ({time_of_sol:.2f}) | Power: {power_summary} | "
                   f"{material_summary} | Modules: {active_modules}/{len(self.modules)} active")
    
    def _auto_save(self):
        """Auto-save plant state."""
        try:
            state_data = self.plant_state.save_state()
            # Store module states
            for module in self.modules:
                state_data["module_states"][module.name] = module.save_state()
            
            # Could save to file here in future
            logger.debug(f"Auto-saved state at sol {self.plant_state.environment.sol}")
        except Exception as e:
            logger.warning(f"Auto-save failed: {e}")
    
    def pause(self):
        """Pause the simulation."""
        self.is_paused = True
        logger.info("Simulation paused")
    
    def resume(self):
        """Resume the simulation."""
        self.is_paused = False
        logger.info("Simulation resumed")
    
    def stop(self):
        """Stop the simulation."""
        self.is_running = False
        logger.info("Simulation stopped")
    
    def step(self) -> Dict[str, Any]:
        """Execute one simulation timestep and return results."""
        if not self.is_running:
            self.is_running = True
            self.simulation_steps = 0
            
        step_result = self._execute_timestep()
        return step_result
    
    def get_current_status(self) -> Dict[str, Any]:
        """Get current simulation status."""
        return {
            "is_running": self.is_running,
            "is_paused": self.is_paused,
            "current_sol": self.plant_state.environment.sol,
            "time_of_sol": self.plant_state.environment.time_of_sol,
            "simulation_steps": self.simulation_steps,
            "modules": [m.get_status_summary() for m in self.modules],
            "power_budget": str(self.plant_state.power_budget),
            "materials": self.plant_state.get_material_inventory()
        }
    
    def save_state_to_file(self, filepath: str):
        """Save complete simulation state to file."""
        import json
        
        state_data = self.plant_state.save_state()
        state_data["module_states"] = {}
        for module in self.modules:
            state_data["module_states"][module.name] = module.save_state()
        
        state_data["simulation_config"] = {
            "timestep_s": self.config.timestep_s,
            "simulation_steps": self.simulation_steps
        }
        
        with open(filepath, 'w') as f:
            json.dump(state_data, f, indent=2)
        
        logger.info(f"Saved simulation state to {filepath}")
    
    def load_state_from_file(self, filepath: str):
        """Load simulation state from file."""
        import json
        
        with open(filepath, 'r') as f:
            state_data = json.load(f)
        
        self.plant_state.load_state(state_data)
        
        # Load module states
        if "module_states" in state_data:
            for module in self.modules:
                if module.name in state_data["module_states"]:
                    module.load_state(state_data["module_states"][module.name])
        
        if "simulation_config" in state_data:
            config = state_data["simulation_config"]
            self.simulation_steps = config.get("simulation_steps", 0)
        
        logger.info(f"Loaded simulation state from {filepath}")
    
    def __repr__(self) -> str:
        return (f"SimulationEngine({len(self.modules)} modules, "
                f"Sol {self.plant_state.environment.sol}, "
                f"{'RUNNING' if self.is_running else 'STOPPED'})") 