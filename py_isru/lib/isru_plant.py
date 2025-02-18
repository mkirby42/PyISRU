"""
Revised ISRU Plant Implementation for a Martian ISRU Plant

This class orchestrates the Sabatier reactor, Electrolysis reactor,
storage tanks, and power systems to simulate overall plant operation.

All subsystems use consistent naming conventions and unit annotations.
"""

import logging
from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, Optional, Tuple

import numpy as np
from scipy import constants

from .reactor import ResourceType, OperationalStatus
from .sabatier_reactor import SabatierReactor, SabatierSpecification
from .electrolysis_reactor import ElectrolysisReactor, ElectrolysisSpecification
from .storage_tank import StorageTank, TankSpecification
from .power_system import (
    PowerSystemStatus,
    SolarArray, SolarArraySpecification,
    Battery, BatterySpecification,
    KrustyReactor, KrustySpecification
)
from .thermodynamics import ThermodynamicState, ReactionKinetics

# Set up a module-level logger.
logger = logging.getLogger(__name__)

class PlantStatus(Enum):
    """Overall plant operational status"""
    STARTUP = auto()
    RUNNING = auto()
    SHUTDOWN = auto()
    STANDBY = auto()
    EMERGENCY = auto()
    MAINTENANCE = auto()

@dataclass
class PlantSpecification:
    """Complete specification for an ISRU plant"""
    sabatier_spec: SabatierSpecification
    electrolysis_spec: ElectrolysisSpecification
    tank_specs: Dict[ResourceType, TankSpecification]
    solar_spec: SolarArraySpecification
    battery_spec: BatterySpecification
    krusty_spec: KrustySpecification

    # Control parameters
    min_tank_levels_mol: Dict[ResourceType, float]
    max_tank_levels_mol: Dict[ResourceType, float]
    emergency_power_threshold_W: float
    maintenance_interval_s: float

    def __repr__(self):
        return (f"PlantSpecification(sabatier_spec={self.sabatier_spec}, "
                f"electrolysis_spec={self.electrolysis_spec}, "
                f"tank_specs={self.tank_specs}, "
                f"solar_spec={self.solar_spec}, "
                f"battery_spec={self.battery_spec}, "
                f"krusty_spec={self.krusty_spec}, "
                f"min_tank_levels_mol={self.min_tank_levels_mol}, "
                f"max_tank_levels_mol={self.max_tank_levels_mol}, "
                f"emergency_power_threshold_W={self.emergency_power_threshold_W}, "
                f"maintenance_interval_s={self.maintenance_interval_s})")

# Create an ISRUPlant error class
class ISRUPlantError(Exception):
    """Exception class for ISRU Plant errors"""
    def __init__(self, error_code):
        super().__init__(error_code)
        self.error_code = error_code

class ISRUPlantErrorCode(Enum):
    """Error codes for ISRU Plant"""
    INSUFFICIENT_POWER = auto()
    INSUFFICIENT_RESOURCE = auto()
    EMERGENCY_SHUTDOWN = auto()
    MAINTENANCE_REQUIRED = auto()
    FAULT_CONDITION = auto()
    PLANT_NOT_IN_STANDBY = auto()
    KRUSTY_FAILED_TO_START = auto()
    PLANT_STARTUP_FAILED = auto()
    PLANT_SHUTDOWN_FAILED = auto()
    PLANT_NOT_RUNNING_OR_EMERGENCY = auto()
    
    
class ISRUPlantWarning(Enum):
    """Warning codes for ISRU Plant"""
    POWER_LIMITED = auto()
    RESOURCE_LIMITED = auto()
    OPERATIONAL_STATUS_CHANGE = auto()
    
    
