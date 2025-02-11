Product Requirements Document (PRD)

Title: Martian ISRU Plant Simulation Web App

Version: 1.2

Author: Mathew Kirby

Date: 02-09-2025

1. Overview

1.1 Summary

This project is a high-fidelity, probabilistic simulation of a Martian ISRU plant, hosted as an open-source Python web application on an AWS EC2 instance. It will use Dash (Plotly) as the frontend with Flask as the backend, offering a fully Python-based interactive dashboard.

Users will be able to:
    •    Monitor resource levels (e.g., CO₂, H₂, O₂, CH₄) in real-time.
    •    Inject system failures with probabilistic degradation models.
    •    Deploy a hybrid power system (Ballot's Solar + Batteries + KRUSTY Reactors) for redundancy.
    •    Dynamically control time progression (1 sec = 1 hour up to 1 sec = 1 year).
    •    Manually override system settings to optimize performance.

2. Scope

2.1 Features

Feature    Description    Priority
Realistic ISRU Simulation    Implements physics-based chemical processes (Sabatier, electrolysis, thermal dynamics)    High
Tank Level Visualization    Time-series display of CO₂, O₂, CH₄, H₂ storage levels    High
Environmental Effects    Models solar fluctuations, dust storms, and temperature shifts    High
Probabilistic System Failures    Components degrade or fail with realistic probabilities    High
User-Controlled System Overrides    Allows manual adjustments to system parameters    High
Hybrid Power System (Solar + Battery + KRUSTY Reactors)    Users can toggle power sources dynamically    High
Adjustable Time Acceleration    Dynamic time control from 1 sec = 1 hr to 1 sec = 1 yr    High
Dash Frontend with Flask Backend    Fully Python-based interactive UI    High
Open Source    Fully accessible codebase on GitHub    Medium
EC2 Hosting    Deploys Flask web app on an AWS EC2 instance    Medium

3. Technical Specifications

3.1 Tech Stack
    •    Backend: Flask (Python)
    •    Frontend: Dash (Plotly)
    •    Database: SQLite (or Pandas for in-memory storage)
    •    Hosting: AWS EC2
    •    Simulation Engine: NumPy, SciPy for calculations

3.2 Simulation Model

The simulation will be as realistic as possible, incorporating:

Core ISRU Processes
    1.    Sabatier Reaction
    •     CO₂ + 4H₂ → CH₄ + 2H₂O
    •    Converts atmospheric CO₂ into methane fuel and water
    •    Temperature and catalyst efficiency affect yield
    2.    Electrolysis Reaction
    •    2H₂O → 2H₂ + O₂
    •    Produces breathable oxygen and hydrogen for Sabatier reaction
    •    Power-intensive process
    3.    Atmospheric CO₂ Intake
    •    Scroll pump collects Martian CO₂, affected by atmospheric pressure & dust storms
    4.    Thermal Management
    •    Heat generation affects system performance
    •    Extreme cold can lower efficiency

3.3 Environmental Conditions

Factor    Effect on System
Solar Power Availability    Decreases during dust storms
Ambient Temperature    Affects efficiency of chemical reactions
Dust Storms    Reduces solar power & increases CO₂ intake difficulty

3.4 Power System (Ballot's Solar + Batteries + KRUSTY)

The simulation models a comprehensive hybrid power system with realistic physics and degradation:

Power Source    | Functionality    | Degradation Mechanisms
----------------|------------------|----------------------
Ballot's Solar  | Primary power    | - Temperature effects (-0.4%/K)
                |                  | - UV exposure (2% per year)
                |                  | - Radiation damage (1% per year)
                |                  | - Dust accumulation (varies with environment)
                |                  | - Thermal cycling (5% per 1000 cycles)
Battery Storage | Peak/Night power | - Temperature effects on capacity
                |                  | - Cycle aging (depth-dependent)
                |                  | - Calendar aging (2.5%/year)
                |                  | - Self-discharge (temp-dependent)
KRUSTY Reactor | Backup/Base load | - Fuel burnup (0.5%/year)
                |                  | - Thermoelectric degradation (1%/year)
                |                  | - Material creep (temp-dependent)

Components include:

1. Solar Power System:
   - Individual panel physics with realistic degradation
   - Single/dual-axis tracking options
   | Environmental effects (dust storms, temperature)
   | Panel cleaning and maintenance

2. Battery System:
   - Multiple chemistry support (Li-ion, LFP, etc.)
   - Temperature-dependent performance
   - Sophisticated aging models
   - Protection systems

3. KRUSTY Nuclear:
   - Startup/shutdown sequences
   - Thermal management
   - Multiple degradation mechanisms
   - Emergency mode operation

4. Power Distribution:
   - AC/DC transmission with losses
   - Multiple voltage buses
   - Load prioritization
   - Fault detection and isolation

5. Environmental Integration:
   - Mars day/night cycle
   - Seasonal variations
   - Dust storm effects
   - Temperature extremes

The system features:
- Comprehensive fault detection and protection
- Priority-based load shedding
- Power quality monitoring
- Thermal management for all components
- Realistic degradation modeling
- Emergency mode transitions

3.5 System Failures & Repairs

Failure    Effect on System    Probability Model
Pump Failure    Stops CO₂ intake     5% per week
Catalyst Degradation    Reduces Sabatier efficiency     0.5% per day
Power Loss    Stops all processing    Based on dust storms & solar
Storage Tank Leak    Gradual loss of stored resources     1% per month

    •    Failures are probabilistic, not deterministic.
    •    Users can override failures manually or define repair times.

4. User Experience & UI/UX

4.1 Dash-Based Dashboard Design

The interactive dashboard will include:
    1.    Live Tank Levels (O₂, CH₄, H₂, CO₂) over time.
    2.    Adjustable Time Acceleration (slider from 1 sec = 1 hr to 1 sec = 1 yr).
    3.    Failure Injection Panel (dropdown to inject issues + slider for repair time).
    4.    KRUSTY Reactor Toggle (to deploy emergency power).
    5.    System Status Indicators (showing active failures).

4.2 User Flow
    1.    User visits the Flask web app.
    2.    Starts the ISRU simulation (default or custom conditions).
    3.    Observes tank levels & system performance.
    4.    Injects a failure (e.g., pump failure).
    5.    Defines repair time and watches the system recover.
    6.    Deploys a KRUSTY reactor if power issues arise.
    7.    Adjusts time acceleration to observe long-term effects.

5. Development Timeline

Phase    Tasks    Duration
Phase 1: Simulation Engine    Implement ISRU chemical processes & probabilistic failures    2 weeks
Phase 2: Flask Backend    API for system control & logging    1 week
Phase 3: Dash-Based UI    Build front-end dashboard with tank levels, power system    2 weeks
Phase 4: KRUSTY Reactor & Time Control    Implement hybrid power system & time acceleration    1 week
Phase 5: Hosting & Testing    Deploy Flask app on EC2, bug fixes    1 week

6. Success Criteria
    •    Realistic ISRU simulation with probabilistic failures.
    •    Hybrid power system (Solar + Battery + KRUSTY).
    •    User-controllable overrides (failure injection, repair times, KRUSTY reactor).
    •    Adjustable time progression (1 sec = 1 hr to 1 sec = 1 yr).
    •    Minimalist Dash-based dashboard with clear visualizations.
    •    Open-source deployment on EC2.