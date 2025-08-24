#!/usr/bin/env python3
import logging
import json
from src.resource_bus import ResourceBus, ResourceType
from src.methanation import Methanation, PFRMethanation
from src.units import Q_, mol, mol_per_second, second, to_json_serializable

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

def run_methanation_test():
    # Initialize resource bus with starting moles
    bus = ResourceBus()
    bus.add_resource(ResourceType.CO2, Q_(10.0, mol))  # 10 mol CO2
    bus.add_resource(ResourceType.H2, Q_(50.0, mol))   # 50 mol H2 (excess - stoichiometric would be 40)
    bus.add_resource(ResourceType.CH4, Q_(0.0, mol))   # Start with no products
    bus.add_resource(ResourceType.H2O, Q_(0.0, mol))
    
    # Create methanation process with constant rate
    methanation = Methanation(bus, rate_constant=Q_(0.5, mol_per_second))
    
    logger.info("Methanation Simulation - Constant Rate")
    logger.info("=" * 50)
    logger.info("Initial state:")
    status = methanation.status()
    logger.info(status)
    
    # Run simulation for 30 seconds with 1-second timesteps
    dt = Q_(1.0, second)  # 1 second timesteps
    all_statuses = {}
    for t in range(0, 31, 1):
        if t > 0:  # Don't tick on first iteration
            methanation.tick(dt)
        
        if t % 5 == 0:  # Save status every 5 seconds
            status = methanation.status()
            logger.info(status)
            all_statuses[t] = to_json_serializable(status)
    
    with open("methanation_sim_level_1_status.json", "w") as f:
        json.dump(all_statuses, f, indent=4)

if __name__ == "__main__":
    run_methanation_test()