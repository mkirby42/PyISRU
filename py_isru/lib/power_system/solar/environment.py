"""
Mars environment model for solar power calculations.
"""
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional, Tuple

import numpy as np

class DustStormSeverity(Enum):
    """Mars dust storm severity levels"""
    NONE = auto()
    LIGHT = auto()
    MODERATE = auto()
    SEVERE = auto()
    GLOBAL = auto()

@dataclass
class MarsEnvironmentSpecification:
    """Mars environment specifications"""
    latitude: float  # rad
    longitude: float  # rad
    altitude: float  # m
    dust_opacity: float = 0.5  # typical background tau
    temperature_range: Tuple[float, float] = (150.0, 300.0)  # K
    pressure: float = 600.0  # Pa
    
class MarsEnvironment:
    """Mars environment model for solar calculations"""
    
    def __init__(self, spec: MarsEnvironmentSpecification):
        self.spec = spec
        
        # Time tracking
        self.time_of_day = 0.0  # s
        self.day_of_year = 0  # Mars sols since perihelion
        self.day_length = 88775.244  # s, length of Mars sol
        self.year_length = 668.6  # sols
        
        # Environmental state
        self.dust_storm = DustStormSeverity.NONE
        self.dust_opacity = spec.dust_opacity
        self.temperature = np.mean(spec.temperature_range)  # K
        self.wind_speed = 0.0  # m/s
        
        # Orbital parameters
        self.eccentricity = 0.0934  # Mars orbital eccentricity
        self.obliquity = np.radians(25.19)  # Mars axial tilt
        self.perihelion_Ls = np.radians(251.0)  # solar longitude at perihelion
        
    def calculate_solar_position(self) -> Tuple[float, float]:
        """Calculate sun position (azimuth, elevation) in radians"""
        # Solar time angle
        hour_angle = 2 * np.pi * (self.time_of_day / self.day_length - 0.5)
        
        # Solar declination
        Ls = 2 * np.pi * (self.day_of_year / self.year_length)
        declination = np.arcsin(
            np.sin(self.obliquity) * 
            np.sin(Ls - self.perihelion_Ls)
        )
        
        # Calculate elevation
        sin_elevation = (
            np.sin(self.spec.latitude) * np.sin(declination) +
            np.cos(self.spec.latitude) * np.cos(declination) * np.cos(hour_angle)
        )
        elevation = np.arcsin(np.clip(sin_elevation, -1.0, 1.0))
        
        # Calculate azimuth
        sin_azimuth = (
            np.cos(declination) * 
            np.sin(hour_angle) / 
            np.cos(elevation)
        )
        cos_azimuth = (
            (np.sin(declination) * np.cos(self.spec.latitude) -
             np.cos(declination) * np.sin(self.spec.latitude) * 
             np.cos(hour_angle)) /
            np.cos(elevation)
        )
        azimuth = np.arctan2(sin_azimuth, cos_azimuth)
        
        return azimuth, elevation
        
    def calculate_solar_intensity(self) -> float:
        """Calculate solar intensity at surface in W/m^2"""
        # Base intensity at Mars' mean distance
        base_intensity = 590.0  # W/m^2
        
        # Orbital distance variation
        Ls = 2 * np.pi * (self.day_of_year / self.year_length)
        r = (1 - self.eccentricity**2) / (
            1 + self.eccentricity * np.cos(Ls - self.perihelion_Ls)
        )
        intensity = base_intensity / (r * r)
        
        # Atmospheric transmission
        _, elevation = self.calculate_solar_position()
        if elevation <= 0:
            return 0.0
            
        # Air mass calculation (simplified for Mars)
        air_mass = 1.0 / np.sin(elevation)
        
        # Beer-Lambert law for atmospheric extinction
        transmission = np.exp(-self.dust_opacity * air_mass)
        
        return intensity * transmission
        
    def calculate_dust_rate(self) -> float:
        """Calculate dust accumulation rate in coverage/second"""
        base_rates = {
            DustStormSeverity.NONE: 1e-8,
            DustStormSeverity.LIGHT: 1e-7,
            DustStormSeverity.MODERATE: 1e-6,
            DustStormSeverity.SEVERE: 1e-5,
            DustStormSeverity.GLOBAL: 1e-4
        }
        
        base_rate = base_rates[self.dust_storm]
        wind_factor = 1.0 + (self.wind_speed / 10.0)**2
        
        return base_rate * wind_factor
        
    def update_temperature(self, dt: float) -> None:
        """Update ambient temperature based on time of day"""
        min_temp, max_temp = self.spec.temperature_range
        
        # Diurnal temperature variation (simplified sinusoidal)
        _, elevation = self.calculate_solar_position()
        temp_range = max_temp - min_temp
        
        # Temperature lags solar elevation by ~2 hours
        phase_lag = 2 * np.pi * (2.0 / 24.0)
        temp_factor = np.sin(elevation + phase_lag)
        
        self.temperature = min_temp + (0.5 + 0.5 * temp_factor) * temp_range
        
    def update_dust_storm(self, dt: float) -> None:
        """Update dust storm conditions"""
        # Simple random dust storm evolution
        if np.random.random() < 0.001 * dt:  # Small chance of storm starting/changing
            current_level = list(DustStormSeverity).index(self.dust_storm)
            
            # Can go up or down one level
            new_level = current_level + np.random.choice([-1, 0, 1])
            new_level = np.clip(new_level, 0, len(DustStormSeverity) - 1)
            
            self.dust_storm = list(DustStormSeverity)[new_level]
            
            # Update opacity based on storm severity
            base_opacity = self.spec.dust_opacity
            opacity_factors = {
                DustStormSeverity.NONE: 1.0,
                DustStormSeverity.LIGHT: 2.0,
                DustStormSeverity.MODERATE: 5.0,
                DustStormSeverity.SEVERE: 10.0,
                DustStormSeverity.GLOBAL: 20.0
            }
            self.dust_opacity = base_opacity * opacity_factors[self.dust_storm]
            
    def update_wind(self, dt: float) -> None:
        """Update wind conditions"""
        # Simple random walk wind speed
        target_speed = np.random.exponential(5.0)  # Mean wind speed 5 m/s
        delta_speed = (target_speed - self.wind_speed) * dt
        self.wind_speed = max(0.0, self.wind_speed + delta_speed)
        
    def step(self, dt: float) -> None:
        """Advance environment state by one time step"""
        # Update time
        self.time_of_day += dt
        if self.time_of_day >= self.day_length:
            self.time_of_day -= self.day_length
            self.day_of_year += 1
            
        if self.day_of_year >= self.year_length:
            self.day_of_year = 0
            
        # Update environmental conditions
        self.update_temperature(dt)
        self.update_dust_storm(dt)
        self.update_wind(dt) 