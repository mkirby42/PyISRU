#!/usr/bin/env python3
import logging
import json
import argparse
from pyisru.resource_bus import ResourceBus, ResourceType
from pyisru.methanation import PFRMethanation
from pyisru.units import Q_, mol, kelvin, cubic_meter, joule_per_mol, cubic_meter_per_second, pre_exponential_units, to_json_serializable, second
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
        # PFR parameters
        "reactor_volume_m3": 0.1,
        "temperature_K": 673.0,
        "pre_exponential": 1e5,
        "activation_energy_J_per_mol": 80000.0,
        "volumetric_flow_rate_m3_per_s": 0.001,
        # Simulation control
        "dt_seconds": 1.0,
        "duration_seconds": 30,
        "log_interval_seconds": 5,
        "output_path": "methanation_sim_level_3_status.json",
    }


def _load_config(path: str | None) -> dict:
    config = _default_config()
    if not path:
        return config

    try:
        with open(path, "r") as f:
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

def run_pfr_test(config: dict):
    # Test PFR methanation reactor
    try:
        bus = ResourceBus()
        bus.add_resource(ResourceType.CO2, Q_(float(config["initial_moles"].get("CO2", 10.0)), mol))
        bus.add_resource(ResourceType.H2, Q_(float(config["initial_moles"].get("H2", 50.0)), mol))
        bus.add_resource(ResourceType.CH4, Q_(float(config["initial_moles"].get("CH4", 0.0)), mol))
        bus.add_resource(ResourceType.H2O, Q_(float(config["initial_moles"].get("H2O", 0.0)), mol))

        # Create PFR reactor with configurable parameters
        pfr = PFRMethanation(
            bus,
            reactor_volume=Q_(float(config.get("reactor_volume_m3", 0.1)), cubic_meter),
            temperature=Q_(float(config.get("temperature_K", 673.0)), kelvin),
            pre_exponential=Q_(float(config.get("pre_exponential", 1e5)), pre_exponential_units),
            activation_energy=Q_(float(config.get("activation_energy_J_per_mol", 80000.0)), joule_per_mol),
            volumetric_flow_rate=Q_(float(config.get("volumetric_flow_rate_m3_per_s", 0.001)), cubic_meter_per_second),
        )

        logger.info("\nPFR Methanation Simulation")
        logger.info("=" * 50)
        logger.info("Initial state:")
        status = pfr.status()
        logger.info(status)

        # Run simulation using SimulationRunner
        dt = Q_(float(config.get("dt_seconds", 1.0)), second)
        duration = float(config.get("duration_seconds", 60))
        log_interval = float(config.get("log_interval_seconds", 5))
        output_path = config.get("output_path", "methanation_sim_level_2_status.json")

        events = parse_events(config.get("events"))

        def on_log(t_s: int, bus: ResourceBus, process: PFRMethanation):
            # Attach axial profiles at log times
            prof = process.get_axial_profiles()
            return {"axial_profiles": prof} if prof is not None else {}

        runner = SimulationRunner(
            bus=bus,
            process=pfr,
            dt=dt,
            duration_seconds=duration,
            log_interval_seconds=log_interval,
            events=events,
            on_log=on_log,
        )
        all_statuses = runner.run()

        with open(output_path, "w") as f:
            json.dump(all_statuses, f, indent=4)

    except ImportError:
        logger.error("\nPFR Methanation requires scipy. Install with: pip install scipy")
    except Exception as e:
        logger.error(f"Error in PFR simulation: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run level 3 methanation simulation (PFR).")
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to JSON config file (optional).",
    )
    args = parser.parse_args()

    cfg = _load_config(args.config)
    run_pfr_test(cfg)