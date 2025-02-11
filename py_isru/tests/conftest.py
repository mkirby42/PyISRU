"""
Test configuration and shared fixtures.
"""
import os
import sys
import pytest

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

@pytest.fixture(autouse=True)
def setup_test_env():
    """Set up test environment"""
    # Set random seed for reproducibility
    import numpy as np
    np.random.seed(42)
    
    # Set up any environment variables needed for testing
    os.environ["PYISRU_TEST"] = "1"
    
    yield
    
    # Clean up after tests
    if "PYISRU_TEST" in os.environ:
        del os.environ["PYISRU_TEST"] 