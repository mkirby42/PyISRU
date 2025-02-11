"""
Power transmission and distribution system implementation.
"""
from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, Optional, Set

from .base import PowerSystem, PowerSystemStatus, PowerPriority

class BusType(Enum):
    """Types of power distribution buses"""
    MAIN = auto()
    CRITICAL = auto()
    SECONDARY = auto()

@dataclass
class BusSpecification:
    """Power distribution bus specifications"""
    type: BusType
    voltage: float  # V
    max_power: float  # W
    priority: PowerPriority

class PowerBus:
    """Power distribution bus"""
    
    def __init__(self, spec: BusSpecification):
        self.spec = spec
        self.loads: Dict[str, float] = {}  # name -> power draw in watts
        self.current_power = 0.0  # W
        self.voltage = spec.voltage  # V
        self.is_active = True
        self.has_fault = False
        
    def add_load(self, name: str, power: float) -> bool:
        """Add a load to the bus"""
        if self.current_power + power > self.spec.max_power:
            return False
        self.loads[name] = power
        self.current_power += power
        return True
        
    def remove_load(self, name: str) -> None:
        """Remove a load from the bus"""
        if name in self.loads:
            self.current_power -= self.loads[name]
            del self.loads[name]
            
    def calculate_losses(self) -> float:
        """Calculate power losses on the bus"""
        # Simple I²R losses model
        current = self.current_power / self.voltage if self.voltage > 0 else 0
        resistance = 0.01  # Ohm
        return current * current * resistance

class TransmissionSystem(PowerSystem):
    """Power transmission and distribution system"""
    
    def __init__(self):
        super().__init__()
        
        # System state
        self.current_power = 0.0  # W
        self.voltage = 120.0  # V
        self.max_power = 90_000  # W (90kW - transmission limit)
        self.efficiency = 0.95
        
        # Protection thresholds
        self.undervoltage_threshold = 0.9  # per unit
        self.overvoltage_threshold = 1.1  # per unit
        self.overcurrent_threshold = 1.2  # per unit
        
        # Initialize buses
        self.buses: Dict[str, PowerBus] = {}
        self.bus_connections: Dict[str, Set[str]] = {}
        
        self._init_buses()
        self.status = PowerSystemStatus.ONLINE  # Set initial status to ONLINE
        
    def _init_buses(self) -> None:
        """Initialize the standard bus configuration"""
        specs = {
            'MAIN': BusSpecification(
                type=BusType.MAIN,
                voltage=120.0,
                max_power=100_000,
                priority=PowerPriority.HIGH
            ),
            'CRITICAL': BusSpecification(
                type=BusType.CRITICAL,
                voltage=120.0,
                max_power=20_000,
                priority=PowerPriority.CRITICAL
            ),
            'SECONDARY': BusSpecification(
                type=BusType.SECONDARY,
                voltage=120.0,
                max_power=80_000,
                priority=PowerPriority.LOW
            )
        }
        
        for name, spec in specs.items():
            self.add_bus(name, spec)
            
    def add_bus(self, name: str, spec: BusSpecification) -> bool:
        """Add a distribution bus"""
        if name in self.buses:
            return False
        self.buses[name] = PowerBus(spec)
        self.bus_connections[name] = set()
        return True
        
    def connect_buses(self, bus1: str, bus2: str) -> bool:
        """Connect two distribution buses"""
        if (bus1 not in self.buses or 
            bus2 not in self.buses or
            bus1 == bus2):
            return False
        self.bus_connections[bus1].add(bus2)
        self.bus_connections[bus2].add(bus1)
        return True
        
    def disconnect_buses(self, bus1: str, bus2: str) -> None:
        """Disconnect two distribution buses"""
        if bus1 in self.bus_connections and bus2 in self.bus_connections:
            self.bus_connections[bus1].discard(bus2)
            self.bus_connections[bus2].discard(bus1)
            
    def add_load(self, bus_name: str, load_name: str, power: float) -> bool:
        """Add a load to a bus"""
        if bus_name not in self.buses:
            return False
        return self.buses[bus_name].add_load(load_name, power)
        
    def remove_load(self, bus_name: str, load_name: str) -> None:
        """Remove a load from a bus"""
        if bus_name in self.buses:
            self.buses[bus_name].remove_load(load_name)
            
    def calculate_output(self) -> float:
        """Calculate total system power output"""
        if self.status != PowerSystemStatus.ONLINE:
            return 0.0
            
        # Calculate total load power
        load_power = sum(bus.current_power for bus in self.buses.values())
        
        # Calculate losses based on load power
        transmission_losses = self._calculate_losses(load_power)
        
        # Update and return total system power
        self.current_power = load_power + transmission_losses
        return self.current_power
        
    def _calculate_losses(self, load_power: float) -> float:
        """Calculate transmission system losses"""
        # Base losses from transmission inefficiency
        base_losses = load_power * (1.0 - self.efficiency)
        
        # Additional losses from buses
        bus_losses = sum(bus.calculate_losses() for bus in self.buses.values())
        
        return base_losses + bus_losses
        
    def _check_protection(self) -> bool:
        """Check if protection systems should trip"""
        # Check voltage limits first
        under_threshold = self.undervoltage_threshold * 120.0
        over_threshold = self.overvoltage_threshold * 120.0
        print(f"Voltage check: actual={self.voltage:.1f}V, range={under_threshold:.1f}V-{over_threshold:.1f}V")
        if (self.voltage < under_threshold or
            self.voltage > over_threshold):
            print("Voltage trip!")
            return True
            
        # Then check power limits including losses
        load_power = sum(bus.current_power for bus in self.buses.values())
        losses = self._calculate_losses(load_power)
        total_power = load_power + losses
        max_power = self.max_power * self.overcurrent_threshold
        print(f"Power check: actual={total_power:.0f}W (load={load_power:.0f}W, losses={losses:.0f}W), max={max_power:.0f}W")
        if total_power > max_power:
            print("Overpower trip!")
            return True
            
        return False
        
    def isolate_fault(self, bus_name: str) -> None:
        """Isolate a faulted bus"""
        if bus_name in self.buses:
            self.buses[bus_name].is_active = False
            self.buses[bus_name].has_fault = True
            
            # Disconnect from other buses
            for connected in list(self.bus_connections[bus_name]):
                self.disconnect_buses(bus_name, connected)
                
    def step(self, dt: float) -> None:
        """Update transmission system state"""
        super().step(dt)
        
        if self.status != PowerSystemStatus.OFFLINE:
            # First update power and losses
            self.calculate_output()
            
            # Then check protection systems
            if self._check_protection():
                self.status = PowerSystemStatus.FAULT 