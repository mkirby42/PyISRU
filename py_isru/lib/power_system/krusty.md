# KRUSTY Reactor Implementation

## Overview
Implementation of the Kilopower Reactor Using Stirling TechnologY (KRUSTY) for reliable power generation in the ISRU system.

## Requirements
- Manage reactor startup and shutdown sequences
- Control power output at nominal levels
- Track reactor health and burn-in status
- Model constant degradation rates
- Integrate with PowerSystem base class

## Interface

### KrustySpecification
```python
@dataclass
class KrustySpecification:
    nominal_power: float      # Nominal power output in Watts
    max_power: float         # Maximum safe power output in Watts
    startup_time: float      # Time required for full startup in seconds
    cooldown_time: float     # Time required for safe shutdown in seconds
    burn_in_time: float      # Required burn-in time in seconds
```

### KrustyReactor Class
```python
class KrustyReactor(PowerSystem):
    def __init__(self, spec: KrustySpecification):
        self.spec = spec
        self.status = PowerSystemStatus.OFFLINE
        self.startup_progress = 0.0
        self.burn_in_time = 0.0
        self.current_power = 0.0  # W
```

## Behavior

### Startup Sequence
- Begin from cold shutdown state
- Ramp up power linearly over startup_time
- Progress tracked from 0.0 to 1.0

### Normal Operation
- Maintain stable power output at nominal level
- Track burn-in progress
- Apply constant degradation rates:
  - Fuel burnup: 0.5% per year
  - Thermoelectric: 1% per year
  - Material creep: 0.1% per year

### Protection
- Fault handling for calculation errors
- Emergency shutdown if faults detected

### Shutdown Sequence
- Reduce power output gradually over cooldown_time
- Progress tracked from 1.0 to 0.0

### Faults
- Power calculation errors
- Control system failures
- Invalid inputs (negative timesteps)

## Testing

### Test Cases
1. Reactor specification validation
2. Startup sequence progression
3. Normal power operation
4. Degradation tracking
5. Protection systems
6. Shutdown sequence
7. Burn-in tracking
8. Fault handling

### Key Assertions
- Startup/shutdown sequences correct
- Burn-in properly tracked
- Degradation rates accurate
- Faults handled gracefully 