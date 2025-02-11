# Power Transmission System Design

## Overview
The power transmission system manages power distribution between sources (solar arrays, KRUSTY, batteries) and loads across the mars base.

## Core Components

### 1. Transmission Types
- **DC Distribution**: 120V DC main bus only
  - Simpler than mixed AC/DC
  - Matches solar/battery native DC
  - Fewer conversion losses

### 2. Bus Architecture
- **Main Bus**: 120V DC primary distribution
- **Critical Bus**: Battery-backed for life support
- **Secondary Bus**: Non-critical loads

### 3. Protection Systems
- Over/under voltage protection (±10% nominal)
- Overcurrent protection (120% rated)
- Automatic bus isolation

### 4. Load Management
- Simple priority-based load shedding:
  - Priority 1: Life support
  - Priority 2: ISRU core
  - Priority 3: Everything else

## Key Parameters

### Transmission Specifications
- Bus Voltage: 120V DC
- Maximum System Power: 100kW
- Transmission Efficiency: ≥95%

### Protection Thresholds
- Undervoltage: 0.9 pu
- Overvoltage: 1.1 pu
- Overcurrent: 1.2x rated

## Implementation Details

### Bus Management
```python
class BusManager:
    def __init__(self):
        self.buses = {
            'MAIN': {'voltage': 120},
            'CRITICAL': {'voltage': 120},
            'SECONDARY': {'voltage': 120}
        }
```

### Core Features
- Basic fault detection and isolation
- Simple load shedding based on fixed priorities
- Power monitoring and basic telemetry

## Safety Features

1. Galvanic isolation between buses
2. Redundant ground paths
3. Emergency shutdown systems
4. Thermal monitoring
5. EMI/RFI protection
6. Surge protection

## Future Considerations

1. Smart grid capabilities
2. Machine learning for fault prediction
3. Dynamic topology reconfiguration
4. Advanced power quality management
5. Integration with base-wide energy management 