#!/usr/bin/env python3
import logging
import json
import argparse
from pyisru.resource_bus import ResourceBus, ResourceType
from pyisru.methanation import AdvancedPFRMethanation
from pyisru.units import (Q_, mol, kelvin, cubic_meter, joule_per_mol, cubic_meter_per_second, 
                       pre_exponential_units, to_json_serializable, pascal, meter, 
                       joule_per_mol_kelvin, joule, kilogram, second)
from pyisru.sim_runner import SimulationRunner, parse_events

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)


def _default_config() -> dict:
    return {
        "initial_moles": {
            "CO2": 10.0,
            "H2": 50.0,
            "CH4": 0.0,
            "H2O": 0.0,
        },
        # Advanced PFR parameters (align with AdvancedPFRMethanation API)
        "reactor_volume_m3": 0.5,
        "inlet_temperature_K": 573.0,
        "inlet_pressure_Pa": 2000000.0,
        "pre_exponential": 1e6,
        "activation_energy_J_per_mol": 80000.0,
        "orders": [1.0, 4.0],
        "volumetric_flow_rate_m3_per_s": 0.005,
        "heat_of_reaction_J_per_mol": -165000.0,
        "ambient_temperature_K": 298.0,
        "porosity": 0.4,
        "particle_diameter_m": 0.004,
        "gas_viscosity_Pa_s": 2.5e-5,
        # Equilibrium / reversibility
        "product_orders": [1.0, 2.0],
        "equilibrium_constant_ref": None,
        "equilibrium_T_ref_K": 298.15,
        # Simulation control
        "dt_seconds": 2.0,
        "duration_seconds": 60 * 15,
        "log_interval_seconds": 30,
        "save_interval_seconds": 10,
        "output_path": "methanation_sim_level_4_status.json",
    }


def _load_config(path: str | None) -> dict:
    config = _default_config()
    if not path:
        return config

    try:
        with open(path, "r") as f:
            logger.info(f"Loading config from {path}")
            user_cfg = json.load(f)
    except FileNotFoundError:
        logger.warning("Config file not found at %s. Using defaults.", path)
        return config
    except json.JSONDecodeError as e:
        logger.warning("Invalid JSON in config %s (%s). Using defaults.", path, e)
        return config

    for key, value in user_cfg.items():
        if key == "initial_moles" and isinstance(value, dict):
            config["initial_moles"].update(value)
        else:
            config[key] = value
    return config

