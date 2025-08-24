from enum import Enum
from .units import Q_, mol, ensure_units

class ResourceType(Enum):
    CO2 = "CO2"
    H2 = "H2"
    CH4 = "CH4"
    H2O = "H2O"

class ResourceBus:
    def __init__(self):
        self.resources = {}

    def add_resource(self, resource_type, resource_amount):
        """Add resource with units validation"""
        if isinstance(resource_type, str):
            resource_type = ResourceType(resource_type)
        
        # Ensure amount has mol units
        amount = ensure_units(resource_amount, mol)
        assert amount >= Q_(0, mol), f"Resource amount cannot be negative: {amount}"
        
        self.resources[resource_type] = amount

    def consume_resource(self, resource_type, resource_amount):
        """Consume resource with units validation"""
        if isinstance(resource_type, str):
            resource_type = ResourceType(resource_type)
        
        amount = ensure_units(resource_amount, mol)
        current = self.resources.get(resource_type, Q_(0, mol))
        
        new_amount = current - amount
        if new_amount < Q_(0, mol):
            raise ValueError(f"Cannot consume {amount} of {resource_type.value}, only {current} available")
        
        self.resources[resource_type] = new_amount

    def get_resource(self, resource_type):
        """Get resource amount as pint quantity"""
        if isinstance(resource_type, str):
            resource_type = ResourceType(resource_type)
        return self.resources.get(resource_type, Q_(0, mol))
    
    def set_resource(self, resource_type, resource_amount):
        """Set resource amount with units validation"""
        if isinstance(resource_type, str):
            resource_type = ResourceType(resource_type)
        
        amount = ensure_units(resource_amount, mol)
        assert amount >= Q_(0, mol), f"Resource amount cannot be negative: {amount}"
        
        self.resources[resource_type] = amount
    
    def get_resource_magnitude(self, resource_type):
        """Get resource amount as raw float (for numpy operations)"""
        return self.get_resource(resource_type).magnitude