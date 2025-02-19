from dataclasses import dataclass
import logging
from typing import Dict, List, Optional
import numpy as np
from ..lib.isru_plant import ISRUPlant, ResourceType
from ..lib.environment import MarsEnvironment
from ..lib.reactor import OperationalStatus

logging.basicConfig(level=logging.INFO)

@dataclass
class TimeseriesData:
    timestamps: List[float]
    values: List[float]
    max_points: int = 100

    def add_point(self, timestamp: float, value: float):
        self.timestamps.append(timestamp)
        self.values.append(value)
        if len(self.timestamps) > self.max_points:
            self.timestamps.pop(0)
            self.values.pop(0)

class ISRUPlantSimulator:
    def __init__(self, plant: ISRUPlant):
        self.plant = plant
        self.time_of_day_hours = 0.0
        
        # Nominal flows for testing
        self.nominal_flows = {
            ResourceType.CO2: 100.0,
            ResourceType.H2O: 100.0,
        }
    
    def update(self):
        """Update all timeseries data from current plant state"""
        self.time_of_day_hours = (self.time_of_day_hours + 0.00028) % 24  # ~1 second real = 1 minute simulated
 
        
        # Add input resources to tanks if running
        if self.plant.status == OperationalStatus.RUNNING:
            # Add CO2 and H2O inputs
            self.plant.tanks[ResourceType.CO2].add_resource(self.nominal_flows[ResourceType.CO2], 298.15)
            self.plant.tanks[ResourceType.H2O].add_resource(self.nominal_flows[ResourceType.H2O], 298.15)
        
        # Step the plant
        self.plant.step(1.0)
        
        # Update power history
        
        # Calculate production rates (mol/s)
        new_ch4_total = status['total_CH4_produced_mol']
        new_o2_total = status['total_O2_produced_mol']
        
        dt = 1.0  # Assume 1s update interval
        ch4_rate = (new_ch4_total - self._last_ch4_total) / dt
        o2_rate = (new_o2_total - self._last_o2_total) / dt
        
        self.production_rates['CH4'].add_point(current_time, ch4_rate)
        self.production_rates['O2'].add_point(current_time, o2_rate)
        
        self._last_ch4_total = new_ch4_total
        self._last_o2_total = new_o2_total
        
        # Update tank levels
        for resource, tank in status['tank_levels_mol'].items():
            self.tank_data[resource].add_point(current_time, tank)
        
        # Update reactor inputs if plant is running
        if self.plant.status == PlantStatus.RUNNING:
            # Calculate available reactants from tanks
            co2_available = self.plant.tanks[ResourceType.CO2].moles
            h2o_available = self.plant.tanks[ResourceType.H2O].moles
            h2_available = self.plant.tanks[ResourceType.H2].moles
            
            # Calculate desired flow rates (limited by available amounts)
            co2_flow = min(self.nominal_flows[ResourceType.CO2], co2_available)
            h2o_flow = min(self.nominal_flows[ResourceType.H2O], h2o_available)
            
            # Calculate stoichiometric H2 needed for Sabatier (4:1 ratio with CO2)
            h2_needed = 4 * co2_flow
            h2_flow = min(h2_needed, h2_available)
            
            # If H2 is limiting, scale down CO2 to maintain stoichiometry
            if h2_flow < h2_needed:
                co2_flow = h2_flow / 4
            
            # Remove resources from tanks
            if co2_flow > 0:
                self.plant.tanks[ResourceType.CO2].remove_resource(co2_flow)
            if h2_flow > 0:
                self.plant.tanks[ResourceType.H2].remove_resource(h2_flow)
            if h2o_flow > 0:
                self.plant.tanks[ResourceType.H2O].remove_resource(h2o_flow)
            
            # Feed Sabatier reactor
            sabatier_inputs = {
                ResourceType.CO2: co2_flow,
                ResourceType.H2: h2_flow,
                ResourceType.CH4: 0.0,
                ResourceType.H2O: 0.0,
                ResourceType.O2: 0.0
            }
            sabatier_outputs = self.plant.sabatier.step(1.0, sabatier_inputs)
            
            # Add Sabatier products to tanks
            for resource, amount in sabatier_outputs.items():
                # Only add products we have tanks for and skip intermediate products (CO)
                if amount > 0 and resource != ResourceType.CO and resource in self.plant.tanks:
                    self.plant.tanks[resource].add_resource(amount, self.plant.sabatier.state.temperature_K)
            
            # Feed electrolysis reactor
            electrolysis_inputs = {
                ResourceType.H2O: h2o_flow,
                ResourceType.H2: 0.0,
                ResourceType.O2: 0.0
            }
            electrolysis_outputs = self.plant.electrolysis.step(1.0, electrolysis_inputs)
            
            # Add electrolysis products to tanks
            for resource, amount in electrolysis_outputs.items():
                if amount > 0:
                    self.plant.tanks[resource].add_resource(amount, self.plant.electrolysis.state.temperature_K) 