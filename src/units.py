"""
Unit definitions for PyISRU simulation using pint
"""
import os
# Disable pint numpy integration before importing
os.environ['PINT_ARRAY_PROTOCOL'] = 'builtin'

import pint
import numpy as np

# Create unit registry
ureg = pint.UnitRegistry()
Q_ = ureg.Quantity

# Base units
mol = ureg.mol
second = ureg.second
kelvin = ureg.kelvin
joule = ureg.joule
meter = ureg.meter
pascal = ureg.pascal
watt = ureg.watt
gram = ureg.gram
kilogram = ureg.kilogram

# Derived units commonly used in chemical processes
mol_per_second = mol / second
joule_per_mol = joule / mol
joule_per_mol_kelvin = joule / (mol * kelvin)
cubic_meter = meter**3
cubic_meter_per_second = cubic_meter / second
watts_per_square_meter = watt / (meter**2)
celsius = ureg.celsius

# Additional units for advanced reactor modeling
pascal_second = pascal * second  # Dynamic viscosity
kilogram_per_cubic_meter = kilogram / cubic_meter  # Density
meter_per_second = meter / second  # Velocity

# Gas constant with units
R_GAS_CONSTANT = Q_(8.314, joule_per_mol_kelvin)

# Pre-exponential factor units for 5th order reaction (CO2 + 4H2)
# Units: m^12/(mol^4 * s) 
pre_exponential_units = meter**12 / (mol**4 * second)
reaction_rate_unit = mol / cubic_meter / second

def ensure_units(value, expected_unit):
    """Ensure a value has the expected units, converting if necessary"""
    if isinstance(value, Q_):
        return value.to(expected_unit)
    else:
        # Assume dimensionless value in expected units
        return Q_(value, expected_unit)

def magnitude(quantity):
    """Extract magnitude from pint quantity, handling both quantities and plain numbers"""
    if isinstance(quantity, Q_):
        return quantity.magnitude
    return quantity

def strip_units(quantity):
    """Strip units and return magnitude - use sparingly for numpy operations"""
    if isinstance(quantity, Q_):
        return quantity.magnitude
    return quantity

def to_json_serializable(obj):
    """Convert pint quantities to JSON-serializable format with units as strings"""
    if isinstance(obj, Q_):
        return {"value": obj.magnitude, "units": str(obj.units)}
    elif isinstance(obj, dict):
        return {k: to_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [to_json_serializable(item) for item in obj]
    else:
        return obj