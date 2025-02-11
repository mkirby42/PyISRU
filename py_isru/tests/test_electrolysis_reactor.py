"""
Tests for electrolysis reactor implementation.
"""
import pytest
import numpy as np
from scipy import constants
import logging

from py_isru.lib.reactor import ResourceType, OperationalStatus
from py_isru.lib.electrolysis_reactor import ElectrolysisReactor, ElectrolysisSpecification
from py_isru.lib.thermodynamics import ThermodynamicState, ReactionKinetics

# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@pytest.fixture
def basic_electrolysis_reactor():
    """Create a basic electrolysis reactor for testing"""
    spec = ElectrolysisSpecification(
        # Basic reactor parameters
        volume=0.05,  # m³
        max_temperature=400.0,  # K
        max_pressure=3e6,  # Pa
        thermal_mass=200.0,  # J/K
        heat_loss_coefficient=5.0,  # W/(m²⋅K)
        surface_area=0.5,  # m²
        
        # Electrolysis-specific parameters
        membrane_type="Nafion",
        membrane_thickness=1.27e-4,  # m (127 microns)
        membrane_conductivity=10.0,  # S/m
        electrode_area=0.1,  # m²
        max_current_density=2000.0,  # A/m²
        max_power=5000.0  # 5 kW
    )
    
    initial_state = ThermodynamicState.from_temperature_pressure(353.15, 2e6)  # 80°C
    
    kinetics = ReactionKinetics(
        rate_constants={"forward": 1.0},  # Not used in electrolysis
        activation_energy=0.0,  # Not used in electrolysis
        catalyst_surface_area=spec.electrode_area,
        reaction_order={"H2O": 1}
    )
    
    return ElectrolysisReactor(spec, initial_state, kinetics)

def test_reactor_initialization(basic_electrolysis_reactor):
    """Test reactor initialization"""
    reactor = basic_electrolysis_reactor
    assert reactor.operational_status == OperationalStatus.STANDBY
    assert reactor.membrane_degradation == 1.0
    assert reactor.current_density == 0.0
    assert reactor.state.temperature == 353.15
    assert reactor.state.pressure == 2e6

def test_startup_shutdown(basic_electrolysis_reactor):
    """Test reactor startup and shutdown sequences"""
    reactor = basic_electrolysis_reactor
    
    # Test startup
    assert reactor.operational_status == OperationalStatus.STANDBY
    reactor.start()
    assert reactor.operational_status == OperationalStatus.RUNNING
    
    # Test shutdown
    reactor.shutdown()
    assert reactor.operational_status == OperationalStatus.STANDBY

def test_nernst_voltage(basic_electrolysis_reactor):
    """Test Nernst voltage calculations"""
    reactor = basic_electrolysis_reactor
    
    # Set standard temperature first
    reactor.state.temperature = 298.15  # K
    
    # Calculate at standard conditions
    logger.debug("Testing Nernst voltage at standard conditions:")
    logger.debug(f"Temperature: {reactor.state.temperature}K")
    logger.debug(f"pH2: {1e5} Pa")
    logger.debug(f"pO2: {1e5} Pa")
    V = reactor.calculate_nernst_voltage(1e5, 1e5)  # 1 bar H₂ and O₂
    logger.debug(f"Calculated Nernst voltage: {V}V")
    logger.debug(f"Expected voltage: 1.23V")
    logger.debug(f"Difference: {abs(V - 1.23)}V")
    assert np.isclose(V, 1.23, rtol=1e-2)  # Should be close to standard potential
    
    # Test pressure dependence
    V_high_p = reactor.calculate_nernst_voltage(2e5, 2e5)
    logger.debug("Pressure dependence:")
    logger.debug(f"V at 2 bar: {V_high_p}V")
    logger.debug(f"V at 1 bar: {V}V")
    assert V_high_p > V  # Higher pressure increases voltage
    
    # Test temperature dependence
    reactor.state.temperature += 50
    V_high_T = reactor.calculate_nernst_voltage(1e5, 1e5)
    logger.debug("Temperature dependence:")
    logger.debug(f"V at {reactor.state.temperature}K: {V_high_T}V")
    logger.debug(f"V at 298.15K: {V}V")
    assert V_high_T < V  # Higher temperature decreases voltage

def test_overpotential(basic_electrolysis_reactor):
    """Test overpotential calculations"""
    reactor = basic_electrolysis_reactor
    
    # Test at different current densities
    current_densities = [100.0, 500.0, 1000.0]
    overpotentials = []
    
    for i in current_densities:
        eta = reactor.calculate_overpotential(i)
        overpotentials.append(sum(eta.values()))
    
    # Overpotential should increase with current density
    assert overpotentials[1] > overpotentials[0]
    assert overpotentials[2] > overpotentials[1]
    
    # Test components
    eta = reactor.calculate_overpotential(500.0)
    assert "activation" in eta
    assert "ohmic" in eta
    assert "concentration" in eta
    
    # Test limiting current behavior
    eta_limit = reactor.calculate_overpotential(reactor.spec.max_current_density * 0.99)
    assert eta_limit["concentration"] < float('inf')
    
    with pytest.raises(ValueError):
        reactor.calculate_overpotential(reactor.spec.max_current_density * 1.1)

