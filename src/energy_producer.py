from .units import Q_, watt, ensure_units

class EnergyProducer:
    def __init__(self, resource_bus):
        self.resource_bus = resource_bus

    def output_power(self):
        return Q_(0.0, watt)
    
class EnergyStorage:
    def __init__(self, resource_bus):
        self.resource_bus = resource_bus

    def charge(self, power):
        power = ensure_units(power, watt)
        # TODO: Implement charging logic
        pass

    def discharge(self, power):
        power = ensure_units(power, watt)
        # TODO: Implement discharge logic
        pass
    
    def get_state_of_charge_percent(self):
        return 0.0  # Dimensionless percentage
    
class SolarPanel(EnergyProducer):
    def __init__(self, resource_bus):
        super().__init__(resource_bus)

class Battery(EnergyStorage):
    def __init__(self, resource_bus):
        super().__init__(resource_bus)