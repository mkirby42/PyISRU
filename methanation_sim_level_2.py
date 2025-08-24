#!/usr/bin/env python3
import logging
import json
from src.resource_bus import ResourceBus, ResourceType
from src.methanation import PFRMethanation
from src.units import Q_, mol, kelvin, cubic_meter, joule_per_mol, cubic_meter_per_second, pre_exponential_units, to_json_serializable

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

def run_pfr_test():
    # Test PFR methanation reactor
    try:
        bus = ResourceBus()
        bus.add_resource(ResourceType.CO2, Q_(10.0, mol))  # 10 mol CO2
        bus.add_resource(ResourceType.H2, Q_(50.0, mol))   # 50 mol H2
        bus.add_resource(ResourceType.CH4, Q_(0.0, mol))
        bus.add_resource(ResourceType.H2O, Q_(0.0, mol))
        
        # Create PFR reactor with realistic parameters
        pfr = PFRMethanation(
            bus,
            reactor_volume=Q_(1.0, cubic_meter),       # 1 m³ reactor
            temperature=Q_(673, kelvin), 
            pre_exponential=Q_(1e5, pre_exponential_units),     # Pre-exponential factor
            activation_energy=Q_(80000, joule_per_mol),
            volumetric_flow_rate=Q_(0.01, cubic_meter_per_second)  # 0.010 m³/s flow rate
        )
        
        logger.info("\nPFR Methanation Simulation")
        logger.info("=" * 50)
        logger.info("Initial state:")
        status = pfr.status()
        logger.info(status)
        
        # Run simulation for 30 seconds with 5-second timesteps
        dt = Q_(1.0, 'second')  # 1 second timesteps
        all_statuses = {}
        duration = 60 * 60 * 1
        for t in range(0, duration, 1):
            if t > 0:  # Don't tick on first iteration
                pfr.tick(dt)
            
            if t % 5 == 0:  # Save status every 5 seconds
                status = pfr.status()
                # logger.info(status)
                all_statuses[t] = to_json_serializable(status)
        
        with open("methanation_sim_level_2_status.json", "w") as f:
            json.dump(all_statuses, f, indent=4)

    except ImportError:
        logger.error("\nPFR Methanation requires scipy. Install with: pip install scipy")
    except Exception as e:
        logger.error(f"Error in PFR simulation: {e}")

if __name__ == "__main__":
    run_pfr_test()