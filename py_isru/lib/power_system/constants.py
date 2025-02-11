"""
Constants for power system components.
"""

# Time constants
SECONDS_PER_SOL = 88775.0  # Mars day in seconds
SECONDS_PER_YEAR = 365.25 * 24 * 3600  # Earth year in seconds
SECONDS_PER_MONTH = 30 * 24 * 3600  # Approximate month in seconds

# Solar constants
MARS_SOLAR_CONSTANT = 590.0  # W/m² at Mars' mean distance from Sun
MARS_ORBITAL_ECCENTRICITY = 0.0934
MARS_AXIAL_TILT = 25.19  # degrees
MARS_ORBITAL_PERIOD = 687 * 24 * 3600  # seconds

# Thermal constants
STEFAN_BOLTZMANN = 5.67e-8  # W/m²K⁴
ROOM_TEMP_K = 298.15  # K (25°C)
FREEZING_POINT_K = 273.15  # K (0°C)

# Battery constants
BATTERY_DEGRADATION_PER_10K = 0.02  # 2% capacity loss per 10K from optimal
BATTERY_SELF_DISCHARGE_PER_MONTH = 0.03  # 3% per month at 20°C
BATTERY_SELF_DISCHARGE_TEMP_FACTOR = 2.0  # Doubles every 10K above 20°C

# Nuclear constants
KRUSTY_BURNUP_PER_YEAR = 0.005  # 0.5% per year at full power
KRUSTY_TE_DEG_PER_YEAR = 0.01  # 1% per year at nominal temp
KRUSTY_CREEP_PER_YEAR = 0.001  # 0.1% per year at nominal temp 