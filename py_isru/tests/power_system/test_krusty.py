"""
Tests for KRUSTY reactor implementation.
"""
import numpy as np
import pytest

from py_isru.lib.power_system import (
    KrustyReactor,
    KrustySpecification,
    PowerSystemStatus,
)

@pytest.fixture
def basic_krusty_spec():
    """Basic KRUSTY reactor specification"""
    return KrustySpecification(
        nominal_power=2500.0,  # 2.5 kW nominal electrical
        max_power=3000.0,     # 3 kW max electrical
        startup_time=3600.0,  # 1 hour startup
        cooldown_time=7200.0, # 2 hour cooldown
        burn_in_time=86400.0  # 24 hour burn-in
    )

def test_krusty_spec_validation():
    """Test KRUSTY specification validation"""
    # Valid spec should work
    spec = KrustySpecification(
        nominal_power=2500.0,
        max_power=3000.0,
        startup_time=3600.0,
        cooldown_time=7200.0,
        burn_in_time=86400.0
    )
    assert spec.nominal_power == 2500.0
    assert spec.max_power == 3000.0
    
    # Test invalid specs
    with pytest.raises(ValueError, match="Nominal power must be positive"):
        KrustySpecification(
            nominal_power=-2500.0,
            max_power=3000.0,
            startup_time=3600.0,
            cooldown_time=7200.0,
            burn_in_time=86400.0
        )
    
    with pytest.raises(ValueError, match="Max power must be greater than nominal power"):
        KrustySpecification(
            nominal_power=3000.0,
            max_power=2500.0,
            startup_time=3600.0,
            cooldown_time=7200.0,
            burn_in_time=86400.0
        )

def test_krusty_startup(basic_krusty_spec):
    """Test KRUSTY reactor startup sequence"""
    reactor = KrustyReactor(basic_krusty_spec)
    assert reactor.status == PowerSystemStatus.OFFLINE
    
    # Start reactor
    assert reactor.start()
    assert reactor.status == PowerSystemStatus.ONLINE
    
    # Check initial state
    assert reactor.startup_progress == 0.0
    assert reactor.calculate_output() == 0.0
    
    # Step through startup
    dt = 360.0  # 6-minute steps
    steps = int(basic_krusty_spec.startup_time / dt)
    
    for i in range(steps):
        reactor.step(dt)
        progress = (i + 1) / steps
        assert np.isclose(reactor.startup_progress, progress, rtol=0.1)
        
        # Power should ramp up linearly
        expected_power = basic_krusty_spec.nominal_power * progress
        assert np.isclose(reactor.calculate_output(), expected_power, rtol=0.1)
        
    # Final state
    assert np.isclose(reactor.startup_progress, 1.0, rtol=1e-10)  # Use tighter tolerance for final check
    assert np.isclose(
        reactor.calculate_output(),
        basic_krusty_spec.nominal_power,
        rtol=0.01
    )

def test_krusty_shutdown(basic_krusty_spec):
    """Test KRUSTY reactor shutdown sequence"""
    reactor = KrustyReactor(basic_krusty_spec)
    
    # Start and complete startup
    reactor.start()
    reactor.step(basic_krusty_spec.startup_time)
    initial_power = reactor.calculate_output()
    
    # Shutdown
    assert reactor.shutdown()
    assert reactor.status == PowerSystemStatus.OFFLINE
    assert reactor.cooldown_progress == 0.0
    
    # Step through cooldown
    dt = 360.0  # 6-minute steps
    steps = int(basic_krusty_spec.cooldown_time / dt)
    
    for i in range(steps):
        reactor.step(dt)
        progress = (i + 1) / steps
        assert np.isclose(reactor.cooldown_progress, progress, rtol=0.1)
        
        # Power should ramp down linearly
        expected_power = initial_power * (1.0 - progress)
        assert np.isclose(reactor.calculate_output(), expected_power, rtol=0.1)
        
    # Final state
    assert reactor.cooldown_progress == 1.0
    assert reactor.calculate_output() == 0.0

def test_krusty_degradation(basic_krusty_spec):
    """Test KRUSTY reactor degradation mechanisms"""
    reactor = KrustyReactor(basic_krusty_spec)
    
    # Start and run for one year
    reactor.start()
    reactor.step(basic_krusty_spec.startup_time)  # Complete startup
    
    # Run for one year
    year_seconds = 365.25 * 24 * 3600
    dt = 3600.0  # 1-hour steps
    steps = int(year_seconds / dt)
    
    initial_power = reactor.calculate_output()
    
    for _ in range(steps):
        reactor.step(dt)
        
    # Check degradation components
    assert reactor.fuel_burnup == pytest.approx(0.005, rel=1e-3)  # 0.5% per year
    assert reactor.thermoelectric_degradation == pytest.approx(0.01, rel=1e-3)  # 1% per year
    assert reactor.material_creep == pytest.approx(0.001, rel=1e-3)  # 0.1% per year
    
    # Check power output reduction
    final_power = reactor.calculate_output()
    expected_reduction = 1.0 - (
        reactor.fuel_burnup + 
        reactor.thermoelectric_degradation + 
        reactor.material_creep
    )
    assert np.isclose(final_power / initial_power, expected_reduction, rtol=0.01)

def test_krusty_protection(basic_krusty_spec):
    """Test KRUSTY reactor protection systems"""
    reactor = KrustyReactor(basic_krusty_spec)
    
    # Start reactor
    reactor.start()
    reactor.step(basic_krusty_spec.startup_time)
    
    # Force a calculation error
    reactor.current_power = float('nan')
    reactor.step(60.0)  # Run for 1 minute
    
    # Should enter fault mode
    assert reactor.status == PowerSystemStatus.FAULT
    assert reactor.fault_condition is not None
    assert "error" in reactor.fault_condition.lower()
    assert reactor.calculate_output() == 0.0

def test_krusty_negative_timestep(basic_krusty_spec):
    """Test handling of negative time steps"""
    reactor = KrustyReactor(basic_krusty_spec)
    reactor.start()
    
    with pytest.raises(ValueError, match="Time step must be positive"):
        reactor.step(-1.0)

def test_krusty_burn_in(basic_krusty_spec):
    """Test KRUSTY burn-in period"""
    reactor = KrustyReactor(basic_krusty_spec)
    
    # Start reactor
    reactor.start()
    reactor.step(basic_krusty_spec.startup_time)
    
    # Initially not burned in
    assert not reactor.burn_in_complete
    
    # Run for just under burn-in time (accounting for startup time)
    remaining_time = basic_krusty_spec.burn_in_time - basic_krusty_spec.startup_time - 1.0
    reactor.step(remaining_time)
    assert not reactor.burn_in_complete
    
    # Complete burn-in
    reactor.step(2.0)
    assert reactor.burn_in_complete

def test_krusty_fault_handling(basic_krusty_spec):
    """Test KRUSTY fault handling"""
    reactor = KrustyReactor(basic_krusty_spec)
    
    # Start reactor
    reactor.start()
    
    # Force a calculation error
    reactor.current_power = float('nan')
    reactor.step(1.0)
    
    # Should enter fault state
    assert reactor.status == PowerSystemStatus.FAULT
    assert reactor.fault_condition is not None
    assert "error" in reactor.fault_condition.lower()
    
    # Power output should be zero in fault state
    assert reactor.calculate_output() == 0.0 