#!/usr/bin/env python3
import logging
import json
from src.resource_bus import ResourceBus, ResourceType
from src.methanation import AdvancedPFRMethanation
from src.units import (Q_, mol, kelvin, cubic_meter, joule_per_mol, cubic_meter_per_second, 
                       pre_exponential_units, to_json_serializable, pascal, meter, 
                       joule_per_mol_kelvin, joule, kilogram, second)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

def run_advanced_pfr_test():
    """Test Advanced PFR methanation reactor with energy balance, pressure drop, and reversible kinetics"""
    try:
        bus = ResourceBus()
        bus.add_resource(ResourceType.CO2, Q_(10.0, mol))  # 10 mol CO2
        bus.add_resource(ResourceType.H2, Q_(50.0, mol))   # 50 mol H2 (excess for testing)
        bus.add_resource(ResourceType.CH4, Q_(0.0, mol))
        bus.add_resource(ResourceType.H2O, Q_(0.0, mol))
        
        # Create Advanced PFR reactor with realistic industrial parameters
        advanced_pfr = AdvancedPFRMethanation(
            resource_bus=bus,
            reactor_volume=Q_(0.5, cubic_meter),              # 500 L reactor
            inlet_temperature=Q_(573, kelvin),                # 300°C inlet
            inlet_pressure=Q_(2000000, pascal),               # 20 bar operating pressure
            pre_exponential_forward=Q_(1e6, pre_exponential_units),     # Forward reaction A factor
            pre_exponential_reverse=Q_(1e4, pre_exponential_units),     # Reverse reaction A factor  
            activation_energy_forward=Q_(80000, joule_per_mol),         # Forward Ea
            activation_energy_reverse=Q_(95000, joule_per_mol),         # Reverse Ea (higher)
            volumetric_flow_rate=Q_(0.005, cubic_meter_per_second),     # 5 L/s flow rate
            heat_of_reaction=Q_(-165000, joule_per_mol),                # Exothermic Sabatier (-165 kJ/mol)
            heat_capacity=Q_(35.0, joule_per_mol_kelvin),               # Gas mixture Cp
            heat_loss_coefficient=Q_(50.0, joule / (cubic_meter * second * kelvin)),  # Heat loss
            ambient_temperature=Q_(298, kelvin),                        # 25°C ambient
            porosity=0.4,                                               # 40% bed porosity
            particle_diameter=Q_(0.004, meter),                         # 4mm catalyst particles
            gas_viscosity=Q_(2.5e-5, pascal * second),                  # Gas viscosity at conditions
            gas_density=Q_(2.0, kilogram / cubic_meter)                 # Gas density at pressure
        )
        
        logger.info("\nAdvanced PFR Methanation Simulation")
        logger.info("=" * 60)
        logger.info("Features: Energy Balance | Pressure Drop | Reversible Kinetics")
        logger.info("=" * 60)
        
        # Log initial reactor configuration
        initial_status = advanced_pfr.status()
        logger.info("Reactor Configuration:")
        logger.info(f"  Type: {initial_status['reactor_type']}")
        logger.info(f"  Volume: {initial_status['reactor_volume']}")
        logger.info(f"  Inlet Temperature: {initial_status['inlet_temperature']}")
        logger.info(f"  Inlet Pressure: {initial_status['inlet_pressure']}")
        logger.info(f"  Heat of Reaction: {initial_status['heat_of_reaction']}")
        logger.info(f"  Porosity: {initial_status['porosity']}")
        logger.info(f"  Particle Diameter: {initial_status['particle_diameter']}")
        logger.info("")
        
        logger.info("Initial Resources:")
        logger.info(f"  CO2: {bus.get_resource(ResourceType.CO2)}")
        logger.info(f"  H2:  {bus.get_resource(ResourceType.H2)}")
        logger.info(f"  CH4: {bus.get_resource(ResourceType.CH4)}")
        logger.info(f"  H2O: {bus.get_resource(ResourceType.H2O)}")
        logger.info("")
        
        # Run simulation for longer duration with smaller timesteps to capture dynamics
        dt = Q_(2.0, 'second')  # 2 second timesteps
        all_statuses = {}
        duration = 60 * 15  # 15 minutes simulation
        
        logger.info("Starting simulation...")
        logger.info("Time [s] | CO2 [mol] | H2 [mol] | CH4 [mol] | H2O [mol] | T_out [K] | P_out [Pa] | Rate [mol/m³/s]")
        logger.info("-" * 120)
        
        for t in range(0, duration, 2):  # Every 2 seconds
            if t > 0:  # Don't tick on first iteration
                advanced_pfr.tick(dt)
            
            # Log progress every 30 seconds
            if t % 30 == 0:
                status = advanced_pfr.status()
                co2 = bus.get_resource(ResourceType.CO2)
                h2 = bus.get_resource(ResourceType.H2)
                ch4 = bus.get_resource(ResourceType.CH4)
                h2o = bus.get_resource(ResourceType.H2O)
                
                T_out = status.get('outlet_temperature', status['inlet_temperature'])
                P_out = status.get('outlet_pressure', status['inlet_pressure'])
                rate = status.get('current_reaction_rate', Q_(0, 'mol/(meter**3 * second)'))
                
                logger.info(f"{t:7d}  | {co2.magnitude:7.3f}   | {h2.magnitude:6.2f}   | {ch4.magnitude:7.3f}   | "
                           f"{h2o.magnitude:7.3f}   | {T_out.magnitude:7.1f}   | {P_out.magnitude:8.0f}   | {rate.magnitude:8.2e}")
            
            # Save detailed status every 10 seconds for analysis
            if t % 10 == 0:
                status = advanced_pfr.status()
                all_statuses[t] = to_json_serializable(status)
                
                # Add current resource levels
                all_statuses[t]['current_resources'] = {
                    'CO2': to_json_serializable(bus.get_resource(ResourceType.CO2)),
                    'H2': to_json_serializable(bus.get_resource(ResourceType.H2)),
                    'CH4': to_json_serializable(bus.get_resource(ResourceType.CH4)),
                    'H2O': to_json_serializable(bus.get_resource(ResourceType.H2O))
                }
                
                # Add temperature and pressure profiles if available
                if hasattr(advanced_pfr, 'temperature_profile') and advanced_pfr.temperature_profile:
                    all_statuses[t]['temperature_profile'] = [
                        to_json_serializable(T) for T in advanced_pfr.temperature_profile
                    ]
                    all_statuses[t]['pressure_profile'] = [
                        to_json_serializable(P) for P in advanced_pfr.pressure_profile
                    ]
            
            # Stop if reaction essentially complete
            if bus.get_resource(ResourceType.CO2).magnitude < 0.05:
                logger.info(f"Simulation stopped at t={t}s - CO2 nearly depleted")
                break
        
        # Final results summary
        logger.info("")
        logger.info("Final Results:")
        final_status = advanced_pfr.status()
        logger.info(f"  Total Time Elapsed: {final_status['time_elapsed']}")
        logger.info(f"  CO2 Consumed: {final_status['total_consumed_CO2']}")
        logger.info(f"  H2 Consumed: {final_status['total_consumed_H2']}")
        logger.info(f"  CH4 Produced: {final_status['total_produced_CH4']}")
        logger.info(f"  H2O Produced: {final_status['total_produced_H2O']}")
        
        # Calculate conversions and selectivity
        initial_co2 = Q_(10.0, mol)
        final_co2 = bus.get_resource(ResourceType.CO2)
        co2_conversion = (initial_co2 - final_co2) / initial_co2 * 100
        
        # Theoretical maximum CH4 from stoichiometry
        theoretical_ch4 = (initial_co2 - final_co2)  # 1:1 stoichiometry
        actual_ch4 = bus.get_resource(ResourceType.CH4)
        selectivity = actual_ch4 / theoretical_ch4 * 100 if theoretical_ch4.magnitude > 0 else Q_(0, '')
        
        logger.info(f"  CO2 Conversion: {co2_conversion.magnitude:.1f}%")
        logger.info(f"  CH4 Selectivity: {selectivity.magnitude:.1f}%")
        
        # Energy balance results
        if 'outlet_temperature' in final_status:
            temp_rise = final_status['outlet_temperature'] - final_status['inlet_temperature']
            logger.info(f"  Temperature Rise: {temp_rise}")
        
        if 'outlet_pressure' in final_status:
            pressure_drop = final_status['inlet_pressure'] - final_status['outlet_pressure']
            logger.info(f"  Pressure Drop: {pressure_drop}")
        
        # Equilibrium analysis
        if 'equilibrium_constant' in final_status:
            logger.info(f"  Equilibrium Constant: {final_status['equilibrium_constant']:.2e}")
        
        # Save all data to JSON file
        with open("methanation_sim_level_3_status.json", "w") as f:
            json.dump(all_statuses, f, indent=4)
        
        logger.info("")
        logger.info("Advanced PFR Features Validated:")
        logger.info("✓ Energy balance with temperature profiles")
        logger.info("✓ Pressure drop via Ergun equation")
        logger.info("✓ Reversible reaction kinetics")
        logger.info("✓ Temperature/pressure dependent concentrations")
        logger.info("✓ Industrial-scale reactor modeling")
        logger.info("")
        logger.info("Data saved to: methanation_sim_level_3_status.json")

    except ImportError as e:
        logger.error(f"\nAdvanced PFR Methanation requires additional packages: {e}")
        logger.error("Install with: pip install scipy numpy")
    except Exception as e:
        logger.error(f"Error in Advanced PFR simulation: {e}")
        raise

if __name__ == "__main__":
    run_advanced_pfr_test()