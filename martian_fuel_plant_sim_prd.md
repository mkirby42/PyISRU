# Martian ISRU Fuel Production Plant - Product Requirements Document (PRD)

## 🌍 Overview

This project simulates a modular, scalable in-situ resource utilization (ISRU) plant on Mars capable of producing methane and oxygen for SpaceX Starship refueling. The system focuses on producing enough fuel for Mars ascent and return to Earth, with scalability to support multiple vehicles.

The simulation will be composed of modular software components representing real physical subsystems, using progressively higher fidelity over time. It will include a data-rich visualization dashboard and be deployable as a Flask app.

---

## 🧭 Goals

* Simulate a Starship-capable ISRU system with realistic constraints.
* Support modular growth in fidelity (e.g., microkinetics, hardware degradation, alternate designs).
* Visualize plant operation with Plotly (real-time and historical playback).
* Educate and demonstrate technical depth and system thinking for prospective employers.

---

## 📐 Technical Specifications

### 🎯 Target Production Rate & Cycle Duration

* **Starship Requirement**:

  * Methane (CH₄): 330,000 kg
  * Oxygen (O₂): 880,000 kg
* **Refueling Cycle Duration**: Default = **30 sols** (\~1 month)
* **Daily Output Targets**:

  * CH₄: \~11,000 kg/day (\~460 kg/hr)
  * O₂: \~29,000 kg/day (\~1,210 kg/hr)

### ⚡ Electrolyzer (Solid Oxide - Baseline)

* **Power Consumption**: \~38 kWh/kg H₂ (target), or \~0.3 kW per 10 g/hr O₂ (NASA MOXIE scaling)
* **Hydrogen Requirement**: \~44,000 kg/day
* **Daily Energy Demand**: \~1.672 GWh/day (\~70 MW continuous if 24/7)
* **Future Additions**: Degradation modeling, alternate electrolyzer technologies

### 🌀 Atmospheric Intake (Scroll Compressor)

* **Function**: Compress & filter Martian CO₂ atmosphere
* **Scaling Reference**: MOXIE = 120 W for 83 g/hr CO₂ → \~1.5 kW per 1 kg/hr CO₂ intake
* **Initial Assumption**: \~5 kW draw, scalable
* **Losses**: Configurable filtering efficiency
* **Future Addition**: CO₂ purity modeling

### 🧪 Sabatier Reactor (Single Bed - Baseline)

* **Reaction**: CO₂ + 4H₂ → CH₄ + 2H₂O
* **Power Draw**: \~200 kWh/kg CH₄ → \~2.2 GWh/day → \~92 MW continuous (scalable)
* **Heat Removal**: \~1.1 kW thermal cooling per 1 kg/hr CH₄
* **Performance**: Yield depends on temperature and pressure
* **Product Loop**: Water recycled to electrolysis
* **Future Additions**: Multi-bed, microkinetic modeling, catalyst degradation

### ☀️ Power Plant (Solar + Battery)

* **Solar Irradiance (Mars avg)**: \~590 W/m²
* **Panel Efficiency**: \~20% → \~118 W/m² peak output
* **Required Array**: \~8,500–10,000 m² for 1 MW
* **Battery Storage**: \~1–2 MWh, sized to cover nighttime or storm periods
* **Challenges**: Night power, storm derating, charge/discharge efficiency (\~90%)

---

## 📦 Modules

### 1. Electrolysis Module

* **Type**: Solid oxide (initial)
* **Inputs**: H₂O
* **Outputs**: H₂ (to Sabatier), O₂ (stored)
* **Power demand**: Realistic values, scales with throughput
* **Future TODO**:

  * Degradation modeling
  * Alternate electrolyzer types

### 2. Power Plant Module

* **Type**: Solar + Battery
* **Handles**:

  * Power generation (with day/night cycle, solar irradiance)
  * Battery storage (charge/discharge efficiency, capacity limits)
