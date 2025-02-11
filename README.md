# PyISRU: Martian ISRU Plant Simulation

A high-fidelity simulation of a Martian In-Situ Resource Utilization (ISRU) plant, implementing detailed chemical and physical models of the Sabatier and electrolysis processes.

## Features

- Full chemical reaction network modeling
- Real gas behavior and phase transitions
- Detailed power system simulation (Solar + Battery + KRUSTY)
- Probabilistic component degradation
- Interactive web dashboard

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/py_isru.git
cd py_isru
```

2. Create a virtual environment (optional but recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

1. Start the simulation server:
```bash
python app.py
```

2. Open your browser and navigate to `http://localhost:8050`

## Components

- `lib/thermodynamics.py`: Core thermodynamic calculations
- `lib/reactor.py`: Base reactor class and common functionality
- `lib/sabatier_reactor.py`: Sabatier reaction modeling
- `lib/electrolysis_reactor.py`: Water electrolysis modeling
- `lib/storage_tank.py`: Gas/liquid storage with phase behavior
- `lib/power_system.py`: Power generation and storage
- `lib/isru_plant.py`: Main plant orchestration

## Development

1. Install development dependencies:
```bash
pip install -r requirements-dev.txt
```

2. Run tests:
```bash
pytest
```

3. Type checking:
```bash
mypy py_isru
```

4. Linting:
```bash
pylint py_isru
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

MIT License - see LICENSE file for details

# Refferences
[Carbon Dioxide Methanation: Design of a Fully Integrated Plant](https://pubs.acs.org/doi/10.1021/acs.energyfuels.0c00580)

[Mars InSitu Resource Utilization: A Review](https://www.sciencedirect.com/science/article/abs/pii/S0032063319301618#!)

![Plant Diagram](plant_diagram.png)

## Open source Python package for In-Situ Resource Utilization research.

### Modeling of reaction systems with applications in fuel production, environmental control, life support, power generation, and structural materials production. 

## Fuel Production
### Sabitier/RWGS Reactor
### Water Electrolysis

## Enviromental Control and Life Support Systems (ECLSS)
### Atmosphereic Gas Production, Scrubbing, and Storage
### Water Systems
### Food Production

## Power Generation
### Nuclear
### Solar
### Geothermal
### Wind

## Structural Materials Production
### Steel
### Concrete
### Polymers

## Chemical Utilities
### Equation Balencing
### Stoichiometry
### Periodic Table

## Physical Utilities
### Thermodynamics
### Material Properties