def test_faraday_law(basic_electrolysis_reactor):
    """Test production rates according to Faraday's law"""
    reactor = basic_electrolysis_reactor
    reactor.start()
    
    # Set a known current density
    reactor.current_density = 1000.0  # A/m²
    
    inputs = {ResourceType.H2O: 1.0}  # Excess water
    outputs = reactor.step(1.0, inputs)
    
    # Calculate expected production from Faraday's law
    F = constants.physical_constants['Faraday constant'][0]
    expected_h2 = reactor.current_density * reactor.spec.electrode_area * 1.0 / (2 * F)
    expected_o2 = expected_h2 / 2
    
    assert np.isclose(outputs[ResourceType.H2], expected_h2, rtol=1e-10)
    assert np.isclose(outputs[ResourceType.O2], expected_o2, rtol=1e-10)
    assert np.isclose(outputs[ResourceType.H2O], inputs[ResourceType.H2O] - 2 * expected_o2, rtol=1e-10)

def test_membrane_degradation(basic_electrolysis_reactor):
    """Test membrane degradation over time"""
    reactor = basic_electrolysis_reactor
    reactor.start()
    
    initial_degradation = reactor.membrane_degradation
    
    # Run at high current density
    reactor.current_density = reactor.spec.max_current_density * 0.9
    inputs = {ResourceType.H2O: 1.0}
    
    # Simulate for 24 hours
    for _ in range(24):
        reactor.step(3600.0, inputs)
    
    # Membrane should show degradation
    assert reactor.membrane_degradation < initial_degradation
    
    # Higher current density should cause faster degradation
    reactor = basic_electrolysis_reactor
    reactor.start()
    reactor.current_density = reactor.spec.max_current_density * 0.5
    
    for _ in range(24):
        reactor.step(3600.0, inputs)
    
    assert reactor.membrane_degradation > initial_degradation / 2

def test_safety_limits(basic_electrolysis_reactor):
    """Test safety limit handling"""
    reactor = basic_electrolysis_reactor
    reactor.start()
    
    # Test temperature limit
    reactor.state.temperature = reactor.spec.max_temperature + 10.0
    assert not reactor.check_safety_limits()
    assert reactor.operational_status == OperationalStatus.FAULT
    
    # Reset and test pressure limit
    reactor = basic_electrolysis_reactor
    reactor.start()
    reactor.state.pressure = reactor.spec.max_pressure + 1e5
    assert not reactor.check_safety_limits()
    assert reactor.operational_status == OperationalStatus.FAULT

def test_power_consumption(basic_electrolysis_reactor):
    """Test power consumption calculations"""
    reactor = basic_electrolysis_reactor
    
    # When standby, should be zero
    logger.debug("Testing power consumption:")
    logger.debug(f"Initial power (standby): {reactor.calculate_power_consumption()}W")
    assert reactor.calculate_power_consumption() == 0.0
    
    # When running, should follow V*I relationship
    reactor.start()
    initial_current = 1000.0  # A/m²
    reactor.current_density = initial_current
    logger.debug("Running state:")
    logger.debug(f"Current density: {reactor.current_density} A/m²")
    logger.debug(f"Max current density: {reactor.spec.max_current_density} A/m²")
    logger.debug(f"Electrode area: {reactor.spec.electrode_area} m²")
    
    power = reactor.calculate_power_consumption()
    logger.debug(f"Initial power: {power}W")
    assert power > 0.0
    
    # Power should scale with current density
    reactor.current_density *= 2
    logger.debug("After doubling current:")
    logger.debug(f"New current density: {reactor.current_density} A/m²")
    new_power = reactor.calculate_power_consumption()
    logger.debug(f"New power: {new_power}W")
    logger.debug(f"Expected power: {power * 2}W")
    logger.debug(f"Max power: {reactor.spec.max_power}W")
    logger.debug(f"Power ratio: {new_power/(power * 2)}")
    assert np.isclose(reactor.calculate_power_consumption(), power * 2, rtol=0.2)

def test_efficiency(basic_electrolysis_reactor):
    """Test overall system efficiency"""
    reactor = basic_electrolysis_reactor
    reactor.start()
    
    # Set moderate current density
    reactor.current_density = 500.0  # A/m²
    
    inputs = {ResourceType.H2O: 1.0}
    outputs = reactor.step(1.0, inputs)
    
    # Calculate efficiency
    HHV_H2 = 286e3  # J/mol
    power_in = reactor.calculate_power_consumption()
    power_out = outputs[ResourceType.H2] * HHV_H2
    
    efficiency = power_out / power_in
    assert 0.5 < efficiency < 0.9  # Typical range for PEM electrolysis 