* **Simulation features**:

  * Dust storms affecting generation
  * Brownouts and load management

### 3. Atmosphere Intake System

* **Type**: Scroll compressor (MOXIE-inspired)
* **Function**: Intake Mars atmosphere, filter, pressurize to reactor spec
* **Simulates**:

  * Power draw
  * Throughput
  * Filtering losses
* **Future TODO**:

  * CO₂ purity handling and monitoring

### 4. Sabatier Reactor Module

* **Type**: Single-bed reactor (initial)
* **Reaction**: CO₂ + 4H₂ → CH₄ + 2H₂O
* **Simulates**:

  * Temp/pressure dependent yield
  * Thermal regulation (heating/cooling curves)
  * Water loop back to electrolysis
* **Future TODO**:

  * Staged reactors
  * Microkinetic models
  * Catalyst degradation

### 5. Martian Environment Module

* **Features**:

  * Day/night cycle based on lat/lon
  * Solar irradiance
  * Temperature profiles
  * Altitude and atmospheric density
  * Dust storm events
* **User input**:

  * Latitude, longitude, altitude
  * Weather event injection

---

## 🧪 Simulation Framework

### ⏱️ Timestep Granularity

* **Default timestep**: 1 minute (60s)
* **Per-module update frequency**:

  * Fast (e.g. thermal): every timestep
  * Slow (e.g. solar, weather): every 10–60 minutes
* **Scheduler logic**: Each module defines `next_update_time` and `simulate(dt)` method

### 🔥 Operating Limits & Safety Shutdowns

**Each Module Should Have:**
* Max operating temperature, pressure, flow rate
* Min thresholds (e.g., cooling water flow, H₂ supply pressure)

**Behavior When Exceeded:**
* **Soft violation**: log warning + degrade performance
* **Hard violation**: force shutdown + cooldown period

```python
if temp > max_temp:
    self.status = 'shutdown'
    self.recovery_time = now + cooldown_period
```

### 🧯 Safety Margins

| Component | Safety Margin | Reason |
|-----------|---------------|---------|
| Battery | 20% min SoC | Prevent deep discharge damage |
| Reactors | 90% of rated temp | Avoid catalyst sintering |
| Tanks | 80–90% fill limit | Prevent overpressure risk |

*Make these configurable per scenario or as constants in `safety.py`*

### ⚠️ Failure Modes & Status Management

**Module Status Types:**
```python
class Status(Enum):
    OK = 'ok'
    DEGRADED = 'degraded'
    IDLE = 'idle'
    SHUTDOWN = 'shutdown'
```

**Failure Response Matrix:**

| Condition | Effect |
|-----------|--------|
| Exceed soft limit | Reduced efficiency (e.g., 70% yield) |
| Exceed hard limit | Forced shutdown, logs |
| Insufficient power | Throttled operation or idle |
| Blocked inputs | Stalled throughput |

### 💡 Brownout Response & Power Management

**Priority-Based Power Allocation:**
```python
if available_kw < total_demand:
    for module in sorted(modules, key=lambda m: m.priority):
        granted_kw = min(available_kw, module.min_power)
        module.apply_power(granted_kw)
        available_kw -= granted_kw
```

**Each module reports:**
* `power_requested`
* `power_granted` 
* `min_power`, `max_power`
* `priority` (1=critical, 5=deferrable)

### 💾 State Persistence

* **Supports**: Pause/resume, checkpointing
* **Modes**:

  * In-memory: testing/iteration
  * File-based (e.g. JSON): long runs, replay
* **Each module implements**:

  ```python
  def save_state(self) -> dict
  def load_state(self, state: dict)
  ```

### 🔌 Module Interface Pattern

* **Central `PlantState`** shared among all modules
* Contains:

  * Material stores (CH₄, O₂, CO₂, H₂O, H₂)
  * Power supply/demand budget
  * Environment state
* Modules access shared state:

  ```python
  state.materials["H2"].withdraw(kg=5)
  state.power_budget.consume(kw=250)
  ```

