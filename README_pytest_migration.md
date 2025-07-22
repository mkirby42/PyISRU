# PyISRU Test Suite Migration to Pytest

This document explains the migration from custom test scripts to pytest and how to use the new test suite.

## What Changed

### Before (Custom Test Scripts)
- `test_simulation.py` - Custom main() function with manual test orchestration
- `test_core_framework.py` - Custom test functions with print statements
- `test_atmosphere_intake.py` - Manual test execution and validation
- `debug_modules.py` - Debug script for individual modules
- `debug_sabatier.py` - Debug script for Sabatier reactor
- `quick_test.py` - Quick validation script
- `quick_massive_test.py` - Massive power plant test

### After (Pytest)
- All tests moved to `tests/` directory with proper organization
- All tests converted to pytest format with proper fixtures and assertions
- `tests/conftest.py` - Shared fixtures and helper functions
- `pytest.ini` - Test configuration with `testpaths = tests`
- `tests/test_debug.py` - Debug tests replacing the debug scripts
- Proper test markers for organization (`@pytest.mark.unit`, `@pytest.mark.integration`, etc.)

## Installation

Install pytest and related dependencies:

```bash
pip install -r requirements.txt
```

## Running Tests

### Run All Tests
```bash
pytest
```

### Run Specific Test Categories

**Unit Tests Only:**
```bash
pytest -m unit
```

**Integration Tests:**
```bash
pytest -m integration
```

**Full Simulation Tests:**
```bash
pytest -m simulation
```

**Debug Tests (replacing old debug scripts):**
```bash
pytest -m debug
```

**Power System Tests:**
```bash
pytest -m power
```

**Material Flow Tests:**
```bash
pytest -m materials
```

### Run Specific Test Files

**Core Framework Tests:**
```bash
pytest tests/test_core_framework.py
```

**Simulation Tests:**
```bash
pytest tests/test_simulation.py
```

**Atmosphere Intake Tests:**
```bash
pytest tests/test_atmosphere_intake.py
```

**Debug Tests:**
```bash
pytest tests/test_debug.py
```

### Skip Slow Tests
```bash
pytest -m "not slow"
```

### Run Tests in Parallel (if you have pytest-xdist)
```bash
pytest -n auto
```

### Generate Coverage Report
```bash
pytest --cov=src --cov-report=html
```

## Test Markers

The test suite uses markers to categorize tests:

- `@pytest.mark.unit` - Unit tests for individual components
- `@pytest.mark.integration` - Integration tests for component interactions  
- `@pytest.mark.simulation` - Full simulation tests
- `@pytest.mark.slow` - Slow-running tests
- `@pytest.mark.power` - Power system tests
- `@pytest.mark.materials` - Material flow tests
- `@pytest.mark.environment` - Environmental condition tests
- `@pytest.mark.debug` - Debug and diagnostic tests

## Key Features

### Fixtures
- `basic_simulation` - Basic simulation with environment module
- `power_simulation` - Simulation with power module added
- `full_isru_simulation` - Complete ISRU simulation with all modules
- `power_scenarios` - Different power configurations for testing
- `production_targets` - Production targets for validation

### Parametrized Tests
Many tests are parametrized to test multiple scenarios:

```python
@pytest.mark.parametrize("power_scenario,expected_ch4_min", [
    ("limited", 0),      # Should produce very little due to power shortage
    ("adequate", 500),   # Should produce moderate amounts  
    ("massive", 2000),   # Should produce significant amounts
])
def test_power_scenario_simulation(full_simulation_factory, power_scenario, expected_ch4_min):
    # Test implementation
```

### Helper Functions
- `assert_material_balance()` - Verify material conservation
- `assert_power_balance()` - Verify power allocation is reasonable
- `assert_production_rates()` - Verify minimum production rates

## Migration from Old Scripts

### Old Debug Scripts → New Debug Tests

| Old Script | New Test | Command |
|-----------|----------|---------|
| `debug_modules.py` | `test_debug.py::test_individual_module_debug` | `pytest test_debug.py::test_individual_module_debug -v` |
| `debug_sabatier.py` | `test_debug.py::test_sabatier_debug` | `pytest test_debug.py::test_sabatier_debug -v` |
| `quick_massive_test.py` | `test_debug.py::test_massive_power_quick_test` | `pytest test_debug.py::test_massive_power_quick_test -v` |
| `quick_test.py` | Multiple tests in `test_debug.py` | `pytest test_debug.py -k "basic" -v` |

### Old Test Scripts → New Test Files

| Old File | New File | Purpose |
|----------|----------|---------|
| `test_simulation.py` | `test_simulation.py` | Full simulation tests with parametrized scenarios |
| `test_core_framework.py` | `test_core_framework.py` | Core framework unit and integration tests |
| `test_atmosphere_intake.py` | `test_atmosphere_intake.py` | Atmosphere intake module tests |

## Running Equivalent Tests

### To run what used to be `debug_modules.py`:
```bash
pytest test_debug.py::test_individual_module_debug -v -s
```

### To run what used to be `quick_massive_test.py`:
```bash
pytest test_debug.py::test_massive_power_quick_test -v -s
```

### To run the full simulation test suite:
```bash
pytest test_simulation.py -v
```

### To run all tests that were in the old test files:
```bash
pytest tests/test_core_framework.py tests/test_simulation.py tests/test_atmosphere_intake.py -v
```

## Debugging Failed Tests

### Verbose Output
```bash
pytest -v -s test_debug.py::test_sabatier_debug
```

### Show Print Statements
```bash
pytest -s test_debug.py
```

### Stop on First Failure
```bash
pytest -x
```

### Drop into PDB on Failure
```bash
pytest --pdb
```

## Benefits of Pytest Migration

1. **Better Organization** - Tests are properly categorized with markers
2. **Shared Fixtures** - Common setup code is reusable across tests  
3. **Parametrized Tests** - Easy to test multiple scenarios
4. **Better Assertions** - Clear error messages when tests fail
5. **Parallel Execution** - Tests can run in parallel for speed
6. **Coverage Reports** - Easy to generate test coverage reports
7. **CI/CD Integration** - Works well with continuous integration systems
8. **Plugin Ecosystem** - Many useful plugins available

## File Cleanup

The following files can be removed after confirming the new tests work:
- `debug_modules.py`
- `debug_sabatier.py` 
- `quick_test.py`
- `quick_massive_test.py`

The JSON result files are preserved:
- `limited_power_results.json`
- `scaled_power_results.json`
- `simulation_results.json`

## Next Steps

1. Run the new test suite to verify everything works
2. Remove old debug scripts if satisfied with new tests  
3. Add any missing test coverage for new features
4. Integrate with CI/CD pipeline
5. Consider adding property-based testing with Hypothesis 