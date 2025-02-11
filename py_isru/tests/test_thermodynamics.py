"""
Tests for core thermodynamic calculations.
"""
import pytest
import numpy as np
from scipy import constants

from py_isru.lib.thermodynamics import ThermodynamicState, ReactionKinetics, GasProperties

def test_thermodynamic_state_creation():
    """Test basic ThermodynamicState creation and properties"""
    state = ThermodynamicState(
        temperature=298.15,
        pressure=101325.0,
        enthalpy=0.0,
        entropy=0.0,
        gibbs_energy=0.0
    )
    assert state.temperature == 298.15
    assert state.pressure == 101325.0

def test_thermodynamic_state_from_temperature_pressure():
    """Test factory method for ThermodynamicState"""
    state = ThermodynamicState.from_temperature_pressure(298.15, 101325.0)
    assert state.temperature == 298.15
    assert state.pressure == 101325.0
    assert state.gibbs_energy == state.enthalpy - state.temperature * state.entropy

def test_equilibrium_constant_calculation():
    """Test equilibrium constant calculation"""
    state = ThermodynamicState(
        temperature=298.15,
        pressure=101325.0,
        enthalpy=0.0,
        entropy=0.0,
        gibbs_energy=0.0
    )
    
    # Test with known values for CO₂ + 4H₂ → CH₄ + 2H₂O at 298K
    delta_g = -130.8e3  # J/mol
    K = state.calculate_equilibrium_constant(delta_g)
    
    # K should be very large (reaction strongly favors products)
    assert K > 1e20
    
    # Test that K decreases with temperature (endothermic reaction)
    state_hot = ThermodynamicState(
        temperature=598.15,  # 325°C
        pressure=101325.0,
        enthalpy=0.0,
        entropy=0.0,
        gibbs_energy=0.0
    )
    K_hot = state_hot.calculate_equilibrium_constant(delta_g)
    assert K_hot < K

def test_reaction_kinetics():
    """Test reaction rate calculations"""
    kinetics = ReactionKinetics(
        rate_constants={"forward": 1e-3},  # mol/(m³⋅s)
        activation_energy=50e3,  # J/mol
        catalyst_surface_area=100.0,  # m²
        reaction_order={"A": 1, "B": 2}  # First order in A, second order in B
    )
    
    # Test basic rate calculation
    concentrations = {"A": 2.0, "B": 1.5}  # mol/m³
    temperature = 298.15  # K
    
    rate = kinetics.calculate_rate(concentrations, temperature)
    
    # Rate should follow k[A][B]²
    expected_k = 1e-3 * np.exp(-50e3 / (constants.R * temperature))
    expected_rate = expected_k * 2.0 * 1.5**2
    assert np.isclose(rate, expected_rate, rtol=1e-10)
    
    # Test temperature dependence
    rate_hot = kinetics.calculate_rate(concentrations, temperature * 2)
    assert rate_hot > rate  # Rate should increase with temperature
    
    # Test catalyst effects
    rate_with_catalyst = kinetics.calculate_rate(
        concentrations, 
        temperature,
        inhibition_factor=0.5
    )
    assert rate_with_catalyst == rate * 0.5 * kinetics.catalyst_surface_area

def test_gas_properties():
    """Test gas property calculations"""
    # Test ideal gas density calculation
    pressure = 101325.0  # Pa
    temperature = 298.15  # K
    molar_mass = 0.044  # kg/mol (CO₂)
    
    density = GasProperties.calculate_density(pressure, temperature, molar_mass)
    
    # Compare with ideal gas law
    expected_density = pressure * molar_mass / (constants.R * temperature)
    assert np.isclose(density, expected_density, rtol=1e-10)
    
    # Test viscosity calculation using Sutherland's law
    reference_visc = 1.37e-5  # Pa⋅s
    reference_temp = 273.15  # K
    
    viscosity = GasProperties.calculate_viscosity(
        temperature,
        reference_visc,
        reference_temp
    )
    
    # Viscosity should increase with temperature
    viscosity_hot = GasProperties.calculate_viscosity(
        temperature * 1.5,
        reference_visc,
        reference_temp
    )
    assert viscosity_hot > viscosity

def test_edge_cases():
    """Test edge cases and error conditions"""
    # Test zero temperature
    with pytest.raises(ValueError):
        ThermodynamicState.from_temperature_pressure(0.0, 101325.0)
        
    # Test negative pressure
    with pytest.raises(ValueError):
        ThermodynamicState.from_temperature_pressure(298.15, -101325.0)
        
    # Test reaction rate with missing species
    kinetics = ReactionKinetics(
        rate_constants={"forward": 1e-3},
        activation_energy=50e3,
        catalyst_surface_area=100.0,
        reaction_order={"A": 1, "B": 2}
    )
    
    with pytest.raises(KeyError):
        kinetics.calculate_rate({"A": 1.0}, 298.15)  # Missing species B
        
    # Test gas properties with invalid inputs
    with pytest.raises(ValueError):
        GasProperties.calculate_density(101325.0, -273.15, 0.044)  # Negative temperature
        
    with pytest.raises(ValueError):
        GasProperties.calculate_viscosity(298.15, -1e-5, 273.15)  # Negative viscosity 