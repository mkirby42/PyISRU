from dash import Dash, html, dcc, Input, Output, callback_context
from flask import Flask
import dash_bootstrap_components as dbc
from py_isru.dashboard.components.key_metrics import create_key_metrics_panel
from py_isru.dashboard.data_provider import DataProvider
from py_isru.lib.isru_plant import (ISRUPlant, PlantSpecification, ResourceType, 
    SabatierSpecification, ElectrolysisSpecification, TankSpecification, 
    SolarArraySpecification, BatterySpecification, KrustySpecification, PlantStatus)
from py_isru.lib.power_system import (SolarPanelSpecification, TrackerSpecification, TrackingType)
from py_isru.dashboard.components.tank_metrics import create_tank_metrics_panel
from py_isru.dashboard.components.control_panel import create_control_panel
import logging
from py_isru.lib.thermodynamics import ReactionKinetics

logging.basicConfig(level=logging.INFO)  # Set to INFO to suppress debug messages

server = Flask(__name__)
app = Dash(
    __name__,
    server=server,
    external_stylesheets=[dbc.themes.DARKLY],
    update_title=None
)

# Create a mock plant specification
mock_spec = PlantSpecification(
    # Sabatier Reactor Spec
    sabatier_spec=SabatierSpecification(
        volume_m3=0.5,  # 500L reactor
        max_temperature_K=1000.0,  # Max safe temp
        max_pressure_Pa=2e6,  # 20 bar max
        thermal_mass_J_per_K=5e4,  # Steel reactor vessel
        heat_loss_coefficient_W_per_m2K=10.0,
        surface_area_m2=3.0,
        catalyst_type="Ru/Al2O3",
        catalyst_loading_kg_per_m3=50.0,
        catalyst_surface_area_m2_per_kg=100.0,
        catalyst_porosity=0.4,
    ),

    # Electrolysis Reactor Spec
    electrolysis_spec=ElectrolysisSpecification(
        volume_m3=0.2,  # 200L cell stack
        max_temperature_K=360.0,  # PEM typical max
        max_pressure_Pa=3e6,  # 30 bar max
        thermal_mass_J_per_K=2e4,
        heat_loss_coefficient_W_per_m2K=15.0,
        surface_area_m2=2.0,
        membrane_type="Nafion",
        membrane_thickness_m=180e-6,  # 180 microns
        membrane_conductivity_S_per_m=10.0,
        electrode_area_m2=1.0,
        max_current_density_A_per_m2=2000.0,  # 2 A/cm²
        max_power_W=5000.0,  # 5 kW stack
        kinetics=ReactionKinetics(
            rate_constant_forward_1_s_inv=1.0,
            activation_energy_J_per_mol=0.0,
            reaction_order={"H2O": 1}
        )
    ),

    # Storage Tanks
    tank_specs={
        ResourceType.CO2: TankSpecification(
            volume_m3=2.0,
            max_pressure_Pa=2e6,  # 20 bar
            max_temperature_K=400.0,
            material="Stainless Steel 316",
            wall_thickness_m=0.01,  # 10mm wall
            thermal_conductivity_W_per_mK=16.3,  # SS316
            safety_factor=2.0
        ),
        ResourceType.H2: TankSpecification(
            volume_m3=1.0,
            max_pressure_Pa=3e6,  # 30 bar (H2 needs higher pressure)
            max_temperature_K=400.0,
            material="Inconel 718",  # Better for H2 embrittlement
            wall_thickness_m=0.015,  # 15mm for higher pressure
            thermal_conductivity_W_per_mK=11.4,
            safety_factor=2.5  # Higher for H2
        ),
        ResourceType.O2: TankSpecification(
            volume_m3=1.0,
            max_pressure_Pa=3e6,  # 30 bar
            max_temperature_K=400.0,
            material="Stainless Steel 316",
            wall_thickness_m=0.012,  # 12mm
            thermal_conductivity_W_per_mK=16.3,
            safety_factor=2.0
        ),
        ResourceType.CH4: TankSpecification(
            volume_m3=2.0,
            max_pressure_Pa=2e6,  # 20 bar
            max_temperature_K=400.0,
            material="Stainless Steel 316",
            wall_thickness_m=0.01,  # 10mm
            thermal_conductivity_W_per_mK=16.3,
            safety_factor=2.0
        ),
        ResourceType.H2O: TankSpecification(
            volume_m3=1.0,
            max_pressure_Pa=1e6,  # 10 bar (lower for water)
            max_temperature_K=400.0,
            material="Stainless Steel 316",
            wall_thickness_m=0.008,  # 8mm (lower pressure)
            thermal_conductivity_W_per_mK=16.3,
            safety_factor=1.8
        ),
    },

    # Solar Array Spec
    solar_spec=SolarArraySpecification(
        n_panels=20,
        panel_spec=SolarPanelSpecification(
            area=2.0,  # 2m² per panel
            base_efficiency=0.3,  # 30% efficient
            max_temp=85.0,  # °C
            min_temp=-125.0,  # °C
            mass=10.0,
            dust_tolerance=0.1
        ),
        tracker_spec=TrackerSpecification(
            type=TrackingType.DUAL_AXIS,
            power_consumption=10.0,
            max_slew_rate=5.0,
        )
    ),

    # Battery Spec
    battery_spec=BatterySpecification(
        capacity_wh=50000.0,  # 50 kWh
        max_power=10000.0  # 10 kW charge/discharge
    ),

    # KRUSTY Nuclear Reactor Spec
    krusty_spec=KrustySpecification(
        nominal_power=10000.0,  # 10 kW
        max_power=12000.0,  # 12 kW
        startup_time=3600.0,  # 1 hour
        cooldown_time=7200.0,  # 2 hours
        burn_in_time=86400.0  # 24 hours
    ),

    # Control Parameters
    min_tank_levels_mol={
        resource: 50.0 for resource in ResourceType
    },
    max_tank_levels_mol={
        resource: 1000.0 for resource in ResourceType
    },
    emergency_power_threshold_W=1000.0,  # 1 kW minimum
    maintenance_interval_s=604800.0  # 1 week
)

