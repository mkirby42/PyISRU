"""
Tests for electrolysis reactor implementation.
"""
import pytest
import logging
from math import isclose

# Adjust these imports to match your project structure.
from py_isru.lib.electrolysis_reactor import ElectrolysisReactor, ElectrolysisSpecification
from py_isru.lib.thermodynamics import ThermodynamicState, ReactionKinetics
from py_isru.lib.reactor import ResourceType, OperationalStatus

logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Dummy ReactionKinetics to supply required kinetic parameters
# -----------------------------------------------------------------------------

class DummyKinetics(ReactionKinetics):
    def get_exchange_current_density(self, T_K: float) -> float:
        # Return a constant exchange current density (A/m²)
        return 1e-3  # 1 mA/m²

    def get_operating_current_density(self, T_K: float) -> float:
        # For testing, return a target operating current density.
        # For example, 50% of max current density.
        return 500.0  # A/m²

# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture
def electrolysis_spec():
    """Electrolysis reactor specification (with units in variable names)."""
    return ElectrolysisSpecification(
        volume_m3=1.0,
        max_temperature_K=1000.0,
        max_pressure_Pa=5e6,
        thermal_mass_J_per_K=1e4,
        heat_loss_coefficient_W_per_m2K=10.0,
        surface_area_m2=5.0,
        membrane_type="Nafion",
        membrane_thickness_m=0.0002,          # 0.2 mm
        membrane_conductivity_S_per_m=10.0,
        electrode_area_m2=1.0,
        max_current_density_A_per_m2=1000.0,
        max_power_W=10000.0,
        startup_time_s=10.0,
        shutdown_time_s=10.0
    )

@pytest.fixture
def initial_state():
    """Initial thermodynamic state at 600 K and 1e5 Pa using water properties."""
    return ThermodynamicState.from_temperature_pressure(600.0, 1e5, substance="H2O")

@pytest.fixture
def dummy_kinetics():
    """Dummy kinetics object to provide exchange and operating current densities."""
    # The parameters for ReactionKinetics below are not used directly by the dummy.
    return DummyKinetics(rate_constant_forward_1_s_inv=1e3,
                         activation_energy_J_per_mol=80000,
                         reaction_order={})

@pytest.fixture
def initial_composition():
    """
    Initial internal composition (mol) of the reactor.
    Start with 100 mol H2O and no H2/O2.
    """
    return {
        ResourceType.H2O: 100.0,
        ResourceType.H2: 0.0,
        ResourceType.O2: 0.0
    }

@pytest.fixture
def reactor(electrolysis_spec, initial_state, dummy_kinetics, initial_composition):
    """Create an ElectrolysisReactor instance for testing."""
    return ElectrolysisReactor(electrolysis_spec, initial_state, initial_composition, dummy_kinetics)

# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------

def test_startup(reactor):
    """
    Test that the reactor transitions from STANDBY to RUNNING via startup,
    the current density ramps up, and membrane hydration is restored.
    """
    assert reactor.operational_status == OperationalStatus.STANDBY
    reactor.start()
    assert reactor.operational_status == OperationalStatus.RUNNING
    assert reactor.current_density_A_per_m2 > 0
    # Membrane hydration should move toward full hydration (1.0)
    assert reactor.membrane_hydration > 0.8

def test_shutdown(reactor):
    """
    Test that the reactor transitions properly from RUNNING to STANDBY via shutdown,
    and that the current density is reduced to zero.
    """
    reactor.start()
    assert reactor.operational_status == OperationalStatus.RUNNING
    reactor.shutdown()
    assert reactor.operational_status == OperationalStatus.STANDBY
    assert isclose(reactor.current_density_A_per_m2, 0.0, rel_tol=1e-3)

def test_step_update(reactor):
    """
    Test that after a simulation step:
      - The reactor produces H2 and O2 (via Faraday's law),
      - Internal composition is updated (H2 and O2 accumulate, water is consumed),
      - Temperature changes from the energy balance.
    """
    # Provide a constant water input (mol/s)
    inputs = {
        ResourceType.H2O: 10.0
    }
    initial_temp = reactor.state.temperature_K
    initial_comp = reactor.composition_mol.copy()
    
    outputs = reactor.step(1.0, inputs)
    
    # Check that H2 and O2 are produced (nonzero production rate)
    assert outputs[ResourceType.H2] > 0
    assert outputs[ResourceType.O2] > 0
    # Ensure water output equals water input (assuming constant withdrawal to maintain volume)
    assert isclose(outputs[ResourceType.H2O], inputs[ResourceType.H2O], rel_tol=1e-3)
    # Verify that internal composition shows production:
    assert reactor.composition_mol[ResourceType.H2] > initial_comp[ResourceType.H2]
    assert reactor.composition_mol[ResourceType.O2] > initial_comp[ResourceType.O2]
    # Temperature should change due to energy balance
    assert not isclose(reactor.state.temperature_K, initial_temp, rel_tol=1e-4)

def test_power_consumption_limit(reactor):
    """
    Test that the reactor's power consumption does not exceed the specified max power.
    """
    # Force a high current density to test power limiting
    reactor.current_density_A_per_m2 = reactor.spec.max_current_density_A_per_m2
    power = reactor.calculate_power_consumption()
    assert power <= reactor.spec.max_power_W

def test_membrane_degradation(reactor):
    """
    Test that after an extended period of high current operation, the membrane degradation factor decreases.
    """
    initial_deg = reactor.membrane_degradation_factor
    # Set a high current density to induce degradation
    reactor.current_density_A_per_m2 = reactor.spec.max_current_density_A_per_m2
    # Simulate one hour of operation (3600 s)
    reactor.update_membrane_degradation(3600)
    # Degradation factor should drop, but not below 0.1
    assert reactor.membrane_degradation_factor < initial_deg
    assert reactor.membrane_degradation_factor >= 0.1

def test_internal_composition_update(reactor):
    """
    Test that the internal composition is updated by the mass balance,
    indicating accumulation of produced gases.
    """
    inputs = {ResourceType.H2O: 5.0}
    total_initial = sum(reactor.composition_mol.values())
    reactor.step(1.0, inputs)
    total_after = sum(reactor.composition_mol.values())
    # Because of production of gases, total moles should increase or at least remain similar.
    assert total_after >= total_initial

def test_temperature_update(reactor):
    """
    Test that the reactor temperature changes as a result of the net energy balance.
    """
    initial_temp = reactor.state.temperature_K
    inputs = {ResourceType.H2O: 10.0}
    reactor.step(1.0, inputs)
    assert not isclose(reactor.state.temperature_K, initial_temp, rel_tol=1e-4)

def test_safety_limits(reactor):
    """
    Test that safety limits are enforced. For example, if the reactor temperature exceeds the maximum,
    check that the reactor reports a fault (assuming check_safety_limits is implemented in the base class).
    """
    # Force temperature above maximum
    reactor.state.temperature_K = reactor.spec.max_temperature_K + 100
    safe = reactor.check_safety_limits()
    assert not safe

