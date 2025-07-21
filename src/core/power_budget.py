from typing import Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)

@dataclass
class PowerRequest:
    """Represents a power request from a module."""
    module_name: str
    requested_kw: float
    min_power_kw: float = 0.0
    max_power_kw: Optional[float] = None
    priority: int = 3  # 1=critical, 5=deferrable
    
    def __post_init__(self):
        if self.requested_kw < 0:
            raise ValueError("Requested power cannot be negative")
        if self.min_power_kw < 0:
            raise ValueError("Minimum power cannot be negative")
        if self.max_power_kw is not None and self.max_power_kw < self.min_power_kw:
            raise ValueError("Maximum power cannot be less than minimum power")
        if not 1 <= self.priority <= 5:
            raise ValueError("Priority must be between 1 (critical) and 5 (deferrable)")

@dataclass 
class PowerAllocation:
    """Represents allocated power to a module."""
    module_name: str
    requested_kw: float
    allocated_kw: float
    priority: int
    
    @property
    def deficit_kw(self) -> float:
        """Power shortage for this module."""
        return max(0, self.requested_kw - self.allocated_kw)
    
    @property
    def allocation_fraction(self) -> float:
        """Fraction of requested power allocated (0-1)."""
        if self.requested_kw == 0:
            return 1.0
        return self.allocated_kw / self.requested_kw

class PowerBudget:
    """Manages power generation, consumption, and allocation across plant modules."""
    
    def __init__(self):
        self.available_kw: float = 0.0
        self.generation_kw: float = 0.0
        self.requests: List[PowerRequest] = []
        self.allocations: List[PowerAllocation] = []
        self.total_demand_kw: float = 0.0
        self.total_allocated_kw: float = 0.0
        self.total_deficit_kw: float = 0.0
        
    def set_generation(self, generation_kw: float):
        """Set available power generation."""
        if generation_kw < 0:
            raise ValueError("Power generation cannot be negative")
        self.generation_kw = generation_kw
        self.available_kw = generation_kw
    
    def add_request(self, request: PowerRequest):
        """Add a power request from a module."""
        # Remove any existing request from this module
        self.requests = [r for r in self.requests if r.module_name != request.module_name]
        self.requests.append(request)
    
    def allocate_power(self) -> Dict[str, float]:
        """
        Allocate available power to modules based on priority and constraints.
        Returns dict of {module_name: allocated_kw}.
        """
        self.allocations.clear()
        
        if not self.requests:
            self.total_demand_kw = 0.0
            self.total_allocated_kw = 0.0
            self.total_deficit_kw = 0.0
            return {}
        
        # Calculate total demand
        self.total_demand_kw = sum(req.requested_kw for req in self.requests)
        
        # Sort by priority (1=highest priority)
        sorted_requests = sorted(self.requests, key=lambda r: (r.priority, r.module_name))
        
        remaining_power = self.available_kw
        allocation_dict = {}
        
        for request in sorted_requests:
            # Calculate allocation for this module
            if remaining_power <= 0:
                allocated = 0.0
            else:
                # Try to give full requested amount, but respect constraints
                desired = request.requested_kw
                max_allowed = request.max_power_kw if request.max_power_kw else desired
                
                allocated = min(desired, max_allowed, remaining_power)
                
                # Ensure we meet minimum requirements if possible
                if allocated < request.min_power_kw and remaining_power >= request.min_power_kw:
                    allocated = min(request.min_power_kw, remaining_power)
            
            allocation = PowerAllocation(
                module_name=request.module_name,
                requested_kw=request.requested_kw,
                allocated_kw=allocated,
                priority=request.priority
            )
            
            self.allocations.append(allocation)
            allocation_dict[request.module_name] = allocated
            remaining_power -= allocated
        
        # Update totals
        self.total_allocated_kw = sum(alloc.allocated_kw for alloc in self.allocations)
        self.total_deficit_kw = sum(alloc.deficit_kw for alloc in self.allocations)
        
        # Log power shortages
        if self.total_deficit_kw > 0:
            logger.warning(f"Power shortage: {self.total_deficit_kw:.1f} kW deficit")
            for alloc in self.allocations:
                if alloc.deficit_kw > 0:
                    logger.warning(f"  {alloc.module_name}: {alloc.deficit_kw:.1f} kW short "
                                 f"({alloc.allocation_fraction:.1%} of requested)")
        
        return allocation_dict
    
    def get_allocation_for_module(self, module_name: str) -> Optional[PowerAllocation]:
        """Get power allocation for a specific module."""
        for alloc in self.allocations:
            if alloc.module_name == module_name:
                return alloc
        return None
    
    def clear_requests(self):
        """Clear all power requests (typically called each timestep)."""
        self.requests.clear()
        self.allocations.clear()
        self.total_demand_kw = 0.0
        self.total_allocated_kw = 0.0
        self.total_deficit_kw = 0.0
    
    @property
    def power_utilization_fraction(self) -> float:
        """Fraction of available power being used (0-1)."""
        if self.available_kw == 0:
            return 0.0
        return self.total_allocated_kw / self.available_kw
    
    @property
    def is_power_shortage(self) -> bool:
        """True if there's insufficient power to meet all requests."""
        return self.total_deficit_kw > 0
    
    def __repr__(self) -> str:
        return (f"PowerBudget(gen: {self.generation_kw:.1f} kW, "
                f"demand: {self.total_demand_kw:.1f} kW, "
                f"allocated: {self.total_allocated_kw:.1f} kW, "
                f"deficit: {self.total_deficit_kw:.1f} kW)") 