@dataclass
class ISRUPlantState:
    """
    Performance metrics for ISRU Plant
    Generated once per step.
    """
    total_CH4_produced_mol: float = 0.0
    total_O2_produced_mol: float = 0.0
    current_CH4_level_mol: float = 0.0
    current_O2_level_mol: float = 0.0
    current_H2O_level_mol: float = 0.0
    current_H2_level_mol: float = 0.0
    current_CO2_level_mol: float = 0.0
    total_energy_consumed_J: float = 0.0
    error: Optional[ISRUPlantError] = None
    warning: Optional[ISRUPlantWarning] = None
    status: Optional[PlantStatus] = None
    time_elapsed_s: float = 0.0
    
    def __repr__(self):
        return (f"ISRUPlantState(total_CH4_produced_mol={self.total_CH4_produced_mol}, "
            f"total_O2_produced_mol={self.total_O2_produced_mol}, "
            f"total_energy_consumed_J={self.total_energy_consumed_J}, "
            f"error={self.error}, "
            f"warning={self.warning}, "
            f"status={self.status}, "
            f"time_elapsed_s={self.time_elapsed_s}, "
            f"current_CH4_level_mol={self.current_CH4_level_mol}, "
            f"current_O2_level_mol={self.current_O2_level_mol}, "
            f"current_H2O_level_mol={self.current_H2O_level_mol}, "
            f"current_H2_level_mol={self.current_H2_level_mol}, "
            f"current_CO2_level_mol={self.current_CO2_level_mol})")
        
    def get_status(self) -> PlantStatus:
        """Get the current plant status."""
        return self.status
    
    def set_status(self, status: PlantStatus) -> None:
        """Set the plant status."""
        self.status = status
        logger.info(f"Status set to {status}")
        
    def update_resource_levels(self, tanks: Dict[ResourceType, StorageTank]) -> None:
        """Update the resource levels for the given tanks."""
        for resource_type, tank in tanks.items():
            self.update_resource_level(resource_type, tank.moles)
        
    def update_resource_level(self, resource_type: ResourceType, amount: float) -> None:
        """Update the resource level for the given resource type."""
        if resource_type == ResourceType.CO2:
            self.current_CO2_level_mol += amount
        elif resource_type == ResourceType.H2O:
            self.current_H2O_level_mol += amount
        elif resource_type == ResourceType.H2:
            self.current_H2_level_mol += amount
        elif resource_type == ResourceType.CH4:
            self.current_CH4_level_mol += amount
        elif resource_type == ResourceType.O2:
            self.current_O2_level_mol += amount
        else:
            raise ValueError(f"Invalid resource type: {resource_type}")
    
    
