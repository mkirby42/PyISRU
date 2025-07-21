from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Tuple
from enum import Enum
from dataclasses import dataclass
import logging
import time

from core.plant_state import PlantState
from core.power_budget import PowerRequest

logger = logging.getLogger(__name__)

class ModuleStatus(Enum):
    """Module operational status."""
    OK = "ok"
    DEGRADED = "degraded" 
    IDLE = "idle"
    SHUTDOWN = "shutdown"

@dataclass
class OperatingLimits:
    """Operating limits for a module."""
    max_temperature_k: Optional[float] = None
    max_pressure_kpa: Optional[float] = None
    max_flow_rate_kg_hr: Optional[float] = None
    min_flow_rate_kg_hr: Optional[float] = None
    min_power_kw: float = 0.0
    max_power_kw: Optional[float] = None
    safety_temp_margin: float = 0.9  # 90% of max temp
    
class BaseModule(ABC):
    """
    Base class for all ISRU plant modules.
    Provides common functionality for status management, power handling, and simulation interface.
    """
    
    def __init__(self, name: str, priority: int = 3):
        self.name = name
        self.priority = priority  # 1=critical, 5=deferrable
        self.status = ModuleStatus.OK
        
        # Operating state
        self.current_temperature_k: float = 273.0  # Room temp default
        self.current_pressure_kpa: float = 101.3   # 1 atm default
        self.current_flow_rate_kg_hr: float = 0.0
        
        # Power state
        self.power_requested_kw: float = 0.0
        self.power_allocated_kw: float = 0.0
        self.min_power_kw: float = 0.0
        self.max_power_kw: Optional[float] = None
        
        # Shutdown/recovery state
        self.is_shutdown: bool = False
        self.shutdown_start_time: float = 0.0
        self.recovery_time_s: float = 0.0  # How long to wait before restart
        
        # Operating limits
        self.limits = OperatingLimits()
        
        # Performance degradation
        self.efficiency_factor: float = 1.0  # 1.0 = 100% efficiency
        
        # Statistics
        self.total_operating_time_s: float = 0.0
        self.total_energy_consumed_kwh: float = 0.0
        
    def request_power(self, plant_state: PlantState, requested_kw: float) -> float:
        """
        Request power from the plant power budget.
        Returns the actual power allocated (may be less than requested).
        """
        self.power_requested_kw = requested_kw
        
        # Create power request
        request = PowerRequest(
            module_name=self.name,
            requested_kw=requested_kw,
            min_power_kw=self.min_power_kw,
            max_power_kw=self.max_power_kw,
            priority=self.priority
        )
        
        # Submit to power budget
        plant_state.power_budget.add_request(request)
        
        return requested_kw  # Actual allocation happens during power budget resolution
    
    def apply_power_allocation(self, allocated_kw: float):
        """Apply the power allocation result from the power budget."""
        self.power_allocated_kw = allocated_kw
        
        # Determine if we have sufficient power to operate
        if allocated_kw < self.min_power_kw and not self.is_shutdown:
            logger.warning(f"{self.name}: Insufficient power ({allocated_kw:.1f} kW < {self.min_power_kw:.1f} kW min), going idle")
            self.status = ModuleStatus.IDLE
        elif self.status == ModuleStatus.IDLE and allocated_kw >= self.min_power_kw:
            logger.info(f"{self.name}: Power restored, resuming operation")
            self.status = ModuleStatus.OK
    
    def check_operating_limits(self, plant_state: PlantState) -> bool:
        """
        Check if module is operating within safe limits.
        Returns True if within limits, False if shutdown required.
        """
        if self.is_shutdown:
            return False
        
        # Temperature check
        if (self.limits.max_temperature_k and 
            self.current_temperature_k > self.limits.max_temperature_k):
            logger.error(f"{self.name}: Temperature {self.current_temperature_k:.1f}K exceeds "
                        f"max {self.limits.max_temperature_k:.1f}K - SHUTDOWN")
            self._initiate_shutdown(plant_state.current_time, "Temperature overage")
            return False
        
        # Temperature warning (soft limit)
        soft_temp_limit = (self.limits.max_temperature_k * self.limits.safety_temp_margin 
                          if self.limits.max_temperature_k else None)
        if (soft_temp_limit and 
            self.current_temperature_k > soft_temp_limit and 
            self.status == ModuleStatus.OK):
            logger.warning(f"{self.name}: Temperature {self.current_temperature_k:.1f}K approaching "
                         f"limit {self.limits.max_temperature_k:.1f}K - degrading performance")
            self.status = ModuleStatus.DEGRADED
            self.efficiency_factor = 0.7  # Reduce to 70% efficiency
        
        # Pressure check
        if (self.limits.max_pressure_kpa and 
            self.current_pressure_kpa > self.limits.max_pressure_kpa):
            logger.error(f"{self.name}: Pressure {self.current_pressure_kpa:.1f}kPa exceeds "
                        f"max {self.limits.max_pressure_kpa:.1f}kPa - SHUTDOWN")
            self._initiate_shutdown(plant_state.current_time, "Pressure overage")
            return False
        
        # Flow rate checks
        if (self.limits.max_flow_rate_kg_hr and 
            self.current_flow_rate_kg_hr > self.limits.max_flow_rate_kg_hr):
            logger.warning(f"{self.name}: Flow rate {self.current_flow_rate_kg_hr:.1f}kg/hr exceeds "
                         f"max {self.limits.max_flow_rate_kg_hr:.1f}kg/hr - throttling")
            self.current_flow_rate_kg_hr = self.limits.max_flow_rate_kg_hr
        
        return True
    
    def _initiate_shutdown(self, current_time: float, reason: str):
        """Initiate emergency shutdown."""
        self.is_shutdown = True
        self.status = ModuleStatus.SHUTDOWN
        self.shutdown_start_time = current_time
        self.recovery_time_s = 3600.0  # 1 hour default recovery time
        self.power_requested_kw = 0.0
        logger.error(f"{self.name}: SHUTDOWN initiated - {reason}")
    
    def attempt_restart(self, current_time: float) -> bool:
        """Attempt to restart after shutdown if recovery time has elapsed."""
        if not self.is_shutdown:
            return True
        
        if current_time - self.shutdown_start_time >= self.recovery_time_s:
            self.is_shutdown = False
            self.status = ModuleStatus.OK
            self.efficiency_factor = 1.0
            logger.info(f"{self.name}: Restart successful after {self.recovery_time_s/3600:.1f}h recovery")
            return True
        
        return False
    
    def update_statistics(self, dt_seconds: float):
        """Update module statistics."""
        if self.status == ModuleStatus.OK or self.status == ModuleStatus.DEGRADED:
            self.total_operating_time_s += dt_seconds
        
        # Energy consumption (kW * hours)
        energy_kwh = self.power_allocated_kw * (dt_seconds / 3600.0)
        self.total_energy_consumed_kwh += energy_kwh
    
    @abstractmethod
    def simulate(self, plant_state: PlantState, dt_seconds: float) -> Dict[str, Any]:
        """
        Run one simulation timestep.
        
        Args:
            plant_state: Central plant state
            dt_seconds: Time step duration in seconds
            
        Returns:
            Dict containing simulation results and state changes
        """
        pass
    
    def save_state(self) -> Dict[str, Any]:
        """Save module state for persistence."""
        return {
            "status": self.status.value,
            "current_temperature_k": self.current_temperature_k,
            "current_pressure_kpa": self.current_pressure_kpa,
            "current_flow_rate_kg_hr": self.current_flow_rate_kg_hr,
            "power_requested_kw": self.power_requested_kw,
            "power_allocated_kw": self.power_allocated_kw,
            "is_shutdown": self.is_shutdown,
            "shutdown_start_time": self.shutdown_start_time,
            "recovery_time_s": self.recovery_time_s,
            "efficiency_factor": self.efficiency_factor,
            "total_operating_time_s": self.total_operating_time_s,
            "total_energy_consumed_kwh": self.total_energy_consumed_kwh
        }
    
    def load_state(self, state_data: Dict[str, Any]):
        """Load module state from saved data."""
        self.status = ModuleStatus(state_data.get("status", "ok"))
        self.current_temperature_k = state_data.get("current_temperature_k", 273.0)
        self.current_pressure_kpa = state_data.get("current_pressure_kpa", 101.3)
        self.current_flow_rate_kg_hr = state_data.get("current_flow_rate_kg_hr", 0.0)
        self.power_requested_kw = state_data.get("power_requested_kw", 0.0)
        self.power_allocated_kw = state_data.get("power_allocated_kw", 0.0)
        self.is_shutdown = state_data.get("is_shutdown", False)
        self.shutdown_start_time = state_data.get("shutdown_start_time", 0.0)
        self.recovery_time_s = state_data.get("recovery_time_s", 0.0)
        self.efficiency_factor = state_data.get("efficiency_factor", 1.0)
        self.total_operating_time_s = state_data.get("total_operating_time_s", 0.0)
        self.total_energy_consumed_kwh = state_data.get("total_energy_consumed_kwh", 0.0)
    
    def get_status_summary(self) -> Dict[str, Any]:
        """Get current module status summary."""
        return {
            "name": self.name,
            "status": self.status.value,
            "power_kw": self.power_allocated_kw,
            "efficiency": self.efficiency_factor,
            "temperature_k": self.current_temperature_k,
            "pressure_kpa": self.current_pressure_kpa,
            "flow_rate_kg_hr": self.current_flow_rate_kg_hr,
            "uptime_hours": self.total_operating_time_s / 3600.0,
            "energy_consumed_kwh": self.total_energy_consumed_kwh
        }
    
    def __repr__(self) -> str:
        return (f"{self.__class__.__name__}({self.name}: {self.status.value}, "
                f"{self.power_allocated_kw:.1f}kW, {self.efficiency_factor:.1%} eff)") 