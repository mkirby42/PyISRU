"""
Solar array implementation managing multiple panels and trackers.
"""
from dataclasses import dataclass
import logging
from typing import List, Optional
import numpy as np

from ..base import ThermalPowerSystem, PowerSystemStatus
from .panel import SolarPanel, SolarPanelSpecification
from .tracker import Tracker, TrackerSpecification, TrackingType

logger = logging.getLogger(__name__)

@dataclass
class SolarArraySpecification:
    """Solar array specifications"""
    n_panels: int                    # Number of panels
    panel_spec: SolarPanelSpecification
    tracker_spec: Optional[TrackerSpecification] = None
    
    def __post_init__(self):
        """Validate specifications"""
        if self.n_panels <= 0:
            raise ValueError("Number of panels must be positive")

    def __repr__(self):
        return (f"SolarArraySpecification(n_panels={self.n_panels}, "
                f"panel_spec={self.panel_spec}, tracker_spec={self.tracker_spec})")

class SolarArray(ThermalPowerSystem):
    """Models a collection of solar panels with optional tracking"""
    
    def __init__(self, spec: SolarArraySpecification):
        super().__init__()
        self.spec = spec
        self.status = PowerSystemStatus.ONLINE
        
        # Create panels and trackers
        self.panels: List[SolarPanel] = []
        self.trackers: List[Tracker] = []
        
        for _ in range(spec.n_panels):
            self.panels.append(SolarPanel(spec.panel_spec))
            if spec.tracker_spec:
                self.trackers.append(Tracker(spec.tracker_spec))
                
        # Set thermal limits from panel spec
        self.max_temp = self.spec.panel_spec.max_temp + 273.15
        self.min_temp = self.spec.panel_spec.min_temp + 273.15
                
        # Fault tracking
        self.fault_condition: Optional[str] = None

    def __repr__(self):
        return (f"SolarArray(status={self.status}, "
                f"n_panels={len(self.panels)}, "
                f"n_trackers={len(self.trackers)}, "
                f"fault_condition={self.fault_condition})")
        
    def calculate_output(self) -> float:
        """Calculate total array power output in Watts"""
        if self.status == PowerSystemStatus.FAULT:
            return 0.0
            
        try:
            # Sum panel outputs
            panel_power = sum(panel.calculate_output() for panel in self.panels)
            logger.debug(f"Panel power: {panel_power}W")
            
            # Subtract tracker power consumption (trackers return negative power)
            tracker_power = sum(tracker.calculate_output() for tracker in self.trackers)
            logger.debug(f"Tracker power: {tracker_power}W")
            
            # Since tracker power is already negative, adding it effectively subtracts
            total_power = panel_power + tracker_power
            logger.debug(f"Total power: {total_power}W")
            return total_power
            
        except Exception as e:
            self.status = PowerSystemStatus.FAULT
            self.fault_condition = f"Power calculation error: {str(e)}"
            return 0.0
            
    def update_environment(self, 
                          incident_power: float,
                          temperature: float,
                          sun_azimuth: float,
                          sun_elevation: float,
                          dust_added: float,
                          dt: float) -> None:
        """
        Update array state based on environmental conditions
        Args:
            incident_power: Solar power at panel surface (W/m²)
            temperature: Panel temperature (°C)
            sun_azimuth: Sun's azimuth angle (degrees)
            sun_elevation: Sun's elevation angle (degrees)
            dust_added: Amount of dust added this step (0-1 scale)
            dt: Time step in seconds
        """
        if dt <= 0:
            raise ValueError("Time step must be positive")
            
        try:
            # Update trackers first
            for tracker in self.trackers:
                # Set new targets
                tracker.track_sun(sun_azimuth, sun_elevation)
                
                # Update position
                tracker.update(dt)
                
            # Update panels using tracker angles
            for i, panel in enumerate(self.panels):
                if i < len(self.trackers):
                    # Get tracker angles
                    az, el = self.trackers[i].get_angles()
                    # For tracked panels, incidence angle is always 0
                    # since panel faces the sun
                    angle = 0.0
                else:
                    # Fixed panels point straight up
                    # Incidence angle is complement of elevation
                    angle = np.deg2rad(90.0 - el)
                    
                panel.update_environment(
                    incident_power=incident_power,
                    temperature=temperature,
                    angle_of_incidence=angle,
                    dust_added=dust_added
                )
                
            # Update array temperature (convert °C to K)
            self.temperature = temperature + 273.15
                
            # Update array status based on components
            self._update_status()
            
        except Exception as e:
            self.status = PowerSystemStatus.FAULT
            self.fault_condition = f"Environment update error: {str(e)}"
            
    def manage_thermal(self, dt: float) -> None:
        """Handle thermal state changes"""
        # Store current fault state
        had_temp_fault = self.fault_condition and "Temperature" in self.fault_condition
        
        # Check array temperature limits first
        if self.temperature > self.max_temp or self.temperature < self.min_temp:
            self.status = PowerSystemStatus.FAULT
            self.fault_condition = f"Temperature {self.temperature-273.15:.1f}°C outside limits"
            return  # Exit early to preserve temperature fault
        elif had_temp_fault:
            # Clear temperature fault
            self.status = PowerSystemStatus.ONLINE
            self.fault_condition = None
            
        # Update panels thermal management
        for panel in self.panels:
            panel.manage_thermal(dt)
                
        # Only update component status if we don't have a temperature fault
        if not (self.status == PowerSystemStatus.FAULT and "Temperature" in str(self.fault_condition)):
            self._update_status()
            
    def _update_status(self) -> None:
        """Update array status based on component states"""
        # Count component states
        n_faulted = sum(1 for p in self.panels if p.status == PowerSystemStatus.FAULT)
        n_faulted += sum(1 for t in self.trackers if t.status == PowerSystemStatus.FAULT)
        
        n_degraded = sum(1 for p in self.panels if p.status == PowerSystemStatus.DEGRADED)
        n_degraded += sum(1 for t in self.trackers if t.status == PowerSystemStatus.DEGRADED)
        
        # Update array status
        if n_faulted > 0:
            self.status = PowerSystemStatus.FAULT
            self.fault_condition = f"{n_faulted} components faulted"
        elif n_degraded > 0:
            self.status = PowerSystemStatus.DEGRADED
        else:
            self.status = PowerSystemStatus.ONLINE
            self.fault_condition = None
            
    def clean(self) -> None:
        """Clean all panels"""
        for panel in self.panels:
            panel.clean()
        
    def get_panel_temperatures(self) -> List[float]:
        """Get temperatures of all panels"""
        return [(panel.temperature - 273.15) for panel in self.panels]  # Convert K to °C
        
    def get_panel_dust_coverage(self) -> List[float]:
        """Get dust coverage of all panels"""
        return [panel.dust_coverage for panel in self.panels]
        
    def get_panel_degradation(self) -> List[float]:
        """Get total degradation of all panels"""
        return [
            panel.uv_degradation + 
            panel.radiation_degradation + 
            panel.thermal_cycle_degradation
            for panel in self.panels
        ]
        
    def step(self, dt: float) -> None:
        """Advance array state by one time step"""
        # logger.info(f"Solar array step: dt={dt:.2f} s, status={self.status.name}")
        # Update trackers
        for tracker in self.trackers:
            tracker.update(dt)
            
        # Update panels
        for panel in self.panels:
            panel.step(dt)

        # Call parent step last to handle thermal management
        super().step(dt)