class ISRUPlant:
    """
    Main ISRU plant class that coordinates all subsystems.
    
    This class manages:
      - The Sabatier and Electrolysis reactors,
      - Storage tanks for various resources,
      - Power systems (solar array, battery, and auxiliary reactor),
      - Overall plant metrics and control logic.
    """
    
    def __init__(self, spec: PlantSpecification):
        self.spec = spec
        self._initialize_subsystems()

    def __repr__(self):
        return (f"ISRUPlant status={self.get_status()}, "
                f"state={self.get_state()}")
        
    def get_status(self) -> PlantStatus:
        """Get the current plant status."""
        return self.get_state().status
    
    def set_status(self, status: PlantStatus) -> None:
        """Set the current plant status."""
        self.get_state().set_status(status)
    
    def get_state(self) -> ISRUPlantState:
        """Get the current state."""
        return self.history[-1]
    
    def set_state(self, state: ISRUPlantState) -> None:
        """Set the current state."""
        self.history.append(state)
        
    def _initialize_subsystems(self) -> None:
        """Initialize all subsystems with their specifications."""
        self._initialize_sabatier_reactor()
        self._initialize_electrolysis_reactor()
        self._initialize_storage_tanks()
        self._initialize_power_systems()
        self._initialize_state()
        logger.info("All subsystems initialized.")

    def _initialize_sabatier_reactor(
        self,
        sabatier_state: ThermodynamicState = ThermodynamicState.from_temperature_pressure(600.0, 101325, "CO2"),
        initial_composition_mol: Dict[ResourceType, float] = {
            ResourceType.CO2: 100.0, 
            ResourceType.H2: 0.0, 
            ResourceType.CH4: 0.0, 
            ResourceType.H2O: 0.0, 
            ResourceType.CO: 0.0, 
            ResourceType.O2: 0.0
        }
    ) -> None:
        """Initialize the Sabatier reactor."""
        self.sabatier = SabatierReactor(
            self.spec.sabatier_spec,
            sabatier_state,
            initial_composition_mol=initial_composition_mol
        )
        logger.info(f"Sabatier reactor initialized: {self.sabatier}")

    def _initialize_electrolysis_reactor(
        self,
        electrolysis_state: ThermodynamicState = ThermodynamicState.from_temperature_pressure(353.15, 101325, "H2O"),
        electrolysis_kinetics: ReactionKinetics = ReactionKinetics(
            rate_constant_forward_1_s_inv=1e3,  # Increased from 1.0
            activation_energy_J_per_mol=40e3,   # Added realistic activation energy
            reaction_order={"H2O": 1}
        ),
        initial_composition_mol: Dict[ResourceType, float] = {
            ResourceType.H2O: 100.0, 
            ResourceType.H2: 0.0, 
            ResourceType.O2: 0.0
        }
    ) -> None:
        """Initialize the electrolysis reactor."""
        self.electrolysis = ElectrolysisReactor(
            self.spec.electrolysis_spec,
            electrolysis_state,
            electrolysis_kinetics,
            initial_composition_mol=initial_composition_mol
        )
        logger.info(f"Electrolysis reactor initialized: {self.electrolysis}")
        
    def _initialize_storage_tanks(self) -> None:
        """Initialize the storage tanks."""
        self.tanks: Dict[ResourceType, StorageTank] = {}
        substance_map = {
            ResourceType.CO2: "CO2",
            ResourceType.H2: "H2",  
            ResourceType.O2: "O2",
            ResourceType.CH4: "CH4",
            ResourceType.H2O: "H2O"
        }
        for resource_type, tank_spec in self.spec.tank_specs.items():
            init_state = ThermodynamicState.from_temperature_pressure(298.15, 101325, substance_map[resource_type])
            self.tanks[resource_type] = StorageTank(tank_spec, resource_type, init_state)
        logger.info(f"Tanks initialized: {self.tanks}")
        
    def _initialize_power_systems(self) -> None:
        """Initialize the power systems."""
        self.solar_array = SolarArray(self.spec.solar_spec)
        self.solar_array.status = PowerSystemStatus.ONLINE
        self.battery = Battery(self.spec.battery_spec)
        self.battery.status = PowerSystemStatus.ONLINE
        self.krusty = KrustyReactor(self.spec.krusty_spec)
        logger.info(f"Power systems initialized: {self.solar_array}, {self.battery}, {self.krusty}")
        
    def _initialize_state(self) -> None:
        """Initialize the state."""
        initial_state = ISRUPlantState(
            total_CH4_produced_mol=0.0,
            total_O2_produced_mol=0.0,
            total_energy_consumed_J=0.0,
            error=None,
            warning=None,
            status=PlantStatus.STANDBY,
            time_elapsed_s=0.0
        )
        self.history = [initial_state]
        logger.info(f"State initialized: {self.get_state()}")
        
    def step(self, dt_s: float) -> None:
        """
        Advance the plant state by one time step.

        Args:
            dt_s: Time step in seconds.
        """
        for _ in range(int(dt_s)):
            step_state = ISRUPlantState(
                time_elapsed_s=self.get_state().time_elapsed_s + 1.0
            )
            logger.debug(f"Plant state: {step_state}")
            self.check_for_standby()
            logger.debug(f"Plant state after standby check: {step_state}")
            
            self._update_power_systems(1.0)
            logger.debug(f"Plant state after power systems update: {step_state}")
            available_power_W = self._calculate_available_power_W()
            required_power_W = self._calculate_required_power_W()
            
            try:
                self._check_power_availability(available_power_W, required_power_W)
            except ISRUPlantError as e:
                step_state.error = e
                if e == ISRUPlantError(ISRUPlantErrorCode.INSUFFICIENT_POWER):
                    self.set_status(PlantStatus.EMERGENCY)
                    raise
                elif e == ISRUPlantError(ISRUPlantErrorCode.INSUFFICIENT_RESOURCE):
                    self.set_status(PlantStatus.STANDBY)
            logger.debug(f"Plant state after power check: {step_state}")
            
            step_state = self._update_reactors(1.0, available_power_W, step_state)
            logger.debug(f"Plant state after reactors: {step_state}")
            step_state = self._update_storage(dt_s, step_state)
            logger.debug(f"Plant state after storage: {step_state}")

            # Check if maintenance is required.
            # if self.get_state().time_elapsed_s > self.spec.maintenance_interval_s:
            #     logger.info("Maintenance interval reached; transitioning to MAINTENANCE mode.")
            #     self.set_status(PlantStatus.MAINTENANCE)
                
            self.history.append(step_state)
            
    def check_for_standby(self) -> None:
        """Check if the plant should enter STANDBY mode."""
        if self.get_state().status == PlantStatus.STANDBY:
            logger.debug("Plant is in STANDBY; skipping processing for this step.")
            return
        
    def _check_power_availability(self, available_power_W: float, required_power_W: float) -> None:
        """Check if power is available."""
        logger.info(f"Power check: available={available_power_W:.2f} W, required={required_power_W:.2f} W")
        if available_power_W < required_power_W:
            if available_power_W < self.spec.emergency_power_threshold_W:
                logger.error("Insufficient power; entering EMERGENCY mode.")
                raise ISRUPlantError(ISRUPlantErrorCode.INSUFFICIENT_POWER)         
            else:
                logger.warning("Power limited; production rates will be adjusted.")
                self._adjust_production_rate(available_power_W / required_power_W)
                raise ISRUPlantError(ISRUPlantErrorCode.POWER_LIMITED)
            
    def _update_power_systems(self, dt_s: float) -> None:
        """Update power system subsystems."""
        # Update solar array first to get available power
        # Set default Mars environment conditions if not already set
        # TODO: Pass in as a parameter at initialization
        self.solar_array.update_environment(
            incident_power=590.0,  # Mars average solar irradiance (W/m²)
            temperature=20.0,      # Panel temperature (°C)
            sun_azimuth=180.0,    # Sun position (degrees)
            sun_elevation=45.0,    # Sun elevation (degrees)
            dust_added=0.001,      # Minimal dust accumulation per step
            dt=dt_s
        )
        self.solar_array.step(dt_s)
        solar_output_W = self.solar_array.calculate_output()
        
        # Update KRUSTY reactor
        self.krusty.step(dt_s)
        krusty_output_W = self.krusty.calculate_output()
        
        # Calculate total power available before battery
        available_power_W = solar_output_W + krusty_output_W
        
        # Calculate power needed for reactors
        required_power_W = self._calculate_required_power_W()
        
        # Determine battery charge/discharge
        power_delta_W = available_power_W - required_power_W
        
        # Only use battery if we need more power
        if power_delta_W < 0:
            # Try to get the remaining power from battery
            battery_power = self.battery.calculate_output()
            if battery_power > 0:
                # Only discharge what we need, up to max battery output
                discharge_power = min(-power_delta_W, battery_power)
                self.battery.update(-discharge_power, dt_s)
                available_power_W += discharge_power
        else:
            # We have excess power, try to charge battery
            self.battery.update(power_delta_W, dt_s)
        
        self.battery.step(dt_s)

        logger.info(f"Power systems updated: solar={solar_output_W:.2f}W, krusty={krusty_output_W:.2f}W, "
                   f"required={required_power_W:.2f}W, battery_delta={power_delta_W:.2f}W, "
                   f"battery_soc={self.battery.state_of_charge:.2f}")

    def _calculate_available_power_W(self) -> float:
        """Calculate the total available power (W)."""
        return (self.solar_array.calculate_output() +
                self.battery.calculate_output() +
                self.krusty.calculate_output())

    def _calculate_required_power_W(self) -> float:
        """Calculate the total power required by the reactors (W)."""
        return (self.sabatier.calculate_power_consumption() +
                self.electrolysis.calculate_power_consumption())

    def _adjust_production_rate(self, power_ratio: float) -> None:
        """
        Adjust production rates by throttling reactors based on power availability.
        
        This implementation:
        1. Clamps power ratio between 0.1 (10%) and 1.0 (100%)
        2. For Electrolysis: Adjusts current density proportionally
        3. For Sabatier: Adjusts reaction rates via temperature control
        
        Args:
            power_ratio: Available power / Required power (0-1 scale)
        """
        # Clamp power ratio between 0.1 and 1.0 to prevent complete shutdown
        power_ratio = max(0.1, min(1.0, power_ratio))
        logger.info(f"Adjusting production rate to {power_ratio*100:.1f}% of nominal")
        
        # Adjust Electrolysis reactor
        if self.electrolysis.operational_status == OperationalStatus.RUNNING:
            current_density = self.electrolysis.current_density_A_per_m2
            target_density = power_ratio * self.electrolysis.spec.max_current_density_A_per_m2
            # Gradually adjust current density (max 20% change per step)
            max_change = 0.2 * self.electrolysis.spec.max_current_density_A_per_m2
            delta = target_density - current_density
            delta = max(-max_change, min(max_change, delta))
            self.electrolysis.current_density_A_per_m2 = current_density + delta
            logger.debug(f"Adjusted electrolysis current density to {self.electrolysis.current_density_A_per_m2:.2f} A/m²")
            
        # Adjust Sabatier reactor
        if self.sabatier.operational_status == OperationalStatus.RUNNING:
            # Control reaction rates through temperature
            # Normal operating range: 300°C to 400°C (573K to 673K)
            min_temp_K = 573
            max_temp_K = 673
            target_temp_K = min_temp_K + power_ratio * (max_temp_K - min_temp_K)
            current_temp_K = self.sabatier.state.temperature_K
            # Gradually adjust temperature (max 20K change per step)
            max_temp_change = 20
            delta_temp = target_temp_K - current_temp_K
            delta_temp = max(-max_temp_change, min(max_temp_change, delta_temp))
            self.sabatier.state.temperature_K = current_temp_K + delta_temp
            logger.debug(f"Adjusted Sabatier temperature to {self.sabatier.state.temperature_K:.2f} K")

    def _update_electrolysis(self, dt_s: float, available_power_W: float, available_h2o_mol: float) -> Tuple[Dict[ResourceType, float], float]:
        """Update electrolysis reactor state."""
        electrolysis_outputs = {resource: 0.0 for resource in ResourceType}

        # Run electrolysis first if water is available.
        if available_h2o_mol > 0 and self.electrolysis.operational_status == OperationalStatus.RUNNING:
            input_h2o_mol = min(available_h2o_mol, 50.0)  # Maximum 50.0 mol water per step
            logger.info(f"Electrolysis inputs: {input_h2o_mol:.3f} mol H2O")
            
            # Remove water from tank before electrolysis
            self.tanks[ResourceType.H2O].remove_resource(input_h2o_mol)
            
            # Pass water to electrolysis as mol/s
            electrolysis_inputs = {ResourceType.H2O: input_h2o_mol / dt_s}
            
            power_needed_electrolysis_W = self.electrolysis.calculate_power_consumption()
            logger.info(f"Electrolysis power needed: {power_needed_electrolysis_W:.2f} W")
            
            if power_needed_electrolysis_W <= available_power_W:
                electrolysis_outputs = self.electrolysis.step(dt_s, electrolysis_inputs)
                available_power_W -= power_needed_electrolysis_W
                logger.info(f"Electrolysis outputs: {electrolysis_outputs}")
                
                # Update storage tanks from electrolysis outputs
                for res, amt_per_s in electrolysis_outputs.items():
                    amt = amt_per_s * dt_s  # Convert from mol/s to mol
                    logger.debug(f"Adding {amt:.3f} mol of {res.name} to tanks")
                    self.tanks[res].add_resource(amt, self.electrolysis.state.temperature_K)
                    
            else:
                # If not enough power, return water to tank
                self.tanks[ResourceType.H2O].add_resource(input_h2o_mol, self.electrolysis.state.temperature_K)
                logger.warning(f"Not enough power for electrolysis: needed {power_needed_electrolysis_W:.2f} W, available {available_power_W:.2f} W")
        else:
            logger.warning("No water available for electrolysis.")
            
        return electrolysis_outputs, available_power_W
    
    def _update_sabatier(self, dt_s: float, available_power_W: float, available_co2_mol: float, available_h2_mol: float) -> Tuple[Dict[ResourceType, float], float]:
        """Update sabatier reactor state."""
        sabatier_outputs = {resource: 0.0 for resource in ResourceType}

        # Run Sabatier if sufficient CO2 and H2 are available.
        sufficient_reactants = (available_co2_mol > 0 and available_h2_mol >= 4)
        sabatier_operational = self.sabatier.operational_status == OperationalStatus.RUNNING
        in_startup_or_first_minute = self.get_status() == PlantStatus.STARTUP or self.time_s < 60.0
        if sufficient_reactants and (sabatier_operational or in_startup_or_first_minute):            
            # Gradually ramp up CO2 usage during first few cycles
            if in_startup_or_first_minute:
                max_co2_mol = 0.05  # Start with 1/10th of normal rate
            else:
                max_co2_mol = 0.5
                
            input_co2_mol = min(available_co2_mol, max_co2_mol)
            input_h2_mol = 4 * input_co2_mol
            logger.info(f"Sabatier inputs: CO2={input_co2_mol:.3f} mol, H2={input_h2_mol:.3f} mol")
            
            # Check reactor pressure before adding more reactants
            if self.sabatier.state.pressure_Pa > 1.8e6:  # 90% of limit
                logger.warning(f"Skipping Sabatier cycle - pressure too high: {self.sabatier.state.pressure_Pa/1e6:.2f} MPa")
                return
                
            logger.info(f"CO2 to use: {input_co2_mol:.3f} mol, H2 needed: {input_h2_mol:.3f} mol")
            if available_h2_mol >= input_h2_mol:
                # Remove reactants from tanks first
                self.tanks[ResourceType.CO2].remove_resource(input_co2_mol)
                self.tanks[ResourceType.H2].remove_resource(input_h2_mol)
                
                # Convert to mol/s for reactor
                sabatier_inputs = {
                    ResourceType.CO2: input_co2_mol / dt_s, 
                    ResourceType.H2: input_h2_mol / dt_s
                }
                
                power_needed_sabatier_W = self.sabatier.calculate_power_consumption()
                
                logger.info(f"Sabatier power needed: {power_needed_sabatier_W:.2f} W")
                
                if power_needed_sabatier_W <= available_power_W:
                    available_power_W -= power_needed_sabatier_W
                    sabatier_outputs = self.sabatier.step(dt_s, sabatier_inputs)
                    logger.info(f"Sabatier outputs: {sabatier_outputs}")
                    
                    # Convert outputs from mol/s to mol and update tanks
                    for res, amt_per_s in sabatier_outputs.items():
                        amt = amt_per_s * dt_s
                        # Skip CO (intermediate product) and only add products we have tanks for
                        if res != ResourceType.CO and res in self.tanks:
                            self.tanks[res].add_resource(amt, self.sabatier.state.temperature_K)
                else:
                    # Return reactants to tanks if reaction can't proceed
                    self.tanks[ResourceType.CO2].add_resource(input_co2_mol, self.sabatier.state.temperature_K)
                    self.tanks[ResourceType.H2].add_resource(input_h2_mol, self.sabatier.state.temperature_K)
                    logger.warning(f"Not enough power for Sabatier: needed {power_needed_sabatier_W:.2f} W, available {available_power_W:.2f} W")
            else:
                logger.warning(f"Insufficient H2 for Sabatier: required {input_h2_mol:.3f} mol, available {available_h2_mol:.3f} mol")
                
        return sabatier_outputs, available_power_W

    def _update_reactors(self, dt_s: float, available_power_W: float, state: ISRUPlantState) -> ISRUPlantState:
        """Update reactor states and process chemical reactions."""
        
        # Don't run reactors if the plant is not running. Pass if we're in STARTUP.
        pass_status = [PlantStatus.RUNNING, PlantStatus.STARTUP]
        if self.get_status() not in pass_status:
            logger.debug(f"Plant not running (status={self.get_status()}); skipping reactor updates.")
            return state

        available_h2o_mol = self.tanks[ResourceType.H2O].moles
        initial_available_power_W = available_power_W
        electrolysis_outputs, available_power_W = self._update_electrolysis(dt_s, available_power_W, available_h2o_mol)
        
        available_co2_mol = self.tanks[ResourceType.CO2].moles
        available_h2_mol = self.tanks[ResourceType.H2].moles
        sabatier_outputs, available_power_W = self._update_sabatier(dt_s, available_power_W, available_co2_mol, available_h2_mol)
        
        # Update state.
        state.total_CH4_produced_mol += sabatier_outputs.get(ResourceType.CH4, 0.0)
        state.total_O2_produced_mol += electrolysis_outputs.get(ResourceType.O2, 0.0)
        state.total_energy_consumed_J += initial_available_power_W * dt_s - available_power_W * dt_s
        return state

    def _update_storage(self, dt_s: float, state: ISRUPlantState) -> ISRUPlantState:
        """Update all storage tank states."""
        for tank in self.tanks.values():
            tank.step(dt_s)
        
        state.update_resource_levels(self.tanks)
        return state
    
    def start(self) -> bool:
        """
        Start the plant.

        This method transitions the plant from STANDBY to STARTUP,
        starts reactors, and ensures power systems are online.
        """
        if self.get_status() != PlantStatus.STANDBY:
            logger.warning("Plant cannot be started because it is not in STANDBY.")
            raise ISRUPlantError(ISRUPlantErrorCode.PLANT_NOT_IN_STANDBY)

        # Start power systems first and wait for KRUSTY to be fully online
        logger.info("Starting KRUSTY reactor...")
        self.krusty.start()
        
        # Wait for KRUSTY to reach full power
        # TODO: This is a hack to wait for KRUSTY to start.
        elapsed_time = 0.0
        dt = 1.0  # 1 second steps
        while elapsed_time < self.krusty.spec.startup_time:
            self.krusty.step(dt)
            elapsed_time += dt
            if self.krusty.status == PowerSystemStatus.ONLINE:
                logger.info(f"KRUSTY reactor online, output power: {self.krusty.calculate_output():.2f}W")
                break
            if elapsed_time >= self.krusty.spec.startup_time:
                logger.error("KRUSTY reactor failed to start")
                raise ISRUPlantError(ISRUPlantErrorCode.KRUSTY_FAILED_TO_START)

        # Start reactors and transition to STARTUP
        self.set_status(PlantStatus.STARTUP)
        self.sabatier.start()
        self.electrolysis.start()

        # Run startup sequence for reactors
        sabatier_startup_time = self.sabatier.spec.startup_time_s
        electrolysis_startup_time = self.electrolysis.spec.startup_time_s
        logger.info(f"Starting reactors - Sabatier startup time: {sabatier_startup_time:.2f}s, "
                   f"Electrolysis startup time: {electrolysis_startup_time:.2f}s")
        
        startup_time = max(sabatier_startup_time, electrolysis_startup_time)
        elapsed_time = 0.0
        
        self.step(startup_time)
        
        # Check if reactors are online
        if (self.sabatier.operational_status == OperationalStatus.RUNNING and 
            self.electrolysis.operational_status == OperationalStatus.RUNNING):
            logger.info("All reactors running")
        
        # Final status check
        if (self.sabatier.operational_status == OperationalStatus.RUNNING and 
            self.electrolysis.operational_status == OperationalStatus.RUNNING and
            self.krusty.status == PowerSystemStatus.ONLINE):
            self.set_status(PlantStatus.RUNNING)
            logger.info("Plant started successfully and now RUNNING")
        else:
            logger.error(f"Plant startup failed - not all systems running at time {elapsed_time:.2f}s")
            logger.error(f"Sabatier status: {self.sabatier.operational_status.name}")
            logger.error(f"{self.sabatier}")
            logger.error(f"Electrolysis status: {self.electrolysis.operational_status.name}")
            logger.error(f"{self.electrolysis}")
            logger.error(f"KRUSTY status: {self.krusty.status.name}")
            self.set_status(PlantStatus.STANDBY)
            raise ISRUPlantError(ISRUPlantErrorCode.PLANT_STARTUP_FAILED)

    def shutdown(self) -> bool:
        """
        Shutdown the plant.

        This method transitions the plant to SHUTDOWN and then to STANDBY,
        and it shuts down reactors while keeping power systems online for monitoring.
        """
        if self.get_status() not in [PlantStatus.RUNNING, PlantStatus.EMERGENCY]:
            logger.warning("Plant cannot be shutdown because it is not RUNNING or in EMERGENCY.")
            raise ISRUPlantError(ISRUPlantErrorCode.PLANT_NOT_RUNNING_OR_EMERGENCY)

        self.set_status(PlantStatus.SHUTDOWN)
        self.sabatier.shutdown()
        self.electrolysis.shutdown()
        self.set_status(PlantStatus.STANDBY)
        logger.info("Plant shutdown completed; now in STANDBY.")

    def get_status_report(self) -> Dict:
        """Return a dictionary report of the current status of all subsystems."""
        return {
            "state": self.get_state(),
            "power_systems": {
                "solar": {
                    "status": self.solar_array.status.name,
                    "output_W": self.solar_array.calculate_output(),
                    "dust_coverage": self.solar_array.get_panel_dust_coverage()
                },
                "battery": {
                    "status": self.battery.status.name,
                    "state_of_charge": self.battery.state_of_charge,
                    "output_W": self.battery.calculate_output()
                },
                "krusty": {
                    "status": self.krusty.status.name,
                    "output_W": self.krusty.calculate_output(),
                }
            },
            "reactors": {
                "sabatier": {
                    "status": self.sabatier.operational_status.name,
                    "temperature_K": self.sabatier.state.temperature_K,
                    "catalyst_degradation": getattr(self.sabatier, "catalyst_degradation", None)
                },
                "electrolysis": {
                    "status": self.electrolysis.operational_status.name,
                    "temperature_K": self.electrolysis.state.temperature_K,
                    "membrane_degradation": getattr(self.electrolysis, "membrane_degradation", None)
                }
            }
        }