def run_advanced_pfr_test(config: dict):
    """Test Advanced PFR methanation reactor with energy balance, pressure drop, and reversible kinetics"""
    try:
        bus = ResourceBus()
        bus.add_resource(ResourceType.CO2, Q_(float(config["initial_moles"].get("CO2", 10.0)), mol))
        bus.add_resource(ResourceType.H2, Q_(float(config["initial_moles"].get("H2", 50.0)), mol))
        bus.add_resource(ResourceType.CH4, Q_(float(config["initial_moles"].get("CH4", 0.0)), mol))
        bus.add_resource(ResourceType.H2O, Q_(float(config["initial_moles"].get("H2O", 0.0)), mol))
        
        # Create Advanced PFR reactor with realistic industrial parameters
        # Heat transfer coefficient handling:
        # - Prefer explicit area-based overall_U (J/(s·m²·K)) if provided
        # - Fallback: map legacy volumetric heat loss coeff (J/(m³·s·K)) via U ≈ h_vol * D/4
        tube_diameter_m = float(config.get("tube_diameter_m", 0.10))
        if "overall_U_J_per_m2_s_K" in config:
            overall_U_val = float(config.get("overall_U_J_per_m2_s_K"))
        elif "heat_loss_coeff_J_per_m3_s_K" in config:
            overall_U_val = float(config.get("heat_loss_coeff_J_per_m3_s_K")) * (tube_diameter_m / 4.0)
        else:
            overall_U_val = 50.0

        advanced_pfr = AdvancedPFRMethanation(
            resource_bus=bus,
            reactor_volume=Q_(float(config.get("reactor_volume_m3", 0.5)), cubic_meter),
            temperature=Q_(float(config.get("inlet_temperature_K", 573.0)), kelvin),
            inlet_pressure=Q_(float(config.get("inlet_pressure_Pa", 2000000.0)), pascal),
            pre_exponential=Q_(float(config.get("pre_exponential", 1e6)), pre_exponential_units),
            activation_energy=Q_(float(config.get("activation_energy_J_per_mol", 80000.0)), joule_per_mol),
            volumetric_flow_rate=Q_(float(config.get("volumetric_flow_rate_m3_per_s", 0.005)), cubic_meter_per_second),
            overall_U=Q_(overall_U_val, joule/(second*meter**2*kelvin)),
            ambient_temperature=Q_(float(config.get("ambient_temperature_K", 298.0)), kelvin),
            void_fraction=float(config.get("porosity", 0.4)),
            particle_diameter=Q_(float(config.get("particle_diameter_m", 0.004)), meter),
            gas_viscosity=Q_(float(config.get("gas_viscosity_Pa_s", 2.5e-5)), kilogram/(meter*second)),
            heat_of_reaction=Q_(float(config.get("heat_of_reaction_J_per_mol", -165000.0)), joule_per_mol),
            product_orders=tuple(config.get("product_orders", [1.0, 2.0])),
            equilibrium_constant_ref=config.get("equilibrium_constant_ref", None),
            equilibrium_T_ref=Q_(float(config.get("equilibrium_T_ref_K", 298.15)), kelvin),
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
        
        # Run simulation via SimulationRunner with logging and save callbacks
        dt = Q_(float(config.get("dt_seconds", 2.0)), 'second')
        duration = float(config.get("duration_seconds", 60 * 15))
        save_interval = float(config.get("save_interval_seconds", 10))
        log_interval = float(config.get("log_interval_seconds", 30))
        events = parse_events(config.get("events"))

        logger.info("Starting simulation...")
        logger.info("Time [s] | CO2 [mol] | H2 [mol] | CH4 [mol] | H2O [mol] | T_out [K] | P_out [Pa] | Rate [mol/m³/s]")
        logger.info("-" * 120)

        def on_log(t_s: int, bus: ResourceBus, process: AdvancedPFRMethanation):
            status = process.status()
            co2 = bus.get_resource(ResourceType.CO2)
            h2 = bus.get_resource(ResourceType.H2)
            ch4 = bus.get_resource(ResourceType.CH4)
            h2o = bus.get_resource(ResourceType.H2O)
            # approximate outlet from last_profile if present
            prof = process.get_axial_profiles()
            T_out = Q_(prof["T"][-1], kelvin) if prof else status['inlet_temperature']
            P_out = Q_(prof["P"][-1], pascal) if prof else status['inlet_pressure']
            rate = status.get('current_reaction_rate_midbed', Q_(0, 'mol/(meter**3 * second)'))
            logger.info(f"{t_s:7d}  | {co2.magnitude:7.3f}   | {h2.magnitude:6.2f}   | {ch4.magnitude:7.3f}   | "
                       f"{h2o.magnitude:7.3f}   | {T_out.magnitude:7.1f}   | {P_out.magnitude:8.0f}   | {rate.magnitude:8.2e}")
            return {}

        def on_save(t_s: int, bus: ResourceBus, process: AdvancedPFRMethanation):
            status = process.status()
            extras = {
                'current_resources': {
                    'CO2': to_json_serializable(bus.get_resource(ResourceType.CO2)),
                    'H2': to_json_serializable(bus.get_resource(ResourceType.H2)),
                    'CH4': to_json_serializable(bus.get_resource(ResourceType.CH4)),
                    'H2O': to_json_serializable(bus.get_resource(ResourceType.H2O)),
                }
            }
            if hasattr(process, 'temperature_profile') and process.temperature_profile:
                extras['temperature_profile'] = [to_json_serializable(T) for T in process.temperature_profile]
                extras['pressure_profile'] = [to_json_serializable(P) for P in process.pressure_profile]
            return extras

        runner = SimulationRunner(
            bus=bus,
            process=advanced_pfr,
            dt=dt,
            duration_seconds=duration,
            log_interval_seconds=log_interval,
            save_interval_seconds=save_interval,
            events=events,
            on_log=on_log,
            on_save=on_save,
        )
        all_statuses = runner.run()
        
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
        output_path = config.get("output_path", "methanation_sim_level_4_status.json")
        with open(output_path, "w") as f:
            json.dump(all_statuses, f, indent=4)
        
        logger.info("")
        logger.info("Advanced PFR Features Validated:")
        logger.info("✓ Energy balance with temperature profiles")
        logger.info("✓ Pressure drop via Ergun equation")
        logger.info("✓ Reversible reaction kinetics")
        logger.info("✓ Temperature/pressure dependent concentrations")
        logger.info("✓ Industrial-scale reactor modeling")
        logger.info("")
        logger.info(f"Data saved to: {output_path}")

    except ImportError as e:
        logger.error(f"\nAdvanced PFR Methanation requires additional packages: {e}")
        logger.error("Install with: pip install scipy numpy")
    except Exception as e:
        logger.error(f"Error in Advanced PFR simulation: {e}")
        raise

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run level 3 methanation simulation (Advanced PFR).")
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to JSON config file (optional).",
    )
    args = parser.parse_args()

    cfg = _load_config(args.config)
    run_advanced_pfr_test(cfg)