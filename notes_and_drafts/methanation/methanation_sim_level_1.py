#!/usr/bin/env python3
import logging
import json
import os
import argparse
from pyisru.resource_bus import ResourceBus, ResourceType
from pyisru.methanation import Methanation
from pyisru.units import Q_, mol, mol_per_second, second, to_json_serializable
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
        "rate_constant": 0.5,
        "dt_seconds": 1.0,
        "total_seconds": 30,
        "log_interval_seconds": 5,
        "output_path": "methanation_sim_level_1_status.json",
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

    # Shallow merge for top-level keys; deep-merge for initial_moles
    for key, value in user_cfg.items():
        if key == "initial_moles" and isinstance(value, dict):
            config["initial_moles"].update(value)
        else:
            config[key] = value
    return config


def run_methanation_test(config: dict):
    # Initialize resource bus with starting moles
    initial_co2 = config["initial_moles"].get("CO2", 10.0)
    initial_h2 = config["initial_moles"].get("H2", 50.0)
    initial_ch4 = config["initial_moles"].get("CH4", 0.0)
    initial_h2o = config["initial_moles"].get("H2O", 0.0)
    
    bus = ResourceBus()
    bus.add_resource(ResourceType.CO2, Q_(initial_co2, mol))
    bus.add_resource(ResourceType.H2, Q_(initial_h2, mol))
    bus.add_resource(ResourceType.CH4, Q_(initial_ch4, mol))
    bus.add_resource(ResourceType.H2O, Q_(initial_h2o, mol))

    # Create methanation process with constant rate
    rate_constant_value = float(config.get("rate_constant", 0.5))
    methanation = Methanation(bus, rate_constant=Q_(rate_constant_value, mol_per_second))

    logger.info("Methanation Simulation - Constant Rate")
    logger.info("=" * 50)
    logger.info("Initial state:")
    status = methanation.status()
    logger.info(status)

    # Run simulation via SimulationRunner
    dt = Q_(float(config.get("dt_seconds", 1.0)), second)
    total_seconds = float(config.get("total_seconds", 30))
    log_interval_seconds = float(config.get("log_interval_seconds", 5))
    output_path = config.get("output_path", "methanation_sim_level_1_status.json")

    # Optional events (none by default keeps behavior identical)
    events = parse_events(config.get("events"))
    runner = SimulationRunner(
        bus=bus,
        process=methanation,
        dt=dt,
        duration_seconds=total_seconds,
        log_interval_seconds=log_interval_seconds,
        events=events,
    )
    json_statuses = runner.run()

    with open(output_path, "w") as f:
        json.dump(json_statuses, f, indent=4)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run level 1 methanation simulation.")
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to JSON config file (optional).",
    )
    args = parser.parse_args()

    cfg = _load_config(args.config)
    run_methanation_test(cfg)