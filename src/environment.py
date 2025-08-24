from .resource_bus import ResourceBus, ResourceType
from .units import Q_, watts_per_square_meter, celsius, pascal, meter, second, kilogram

class Environment:
    def __init__(self, latitude_deg, longitude_deg, altitude_m):
        self.latitude_deg = latitude_deg  # degrees
        self.longitude_deg = longitude_deg  # degrees
        self.altitude_m = Q_(altitude_m, meter)
        self.resource_bus = ResourceBus()

    def get_solar_irradiance(self):
        return Q_(1000.0, watts_per_square_meter)
    
    def get_temperature(self):
        return Q_(20.0, celsius)
    
    def get_pressure(self):
        return Q_(101325.0, pascal)

    def get_wind_speed(self):
        return Q_(0.0, meter / second)
    
    def get_wind_direction_degrees(self):   
        return 0.0  # degrees (dimensionless)
    
    def get_wind_gust(self):
        return Q_(0.0, meter / second)
    
    def get_dust_flux(self):
        return Q_(0.0, kilogram / (meter**2 * second))
        
class EnvironmentWithRealisticSolarIrradiance(Environment):
    def __init__(self, latitude_deg, longitude_deg, altitude_m):
        super().__init__(latitude_deg, longitude_deg, altitude_m)

    def get_solar_irradiance(self):
        # TODO: Implement this. Solar irradiance is a function of latitude, altitude, time of year, and time of day.
        return Q_(1000.0, watts_per_square_meter)