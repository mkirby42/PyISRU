"""
Tests for Sabatier reactor implementation.
"""
import pytest
import numpy as np
from scipy import constants

from py_isru.lib.reactor import ResourceType, OperationalStatus
from py_isru.lib.sabatier_reactor import SabatierReactor, SabatierSpecification
from py_isru.lib.thermodynamics import ThermodynamicState, ReactionKinetics

@pytest.fixture
def basic_sabatier_reactor():
    """Create a basic Sabatier reactor for testing"""
    spec = SabatierSpecification(
        # Basic reactor parameters
        volume=0.1,  # m³
        max_temperature=900.0,  # K
        max_pressure=2e6,  # Pa
        thermal_mass=500.0,  # J/K
        heat_loss_coefficient=10.0,  # W/(m²⋅K)
        surface_area=1.0,  # m²
        
        # Sabatier-specific parameters
        catalyst_type="Ru/Al₂O₃",
        catalyst_loading=100.0,  # kg/m³
        catalyst_surface_area=200.0,  # m²/g
        catalyst_porosity=0.4  # dimensionless
    )
    
    initial_state = ThermodynamicState.from_temperature_pressure(600.0, 1e6)
    
    kinetics = ReactionKinetics(
        rate_constants={"forward": 1e-3},
        activation_energy=75e3,  # J/mol
        catalyst_surface_area=spec.catalyst_loading * 1000 * spec.catalyst_surface_area,  # m²
        reaction_order={"CO2": 1, "H2": 1}  # Simplified for testing
    )
    
    return SabatierReactor(spec, initial_state, kinetics)

def test_reactor_initialization(basic_sabatier_reactor):
    """Test reactor initialization"""
    reactor = basic_sabatier_reactor
    assert reactor.operational_status == OperationalStatus.STANDBY
    assert reactor.catalyst_degradation == 1.0
    assert reactor.state.temperature == 600.0
    assert reactor.state.pressure == 1e6

def test_startup_shutdown(basic_sabatier_reactor):
    """Test reactor startup and shutdown sequences"""
    reactor = basic_sabatier_reactor
    
    # Test startup
    assert reactor.operational_status == OperationalStatus.STANDBY
    reactor.start()
    assert reactor.operational_status == OperationalStatus.RUNNING
    
    # Test shutdown
    reactor.shutdown()
    assert reactor.operational_status == OperationalStatus.STANDBY

def test_reaction_stoichiometry(basic_sabatier_reactor):
    """Test reaction stoichiometry and mass balance"""
    reactor = basic_sabatier_reactor
    reactor.start()
    
    # Input 1 mol CO₂ and 4 mol H₂
    inputs = {
        ResourceType.CO2: 1.0,
        ResourceType.H2: 4.0
    }
    
    outputs = reactor.step(1.0, inputs)
    
    # Check stoichiometry (not all reactants will be consumed)
    co2_consumed = inputs[ResourceType.CO2] - outputs[ResourceType.CO2]
    h2_consumed = inputs[ResourceType.H2] - outputs[ResourceType.H2]
    ch4_produced = outputs[ResourceType.CH4]
    h2o_produced = outputs[ResourceType.H2O]
    
    # Check stoichiometric ratios
    assert np.isclose(h2_consumed / co2_consumed, 4.0, rtol=1e-10)
    assert np.isclose(ch4_produced / co2_consumed, 1.0, rtol=1e-10)
    assert np.isclose(h2o_produced / co2_consumed, 2.0, rtol=1e-10)

def test_temperature_effects(basic_sabatier_reactor):
    """Test temperature effects on reaction rate and equilibrium"""
    reactor = basic_sabatier_reactor
    reactor.start()
    
    # Test at different temperatures
    temperatures = [400.0, 600.0, 800.0]
    rates = []
    
    inputs = {
        ResourceType.CO2: 1.0,
        ResourceType.H2: 4.0
    }
    
    for T in temperatures:
        reactor.state.temperature = T
        outputs = reactor.step(1.0, inputs)
        rates.append(inputs[ResourceType.CO2] - outputs[ResourceType.CO2])
    
    # Reaction rate should increase with temperature
    assert rates[1] > rates[0]
    
    # But very high temperatures should shift equilibrium back to reactants
    assert rates[1] > rates[2]

def test_catalyst_degradation(basic_sabatier_reactor):
    """Test catalyst degradation over time"""
    reactor = basic_sabatier_reactor
    reactor.start()
    
    initial_degradation = reactor.catalyst_degradation
    
    # Run for a long time at high temperature
    reactor.state.temperature = 800.0  # K
    inputs = {
        ResourceType.CO2: 1.0,
        ResourceType.H2: 4.0
    }
    
    # Simulate for 24 hours
    for _ in range(24):
        reactor.step(3600.0, inputs)
    
    # Catalyst should show degradation
    assert reactor.catalyst_degradation < initial_degradation

def test_safety_limits(basic_sabatier_reactor):
    """Test safety limit handling"""
    reactor = basic_sabatier_reactor
    reactor.start()
    
    # Test temperature limit
    reactor.state.temperature = reactor.spec.max_temperature + 10.0
    assert not reactor.check_safety_limits()
    assert reactor.operational_status == OperationalStatus.FAULT
    
    # Reset and test pressure limit
    reactor = basic_sabatier_reactor
    reactor.start()
    reactor.state.pressure = reactor.spec.max_pressure + 1e5
    assert not reactor.check_safety_limits()
    assert reactor.operational_status == OperationalStatus.FAULT

def test_heat_generation(basic_sabatier_reactor):
    """Test heat generation and thermal balance"""
    reactor = basic_sabatier_reactor
    reactor.start()
    
    initial_temp = reactor.state.temperature
    
    inputs = {
        ResourceType.CO2: 1.0,
        ResourceType.H2: 4.0
    }
    
    # Step the reactor
    reactor.step(1.0, inputs)
    
    # Temperature should increase (exothermic reaction)
    assert reactor.state.temperature > initial_temp
    
    # Run until steady state
    for _ in range(100):
        reactor.step(1.0, inputs)
        if abs(reactor.state.temperature - initial_temp) < 0.1:
            break
    
    # Should reach a steady state where heat generation equals heat loss
    heat_generated = abs(reactor.calculate_heat_loss())
    assert 1e3 < heat_generated < 1e6  # Reasonable range for this reaction

def test_power_consumption(basic_sabatier_reactor):
    """Test power consumption calculations"""
    reactor = basic_sabatier_reactor
    
    # When standby, only minimal power for monitoring
    assert reactor.calculate_power_consumption() == 0.0
    
    # When running, should include heating and pumping power
    reactor.start()
    power = reactor.calculate_power_consumption()
    assert power > 0.0
    
    # Power should increase with temperature difference
    reactor.state.temperature += 100.0
    assert reactor.calculate_power_consumption() > power 