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
    """Mars environment specifications (fixed)"""
    latitude_rad: float  # rad
    longitude_rad: float  # rad
    altitude_m: float  # m
    start_time_of_day_s: float = 0.0  # s
    start_sols_since_perihelion: float = 0.0  # Mars sols since perihelion
    start_dust_opacity_tau: float = 0.5  # typical background tau
    temperature_range_K: Tuple[float, float] = (150.0, 300.0)  # K
    pressure_Pa: float = 600.0  # Pa
    day_length_s: float = 88775.244  # s, length of Mars sol
    year_length_sols: float = 668.6  # sols
    eccentricity: float = 0.0934  # Mars orbital eccentricity
    obliquity_rad: float = np.radians(25.19)  # Mars axial tilt
    perihelion_Ls_rad: float = np.radians(251.0)  # solar longitude at perihelion
    
@dataclass
class MarsEnvironmentState:
    """Mars environment state"""
    dust_storm: DustStormSeverity
    dust_opacity_tau: float
    temperature_K: float
    wind_speed_m_per_s: float
    time_of_day_s: float
    sols_since_perihelion: float
    solar_intensity_W_per_m2: float
    sun_azimuth: float
    sun_elevation: float
    dust_density_kg_per_m3: float

class MarsEnvironment:
    """Mars environment model for solar calculations"""
    
    def __init__(self, environment_specification: MarsEnvironmentSpecification):
        self.environment_specification = environment_specification
        # Create initial state with basic values
        self.state = MarsEnvironmentState(
            dust_storm=DustStormSeverity.NONE,
            dust_opacity_tau=environment_specification.start_dust_opacity_tau,
            temperature_K=np.mean(environment_specification.temperature_range_K),
            wind_speed_m_per_s=0.0,
            time_of_day_s=environment_specification.start_time_of_day_s,
            sols_since_perihelion=environment_specification.start_sols_since_perihelion,
            solar_intensity_W_per_m2=0.0,  # Will be updated
            sun_azimuth=0.0,  # Will be updated
            sun_elevation=0.0,  # Will be updated
            dust_density_kg_per_m3=0.0  # Will be updated
        )
        self.history = [self.state]
        
        # Now update the calculated values
        azimuth, elevation = self.calculate_solar_position()
        self.state.sun_azimuth = azimuth
        self.state.sun_elevation = elevation
        self.state.solar_intensity_W_per_m2 = self.calculate_solar_intensity()
        self.state.dust_density_kg_per_m3 = self.calculate_dust_rate()
        
    @property
    def solar_intensity_W_per_m2(self) -> float:
        """Solar intensity at surface in W/m^2"""
        return self.calculate_solar_intensity()
    
    @property
    def sun_azimuth(self) -> float:
        """Sun azimuth in radians"""
        return self.calculate_solar_position()[0]
    
    @property
    def sun_elevation(self) -> float:
        """Sun elevation in radians"""
        return self.calculate_solar_position()[1]
    
    @property
    def dust_density_kg_per_m3(self) -> float:
        """Dust density in kg/m^3"""
        return self.calculate_dust_rate()
    
    def calculate_solar_position(self) -> Tuple[float, float]:
        """Calculate sun position (azimuth, elevation) in radians"""
        # Solar time angle
        hour_angle = 2 * np.pi * (self.get_state().time_of_day_s / self.environment_specification.day_length_s - 0.5)
        
        # Solar declination
        Ls = 2 * np.pi * (self.get_state().sols_since_perihelion / self.environment_specification.year_length_sols)
        declination = np.arcsin(
            np.sin(self.environment_specification.obliquity_rad) * 
            np.sin(Ls - self.environment_specification.perihelion_Ls_rad)
        )
        
        # Calculate elevation
        sin_elevation = (
            np.sin(self.environment_specification.latitude_rad) * np.sin(declination) +
            np.cos(self.environment_specification.latitude_rad) * np.cos(declination) * np.cos(hour_angle)
        )
        elevation = np.arcsin(np.clip(sin_elevation, -1.0, 1.0))
        
        # Calculate azimuth
        sin_azimuth = (
            np.cos(declination) * 
            np.sin(hour_angle) / 
            np.cos(elevation)
        )
        cos_azimuth = (
            (np.sin(declination) * np.cos(self.environment_specification.latitude_rad) -
             np.cos(declination) * np.sin(self.environment_specification.latitude_rad) * 
             np.cos(hour_angle)) /
            np.cos(elevation)
        )
        azimuth = np.arctan2(sin_azimuth, cos_azimuth)
        
        return azimuth, elevation
        
    def calculate_solar_intensity(self) -> float:
        """Calculate solar intensity at surface in W/m^2"""
        state = self.get_state()
        # Base intensity at Mars' mean distance
        base_intensity = 590.0  # W/m^2
        
        # Orbital distance variation
        Ls = 2 * np.pi * (state.sols_since_perihelion / self.environment_specification.year_length_sols)
        r = (1 - self.environment_specification.eccentricity**2) / (
            1 + self.environment_specification.eccentricity * np.cos(Ls - self.environment_specification.perihelion_Ls_rad)
        )
        intensity = base_intensity / (r * r)
        
        # Atmospheric transmission
        _, elevation = self.calculate_solar_position()
        if elevation <= 0:
            return 0.0
            
        # Air mass calculation (simplified for Mars)
        air_mass = 1.0 / np.sin(elevation)
        
        # Beer-Lambert law for atmospheric extinction
        transmission = np.exp(-state.dust_opacity_tau * air_mass)
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
        
        base_rate = base_rates[self.get_state().dust_storm]
        wind_factor = 1.0 + (self.get_state().wind_speed_m_per_s / 10.0)**2
        
        return base_rate * wind_factor
        
    def update_temperature(self, dt: float, step_state: MarsEnvironmentState) -> MarsEnvironmentState:
        """Update ambient temperature based on time of day"""
        min_temp_K, max_temp_K = self.environment_specification.temperature_range_K
        
        # Diurnal temperature variation (simplified sinusoidal)
        _, elevation = self.calculate_solar_position()
        temp_range_K = max_temp_K - min_temp_K
        
        # Temperature lags solar elevation by ~2 hours
        phase_lag = 2 * np.pi * (2.0 / 24.0)
        temp_factor = np.sin(elevation + phase_lag)
        
        step_state.temperature_K = min_temp_K + (0.5 + 0.5 * temp_factor) * temp_range_K
        return step_state
        
    def update_dust_storm(self, dt: float, step_state: MarsEnvironmentState) -> MarsEnvironmentState:
        """Update dust storm conditions"""
        # Simple random dust storm evolution
        if np.random.random() < 0.001 * dt:  # Small chance of storm starting/changing
            current_level = list(DustStormSeverity).index(step_state.dust_storm)
            
            # Can go up or down one level
            new_level = current_level + np.random.choice([-1, 0, 1])
            new_level = np.clip(new_level, 0, len(DustStormSeverity) - 1)
            
            step_state.dust_storm = list(DustStormSeverity)[new_level]
            
            # Update opacity based on storm severity
            base_opacity = self.environment_specification.start_dust_opacity_tau
            opacity_factors = {
                DustStormSeverity.NONE: 1.0,
                DustStormSeverity.LIGHT: 2.0,
                DustStormSeverity.MODERATE: 5.0,
                DustStormSeverity.SEVERE: 10.0,
                DustStormSeverity.GLOBAL: 20.0
            }
            step_state.dust_opacity_tau = base_opacity * opacity_factors[step_state.dust_storm]
            
        return step_state
    
    def update_wind(self, dt: float, step_state: MarsEnvironmentState) -> MarsEnvironmentState:
        """Update wind conditions"""
        # Simple random walk wind speed
        target_speed_m_per_s = np.random.exponential(5.0)  # Mean wind speed 5 m/s
        delta_speed_m_per_s = (target_speed_m_per_s - step_state.wind_speed_m_per_s) * dt
        step_state.wind_speed_m_per_s = max(0.0, step_state.wind_speed_m_per_s + delta_speed_m_per_s)
        return step_state
        
    def step(self, dt: float) -> None:
        """Advance environment state by one time step"""
        step_state = MarsEnvironmentState(
            dust_storm=self.get_state().dust_storm,
            dust_opacity_tau=self.get_state().dust_opacity_tau,
            temperature_K=self.get_state().temperature_K,
            wind_speed_m_per_s=self.get_state().wind_speed_m_per_s,
            time_of_day_s=self.get_state().time_of_day_s,
            sols_since_perihelion=self.get_state().sols_since_perihelion,
            solar_intensity_W_per_m2=self.get_state().solar_intensity_W_per_m2,
            sun_azimuth=self.get_state().sun_azimuth,
            sun_elevation=self.get_state().sun_elevation,
            dust_density_kg_per_m3=self.get_state().dust_density_kg_per_m3
        )
        # Update time
        step_state.time_of_day_s += dt
        if step_state.time_of_day_s >= self.environment_specification.day_length_s:
            step_state.time_of_day_s -= self.environment_specification.day_length_s
            step_state.sols_since_perihelion += 1
            
        if step_state.sols_since_perihelion >= self.environment_specification.year_length_sols:
            step_state.sols_since_perihelion = 0
            
        # Update environmental conditions
        step_state = self.update_temperature(dt, step_state)
        step_state = self.update_dust_storm(dt, step_state)
        step_state = self.update_wind(dt, step_state) 
        
        self.history.append(step_state)
        
    def get_state(self) -> MarsEnvironmentState:
        """Get current environment state"""
        return self.history[-1]

    # @property
    # def day_length_s(self) -> float:
    #     return self.environment_specification.day_length_s

    # @property
    # def year_length_sols(self) -> float:
    #     return self.environment_specification.year_length_sols

    # @property
    # def obliquity_rad(self) -> float:
    #     return self.environment_specification.obliquity_rad

    # @property
    # def perihelion_Ls_rad(self) -> float:
    #     return self.environment_specification.perihelion_Ls_rad

    # @property
    # def spec(self):
    #     return self.environment_specification

    # @property
    # def day_of_year_sols(self) -> float:
    #     return self.get_state().sols_since_perihelion