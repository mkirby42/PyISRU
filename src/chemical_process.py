class ChemicalProcess:
    def __init__(self, resource_bus):
        self.resource_bus = resource_bus

    def tick(self, time_seconds):
        pass
    
    def inputs(self):
        return []
    
    def outputs(self):
        return []
    
    def status(self):
        return {}
    
class Electrolysis(ChemicalProcess):
    def __init__(self, resource_bus):
        super().__init__(resource_bus)

    def inputs(self):
        return ["H2O"]
    
    def outputs(self):
        return ["H2", "O2"]