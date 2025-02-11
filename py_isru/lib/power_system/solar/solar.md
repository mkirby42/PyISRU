# Solar Power System Design

## Overview
Implementation of a Mars-optimized solar power generation system with basic dust and tracking considerations.

## Components

### Solar Panel
Core power generation unit with:
- Basic efficiency calculation
- Dust accumulation modeling
- Physical specifications (area, mass, etc.)
- Temperature protection

### Solar Tracker
Single or dual-axis tracking system:
- Sun position calculation
- Motor control simulation
- Power consumption modeling
- Mechanical limits

### Solar Array
Collection of panels and trackers:
- Power aggregation
- Fault detection
- Status monitoring
- Dust management

### Mars Environment
Environmental condition modeling:
- Solar irradiance calculation
- Dust accumulation
- Temperature modeling
- Atmospheric opacity

## Specifications

### SolarPanelSpecification
```python
@dataclass
class SolarPanelSpecification:
    area: float                # Panel area in m²
    base_efficiency: float     # Base efficiency at standard conditions
    max_temp: float           # Maximum safe temperature (°C)
    min_temp: float           # Minimum safe temperature (°C)
    mass: float               # Panel mass in kg
    dust_tolerance: float     # Maximum dust coverage before degraded state
```

### TrackerSpecification
```python
@dataclass
class TrackerSpecification:
    type: TrackingType        # FIXED, SINGLE_AXIS, DUAL_AXIS
    power_consumption: float  # Power used by tracking system (W)
    max_slew_rate: float     # Maximum rotation speed (deg/s)
```

### SolarArraySpecification
```python
@dataclass
class SolarArraySpecification:
    n_panels: int            # Number of panels
    panel_spec: SolarPanelSpecification
    tracker_spec: Optional[TrackerSpecification]
```

### MarsEnvironmentSpecification
```python
@dataclass
class MarsEnvironmentSpecification:
    latitude: float          # Site latitude (deg)
    longitude: float         # Site longitude (deg)
    elevation: float         # Site elevation (m)
    dust_deposition_rate: float  # Dust accumulation rate (g/m²/sol)
```

## Behavior

### Normal Operation
- Track sun position (if equipped)
- Calculate effective irradiance
- Check temperature limits
- Account for dust coverage
- Aggregate panel outputs

### Protection Features
- Temperature limit protection
- Excessive dust warnings
- Basic fault detection
- Mechanical limits

### Degradation Mechanisms
1. Dust Accumulation
   - Track dust coverage
   - Model cleaning events
   - Impact on optical efficiency

### Fault Handling
- Panel electrical faults
- Tracker mechanical faults
- Basic temperature protection
- Control system errors

## Testing

### Test Cases
1. Panel Performance
   - Standard conditions output
   - Basic temperature limits
   - Dust impact

2. Tracking Accuracy
   - Sun position calculation
   - Motor control precision
   - Power optimization
   - Fault response

3. Environmental Response
   - Temperature protection
   - Dust accumulation
   - Day/night cycles
   - Tracking efficiency

4. System Integration
   - Power aggregation
   - Load response
   - Protection features
   - Fault handling

### Key Assertions
- Power calculations accurate
- Tracking optimizes output
- Dust impact properly modeled
- Faults handled gracefully
- Protection limits enforced
- Status updates correct 