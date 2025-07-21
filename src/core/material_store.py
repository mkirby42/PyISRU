from typing import Optional
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)

@dataclass
class MaterialStore:
    """Represents a material storage container with optional physical properties."""
    
    name: str
    mass_kg: float = 0.0
    pressure_kpa: Optional[float] = None
    temperature_k: Optional[float] = None
    capacity_kg: Optional[float] = None  # None = unlimited
    
    def __post_init__(self):
        if self.mass_kg < 0:
            raise ValueError(f"Mass cannot be negative: {self.mass_kg}")
        if self.capacity_kg is not None and self.capacity_kg <= 0:
            raise ValueError(f"Capacity must be positive: {self.capacity_kg}")
    
    @property
    def available_capacity_kg(self) -> float:
        """Returns remaining storage capacity in kg."""
        if self.capacity_kg is None:
            return float('inf')
        return max(0, self.capacity_kg - self.mass_kg)
    
    @property
    def fill_fraction(self) -> float:
        """Returns fraction of capacity filled (0-1)."""
        if self.capacity_kg is None:
            return 0.0
        return min(1.0, self.mass_kg / self.capacity_kg)
    
    def store(self, mass_kg: float) -> float:
        """
        Store material in container.
        Returns actual amount stored (may be less than requested due to capacity).
        """
        if mass_kg < 0:
            raise ValueError(f"Cannot store negative mass: {mass_kg}")
        
        if mass_kg == 0:
            return 0.0
            
        # Calculate how much we can actually store
        available = self.available_capacity_kg
        actual_stored = min(mass_kg, available)
        
        self.mass_kg += actual_stored
        
        if actual_stored < mass_kg:
            logger.warning(f"{self.name}: Only stored {actual_stored:.3f} kg of {mass_kg:.3f} kg requested (capacity limit)")
        
        return actual_stored
    
    def withdraw(self, mass_kg: float) -> float:
        """
        Withdraw material from container.
        Returns actual amount withdrawn (may be less than requested due to availability).
        """
        if mass_kg < 0:
            raise ValueError(f"Cannot withdraw negative mass: {mass_kg}")
        
        if mass_kg == 0:
            return 0.0
            
        # Calculate how much we can actually withdraw
        actual_withdrawn = min(mass_kg, self.mass_kg)
        
        self.mass_kg -= actual_withdrawn
        
        if actual_withdrawn < mass_kg:
            logger.warning(f"{self.name}: Only withdrew {actual_withdrawn:.3f} kg of {mass_kg:.3f} kg requested (insufficient material)")
        
        return actual_withdrawn
    
    def set_physical_properties(self, pressure_kpa: Optional[float] = None, 
                               temperature_k: Optional[float] = None):
        """Update physical properties (for gas handling, thermal modeling)."""
        if pressure_kpa is not None:
            self.pressure_kpa = pressure_kpa
        if temperature_k is not None:
            self.temperature_k = temperature_k
    
    def __repr__(self) -> str:
        props = [f"{self.mass_kg:.2f} kg"]
        if self.capacity_kg:
            props.append(f"cap: {self.capacity_kg:.1f} kg")
        if self.pressure_kpa:
            props.append(f"{self.pressure_kpa:.1f} kPa")
        if self.temperature_k:
            props.append(f"{self.temperature_k:.1f} K")
        
        return f"MaterialStore({self.name}: {', '.join(props)})" 