import math
from typing import Dict, Any, Optional
import logging
import random

from core import BaseModule, PlantState

logger = logging.getLogger(__name__)

class EnvironmentModule(BaseModule):
    """
    Environment module that calculates Mars environmental conditions:
    - Solar irradiance based on location and time
    - Day/night cycles
    - Atmospheric conditions
    - Weather events (dust storms)
    """
    
    def __init__(self, name: str = "Environment"):
        super().__init__(name, priority=1)  # High priority - other modules depend on this
        
        # Mars orbital/rotational parameters
        self.mars_solar_constant = 590.0  # W/m² at mean distance
        self.sol_length_s = 88775.0       # Mars sol ≈ 24.65 Earth hours
        self.axial_tilt_deg = 25.19       # Mars axial tilt
        self.orbit_eccentricity = 0.0934  # Mars orbital eccentricity
        
        # Atmospheric properties
        self.base_pressure_pa = 610.0     # ~0.6% of Earth at datum
        self.base_temperature_k = 210.0   # Cold Mars baseline
        self.temperature_variation_k = 60.0  # Day/night swing
        
        # Dust storm parameters
        self.dust_storm_probability = 0.001  # Per timestep (adjust based on season)
        self.dust_storm_duration_s = 172800.0  # 2 sols average
        self.current_dust_storm_end = 0.0
        
        # Location-specific factors
        self.elevation_factor = 1.0  # Atmospheric pressure scaling
        
        # No power consumption - this is a passive environmental module
        self.min_power_kw = 0.0
        self.max_power_kw = 0.0
    
    def simulate(self, plant_state: PlantState, dt_seconds: float) -> Dict[str, Any]:
        """Calculate current environmental conditions."""
        
        # Update environmental conditions
        self._calculate_solar_conditions(plant_state)
        self._calculate_atmospheric_conditions(plant_state)
        self._update_dust_conditions(plant_state, dt_seconds)
        
        # Store results
        env = plant_state.environment
        
        return {
            "solar_irradiance_w_m2": env.solar_irradiance_w_m2,
            "ambient_temperature_k": env.ambient_temperature_k,
            "atmospheric_pressure_pa": env.atmospheric_pressure_pa,
            "dust_opacity": env.dust_opacity,
            "sol": env.sol,
            "time_of_sol": env.time_of_sol,
            "is_daytime": env.time_of_sol > 0.25 and env.time_of_sol < 0.75,
            "solar_elevation_deg": self._calculate_solar_elevation(plant_state)
        }
    
    def _calculate_solar_conditions(self, plant_state: PlantState):
        """Calculate solar irradiance based on time and location."""
        env = plant_state.environment
        
        # Solar elevation angle calculation
        solar_elevation_deg = self._calculate_solar_elevation(plant_state)
        
        # Solar irradiance (accounting for atmosphere and angle)
        if solar_elevation_deg > 0:
            # Base irradiance adjusted for elevation angle
            cosine_factor = math.cos(math.radians(90 - solar_elevation_deg))
            
            # Atmospheric attenuation (simple model)
            # Higher elevation = less atmosphere = less attenuation
            air_mass = 1.0 / max(0.1, cosine_factor)  # Approximate air mass
            atmospheric_transmission = 0.7 ** air_mass  # Rough atmospheric model
            
            # Dust attenuation
            dust_transmission = 1.0 - (env.dust_opacity * 0.9)  # Dust blocks up to 90%
            
            # Final irradiance
            env.solar_irradiance_w_m2 = (self.mars_solar_constant * 
                                       cosine_factor * 
                                       atmospheric_transmission * 
                                       dust_transmission)
        else:
            # Night time
            env.solar_irradiance_w_m2 = 0.0
    
    def _calculate_solar_elevation(self, plant_state: PlantState) -> float:
        """Calculate solar elevation angle in degrees."""
        env = plant_state.environment
        
        # Convert time of sol to hour angle
        hour_angle_deg = (env.time_of_sol - 0.5) * 360.0  # -180 to +180 degrees
        
        # Convert to radians
        lat_rad = math.radians(env.latitude_deg)
        hour_angle_rad = math.radians(hour_angle_deg)
        
        # Solar declination (simplified - assumes equinox)
        # For more accuracy, would need Mars orbital position
        declination_rad = 0.0  # Simplified to equinox conditions
        
        # Solar elevation using spherical trigonometry
        elevation_rad = math.asin(
            math.sin(lat_rad) * math.sin(declination_rad) +
            math.cos(lat_rad) * math.cos(declination_rad) * math.cos(hour_angle_rad)
        )
        
        return math.degrees(elevation_rad)
    
    def _calculate_atmospheric_conditions(self, plant_state: PlantState):
        """Calculate atmospheric pressure and temperature."""
        env = plant_state.environment
        
        # Pressure varies with elevation (exponential atmosphere)
        # Mars scale height ≈ 11 km
        scale_height_m = 11000.0
        pressure_factor = math.exp(-env.altitude_m / scale_height_m)
        env.atmospheric_pressure_pa = self.base_pressure_pa * pressure_factor
        
        # Temperature calculation
        # Base temperature + diurnal variation + elevation effects
        solar_heating_factor = env.solar_irradiance_w_m2 / self.mars_solar_constant
        
        # Diurnal temperature swing
        diurnal_temp = self.temperature_variation_k * solar_heating_factor
        
        # Elevation effect (lapse rate: ~2°C per km)
        elevation_temp_effect = -0.002 * env.altitude_m  # K per meter
        
        env.ambient_temperature_k = (self.base_temperature_k + 
                                   diurnal_temp + 
                                   elevation_temp_effect)
    
    def _update_dust_conditions(self, plant_state: PlantState, dt_seconds: float):
        """Update dust storm conditions."""
        env = plant_state.environment
        current_time = plant_state.current_time
        
        # Check if current dust storm has ended
        if env.dust_opacity > 0 and current_time > self.current_dust_storm_end:
            env.dust_opacity = 0.0
            logger.info(f"Dust storm ended at sol {env.sol}")
        
        # Check for new dust storm
        if env.dust_opacity == 0:
            # Probability adjusted for timestep
            storm_prob_this_timestep = self.dust_storm_probability * (dt_seconds / 3600.0)
            
            if random.random() < storm_prob_this_timestep:
                # Start new dust storm
                env.dust_opacity = random.uniform(0.3, 0.8)  # 30-80% opacity
                storm_duration = random.uniform(
                    self.dust_storm_duration_s * 0.5,
                    self.dust_storm_duration_s * 2.0
                )
                self.current_dust_storm_end = current_time + storm_duration
                logger.warning(f"Dust storm started at sol {env.sol}, "
                             f"opacity: {env.dust_opacity:.1%}, "
                             f"duration: {storm_duration/88775:.1f} sols")
    
    def set_location_parameters(self, latitude_deg: float, longitude_deg: float, 
                              altitude_m: float = 0.0):
        """Set location-specific parameters."""
        # Could adjust dust storm probability based on location
        # (e.g., more storms near polar regions during certain seasons)
        
        if abs(latitude_deg) > 60:
            # Polar regions have different weather patterns
            self.dust_storm_probability *= 0.5  # Less frequent storms
            self.temperature_variation_k *= 0.7  # Less diurnal variation
        
        if altitude_m > 10000:  # High elevation (e.g., Olympus Mons)
            self.temperature_variation_k *= 1.2  # More extreme temperatures
    
    def inject_dust_storm(self, opacity: float = 0.6, duration_sols: float = 2.0, current_time: float = 0.0):
        """Manually inject a dust storm for testing/scenarios."""
        if not 0.0 <= opacity <= 1.0:
            raise ValueError("Dust opacity must be between 0 and 1")
        
        self.current_dust_storm_end = (
            current_time + 
            duration_sols * self.sol_length_s
        )
        
        logger.info(f"Injected dust storm: {opacity:.1%} opacity for {duration_sols:.1f} sols")
    
    def set_season(self, mars_year_fraction: float):
        """Adjust conditions based on Mars season (0-1 = full Mars year)."""
        # Mars year ≈ 687 Earth days
        # Could adjust:
        # - Solar constant (Mars orbital distance varies ±20%)
        # - Dust storm probability (higher during southern summer)
        # - Base temperatures
        
        # Orbital distance effect on solar irradiance
        orbit_angle = mars_year_fraction * 2 * math.pi
        distance_factor = 1.0 + self.orbit_eccentricity * math.cos(orbit_angle)
        self.mars_solar_constant = 590.0 * (distance_factor ** -2)
        
        # Dust storm seasonality (peak during southern summer)
        seasonal_dust_factor = 1.0 + 2.0 * math.sin(orbit_angle + math.pi)
        self.dust_storm_probability = 0.001 * seasonal_dust_factor
    
    def get_environmental_summary(self, plant_state: PlantState) -> Dict[str, Any]:
        """Get comprehensive environmental status."""
        env = plant_state.environment
        
        return {
            "location": {
                "latitude_deg": env.latitude_deg,
                "longitude_deg": env.longitude_deg,
                "altitude_m": env.altitude_m
            },
            "time": {
                "sol": env.sol,
                "time_of_sol": env.time_of_sol,
                "local_time_hr": env.time_of_sol * 24.65,
                "is_daytime": env.time_of_sol > 0.25 and env.time_of_sol < 0.75
            },
            "solar": {
                "irradiance_w_m2": env.solar_irradiance_w_m2,
                "elevation_deg": self._calculate_solar_elevation(plant_state),
                "peak_irradiance_w_m2": self.mars_solar_constant
            },
            "atmosphere": {
                "temperature_k": env.ambient_temperature_k,
                "temperature_c": env.ambient_temperature_k - 273.15,
                "pressure_pa": env.atmospheric_pressure_pa,
                "pressure_mbar": env.atmospheric_pressure_pa / 100.0
            },
            "weather": {
                "dust_opacity": env.dust_opacity,
                "dust_storm_active": env.dust_opacity > 0,
                "dust_storm_ends_sol": (self.current_dust_storm_end / self.sol_length_s) if env.dust_opacity > 0 else None
            }
        } 