"""
Solar panel implementation with basic efficiency and dust modeling.
"""
from dataclasses import dataclass
from typing import Optional

import numpy as np

from ..base import ThermalPowerSystem, PowerSystemStatus


@dataclass
class SolarPanelSpecification:
    area: float                # Panel area in m²
    base_efficiency: float     # Base efficiency at standard conditions
    max_temp: float           # Maximum safe temperature (°C)
    min_temp: float           # Minimum safe temperature (°C)
    mass: float               # Panel mass in kg
    dust_tolerance: float     # Maximum dust coverage before degraded state
    
    def __post_init__(self):
        """Validate specifications"""
        if self.area <= 0:
            raise ValueError("Area must be positive")
        if not 0 < self.base_efficiency <= 1:
            raise ValueError("Base efficiency must be between 0 and 1")
        if self.max_temp <= self.min_temp:
            raise ValueError("Maximum temperature must be greater than minimum")
        if self.mass <= 0:
            raise ValueError("Mass must be positive")
        if not 0 < self.dust_tolerance <= 1:
            raise ValueError("Dust tolerance must be between 0 and 1")


class SolarPanel(ThermalPowerSystem):
    """Models a single solar panel with dust accumulation and basic protection"""
    
    def __init__(self, spec: SolarPanelSpecification):
        super().__init__()
        self.spec = spec
        self.status = PowerSystemStatus.ONLINE
        
        # Operating state
        self.dust_coverage: float = 0.0  # 0-1 scale
        self.incident_power: float = 0.0  # W/m²
        self.angle_of_incidence: float = 0.0  # radians
        
        # Set thermal limits from spec (convert °C to K)
        self.max_temp = self.spec.max_temp + 273.15
        self.min_temp = self.spec.min_temp + 273.15
        
        # Fault tracking
        self.fault_condition: Optional[str] = None
        
    def calculate_output(self) -> float:
        """Calculate power output in Watts"""
        if self.status == PowerSystemStatus.FAULT:
            return 0.0
            
        try:
            # Validate inputs first
            if not np.isfinite(self.angle_of_incidence):
                raise ValueError("Invalid angle of incidence")
            if not np.isfinite(self.incident_power):
                raise ValueError("Invalid incident power")
                
            # Basic power calculation
            effective_area = self.spec.area * np.cos(self.angle_of_incidence)
            if not np.isfinite(effective_area):
                raise ValueError("Invalid effective area calculation")
                
            incident_power = self.incident_power * effective_area
            if not np.isfinite(incident_power):
                raise ValueError("Invalid incident power calculation")
            
            # Account for dust coverage
            dust_factor = 1.0 - self.dust_coverage
            
            # Calculate output power
            output_power = incident_power * self.spec.base_efficiency * dust_factor
            if not np.isfinite(output_power):
                raise ValueError("Invalid output power calculation")
                
            return max(0.0, output_power)
            
        except Exception as e:
            self.status = PowerSystemStatus.FAULT
            self.fault_condition = f"Power calculation error: {str(e)}"
            return 0.0
            
    def clean(self) -> None:
        """Clean the panel surface"""
        self.dust_coverage = 0.0
        if self.status == PowerSystemStatus.DEGRADED:
            self.status = PowerSystemStatus.ONLINE
            
    def update_environment(self, 
                          incident_power: float,
                          temperature: float,
                          angle_of_incidence: float,
                          dust_added: float) -> None:
        """
        Update panel state based on environmental conditions
        Args:
            incident_power: Solar power at panel surface (W/m²)
            temperature: Panel temperature (°C)
            angle_of_incidence: Angle between panel normal and sun (radians)
            dust_added: Amount of dust added this step (0-1 scale)
        """
        self.incident_power = max(0.0, incident_power)
        self.temperature = temperature + 273.15  # Convert °C to K
        self.angle_of_incidence = angle_of_incidence
        self.dust_coverage = min(1.0, self.dust_coverage + dust_added)
        
        # Update status based on dust coverage
        if self.dust_coverage > self.spec.dust_tolerance:
            self.status = PowerSystemStatus.DEGRADED
        elif self.status == PowerSystemStatus.DEGRADED and self.dust_coverage <= self.spec.dust_tolerance:
            self.status = PowerSystemStatus.ONLINE
            
    def manage_thermal(self, dt: float) -> None:
        """Handle thermal state changes"""
        # Call parent thermal management first
        super().manage_thermal(dt)
        
        # Check temperature limits
        if self.temperature > self.max_temp or self.temperature < self.min_temp:
            self.status = PowerSystemStatus.FAULT
            self.fault_condition = f"Temperature {self.temperature-273.15:.1f}°C outside limits"
        elif self.status == PowerSystemStatus.FAULT and self.fault_condition and "Temperature" in self.fault_condition:
            # Only clear temperature faults, leave other faults alone
            self.status = PowerSystemStatus.ONLINE
            self.fault_condition = None 