# Create plant with mock spec
plant = ISRUPlant(mock_spec)

# Add initial resources to tanks
initial_resources = {
    ResourceType.CO2: 500.0,  # mol
    ResourceType.H2O: 500.0,  # mol
    ResourceType.H2: 100.0,   # mol
    ResourceType.O2: 0.0,
    ResourceType.CH4: 0.0
}

for resource_type, amount in initial_resources.items():
    plant.tanks[resource_type].add_resource(
        amount,
        298.15  # Room temperature (K)
    )

data_provider = DataProvider(plant)

app.layout = dbc.Container([
    dcc.Interval(
        id='interval-component',
        interval=1000,
        n_intervals=0
    ),
    dbc.Row([
        dbc.Col(html.H1("ISRU Plant Dashboard"), width=12)
    ]),
    dbc.Row([
        dbc.Col(
            html.Div(
                create_control_panel(data_provider),
                id="control-panel"
            ),
            width=12
        )
    ]),
    dbc.Row([
        dbc.Col(
            html.Div(
                create_key_metrics_panel(data_provider),
                id="key-metrics-panel"
            ),
            width=12
        )
    ]),
    dbc.Row([
        dbc.Col(
            html.Div(
                create_tank_metrics_panel(data_provider),
                id="tank-metrics-panel"
            ),
            width=12
        )
    ]),
], fluid=True, className="dbc")

# Update callbacks to include control panel and handle button clicks
@app.callback(
    [Output("control-panel", "children"),
     Output("key-metrics-panel", "children"),
     Output("tank-metrics-panel", "children")],
    [Input("interval-component", "n_intervals"),
     Input("start-button", "n_clicks"),
     Input("stop-button", "n_clicks")]
)
def update_dashboard(n_intervals, start_clicks, stop_clicks):
    ctx = callback_context
    if ctx.triggered:
        trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
        if trigger_id == "start-button":
            data_provider.plant.start()
        elif trigger_id == "stop-button":
            data_provider.plant.shutdown()
    
    data_provider.update()
    return [
        create_control_panel(data_provider),
        create_key_metrics_panel(data_provider),
        create_tank_metrics_panel(data_provider)
    ]

if __name__ == '__main__':
    app.run_server(debug=True) 