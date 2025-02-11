# Battery Implementation

## Overview
Simple battery implementation for power storage and delivery in the ISRU power system.

## Requirements
- Store and deliver energy within capacity limits
- Respect maximum charge/discharge power limits
- Track state of charge
- Handle faults gracefully
- Integrate with PowerSystem base class

## Interface

### BatterySpecification
```python
@dataclass
class BatterySpecification:
    capacity_wh: float      # Total energy storage in Watt-hours
    max_power: float        # Maximum charge/discharge rate in Watts
```

### Battery Class
```python
class Battery(PowerSystem):
    def __init__(self, spec: BatterySpecification):
        self.spec = spec
        self.energy_wh = 0.0
        self.status = PowerSystemStatus.ONLINE

    @property
    def state_of_charge(self) -> float:
        """Return 0-1 state of charge"""
        return self.energy_wh / self.spec.capacity_wh

    def update(self, power: float, dt: float) -> float:
        """
        Update battery state with power flow
        Args:
            power: Power in Watts (positive = charging, negative = discharging)
            dt: Time step in seconds
        Returns:
            Actual power used (may be limited by constraints)
        """
```

## Behavior

### Normal Operation
- Accept power up to max_power for charging
- Deliver power up to max_power for discharging
- Track energy stored based on power * time

### Limits
- Cannot exceed capacity_wh when charging
- Cannot go below 0 Wh when discharging
- Must reduce power when approaching limits
- Must stay within ±max_power

### Faults
- Invalid power/time inputs
- Hardware faults (future expansion)

## Testing

### Test Cases
1. Battery specification validation
2. Initial state verification
3. Normal charging operation
4. Normal discharging operation
5. Power limits enforcement
6. Capacity limits handling
7. Fault detection and handling

### Key Assertions
- Power limits respected
- Energy properly tracked
- State of charge accurate
- Faults handled gracefully 