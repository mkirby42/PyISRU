# ISRU Plant Dashboard Design

Real-time monitoring dashboard for the Martian ISRU plant using Plotly.

## Key Metrics Panel
- Real-time production rates (CH4, O2 mol/s)
- Cumulative production (CH4, O2 mol) 
- Current power consumption/availability (W)
- Plant operational status indicator
- Uptime counter

## Resource Tanks Panel
- Tank level gauges:
  - CO2 (mol)
  - H2 (mol) 
  - O2 (mol)
  - CH4 (mol)
  - H2O (mol)
- Temperature indicators (K)
- Pressure indicators (Pa)

## Power Systems Panel
- Solar array:
  - Output over time (W)
  - Dust coverage (%)
- Battery:
  - State of charge (%)
  - Input/output power (W)
- KRUSTY reactor:
  - Status
  - Output power (W)
- Total power graph:
  - Available vs consumed (W)

## Reactor Status Panel
- Sabatier reactor:
  - Temperature plot (K)
  - Operational status
  - Catalyst degradation (%)
  - Reaction rates (mol/s)
- Electrolysis reactor:
  - Temperature plot (K) 
  - Operational status
  - Membrane degradation (%)
  - Reaction rates (mol/s)

## Alert/Log Panel
- Status change history
- Active fault conditions
- Warning indicators
- System messages

## Technical Implementation
- Plotly for interactive visualizations
- Dark theme for control room visibility
- Websocket-based real-time updates
- Responsive grid layout
- Collapsible/expandable sections

## Data Sources
All metrics available via ISRUPlant.get_status_report():
- Plant status
- Fault conditions
- Production totals
- Tank levels
- Power system states
- Reactor conditions

## Update Frequency
- Key metrics: 1 Hz
- Plots: 0.2 Hz
- Status indicators: On change
- Logs: On event 