### 📦 Material Store Properties

**Recommended Abstraction:**
* **Core**: Mass only (kg)
* **Extended**: Optional metadata for gas handling & thermal balance

```python
class MaterialStore:
    def __init__(self, name, mass_kg, pressure_kpa=None, temperature_k=None)
```

**Pressure/temperature relevant for:**
* Gas handling (compressors, tanks)
* Thermal balance (future fidelity)

### ⚡ Power Budget Tracking

**Per-Module Granularity:**
* Each module reports:
  * `power_requested`
  * `power_granted`
  * `min_power`, `max_power`
* Aggregator handles:
  * Total draw vs available
  * Deficit response
* Enables dashboard views:
  * Instantaneous usage
  * Shortages per component  
  * Time under-power

### 🚦 Flow Rate Coordination

* All `store()` and `withdraw()` methods return actual flow result
* Upstream production capped by downstream consumption limits
* Modules react to failed/partial transactions to modulate behavior

### 🧠 Simulation Engine Responsibilities

* Schedule per-module updates
* Aggregate power usage and material flows
* Enforce constraints (e.g. max battery output)
* Manage state persistence

### 📝 Output Format

* Pandas-compatible logs and states
* Daily/sol summaries for dashboard

---

## 🧑‍💻 User Experience

### 🔧 Parameter Modification

* **Startup config**: all parameters loaded from config or scenario file
* **Optional live tuning**: selected parameters (e.g. power limits) may be adjustable via dashboard/API
* **Preset scenarios**:

  * `equatorial_clear`: low dust, high irradiance
  * `polar_base`: long nights, low irradiance
  * `dust_storm_season`: frequent solar derating
  * `scaled_up`: supports 2+ Starships

### ⏱️ Simulation Speed Modes

* **Real-time**: 1 minute sim = 1 minute wall time
* **Accelerated**: 10× or 100× faster than real time
* **Headless**: Max-speed batch sim for offline analysis
* **Configurable**: `SIMULATION_SPEED` parameter adjusts time scaling
* **Target performance**:

  * 30 sols in <5 minutes (baseline)
  * 100 sols in <2 minutes (headless mode)

---

## 📊 Visualization / Dashboard (Plotly)

* **Core Views**:

  * Power generation & consumption over time
  * Mass flow (CH₄, O₂, CO₂, H₂O, H₂)
  * Reactor performance (temp, pressure, yield)
  * Electrolyzer load vs output
  * Solar irradiance + environment view
  * Battery state-of-charge
  * Timeline scrubber with pause/play & playback speed
* **Event visualizations**:

  * Dust storm overlay
  * Brownout indicators
  * Cycle-by-cycle analysis (e.g., daily output)

---

## ⚙️ Deployment Target

* Flask app integration
* Self-contained modules (importable, testable)
* Lightweight simulation engine for rapid prototyping

---

## 🗺️ Roadmap

1. **Baseline Simulation**

   * Core loop
   * One of each module
   * Plotly live output
2. **Progressive Fidelity Improvements**

   * Add degradation models
   * Replace approximations with empirical equations
   * Parameterizable component design
3. **Environmental Expansion**

   * Multiple location presets
   * Real-world terrain effects
   * Dust storm dynamics
4. **Community Layer**

   * Blog post + embedded dashboard
   * Usage instructions for fellow hobbyists

---

## 🔧 Development Notes

* Code in Python
* Use design patterns for modularity (e.g., Strategy for swapping electrolyzer, Observer for power tracking)
* Favor pure functions and state containers for testability
* Each module should have `simulate(timestep: float)` method returning deltas in state and power/material flow

---

## ✍️ Blog Post Goals

* Convey modularity and realism
* Demonstrate how each component mimics reality
* Explore edge cases (dust storm, power outage)
* Show simulations at different Mars sites (polar vs equator)
* Highlight scalability: 1 → n Starships
