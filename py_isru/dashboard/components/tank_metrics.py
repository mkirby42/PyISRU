from dash import html, dcc
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from typing import Dict
from py_isru.lib.isru_plant import ResourceType  # Add this import

TANK_COLORS = {
    'CO2': '#ff9999',  # Red
    'H2': '#99ff99',   # Green
    'O2': '#9999ff',   # Blue
    'CH4': '#ffff99',  # Yellow
    'H2O': '#99ffff'   # Cyan
}

def create_tank_gauge(resource: str, current_level: float, max_level: float) -> go.Figure:
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=current_level,
        title={'text': f"{resource} Tank", 'font': {'color': 'white', 'size': 16}},
        domain={'x': [0, 1], 'y': [0, 1]},
        gauge={
            'axis': {'range': [0, max_level]},
            'bar': {'color': TANK_COLORS[resource]},
            'steps': [
                {'range': [0, max_level * 0.2], 'color': 'rgba(255, 0, 0, 0.2)'},
                {'range': [max_level * 0.8, max_level], 'color': 'rgba(0, 255, 0, 0.2)'}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': max_level * 0.2
            }
        },
        number={'suffix': " mol"}
    ))
    
    fig.update_layout(
        height=200,
        margin=dict(l=10, r=10, t=50, b=50),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={'color': 'white'}
    )
    
    return fig

def create_tank_metrics_panel(data_provider):
    status = data_provider.plant.get_status_report()
    tank_levels = status['tank_levels_mol']
    
    # Create a mapping from string names to ResourceType enums
    resource_map = {res.name: res for res in ResourceType}
    
    # Get max levels from plant specification
    max_levels = {
        resource: data_provider.plant.spec.max_tank_levels_mol[resource_map[resource]] 
        for resource in tank_levels.keys()
    }
    
    tank_gauges = [
        dbc.Col(
            dcc.Graph(
                figure=create_tank_gauge(resource, level, max_levels[resource]),
                config={'displayModeBar': False}
            ),
            width=6,  # Change to 6 for 2 per row, or better yet:
            xs=12, sm=6, md=4,  # Responsive: 1 column on mobile, 2 on tablet, 3 on desktop
            className="mb-4"
        )
        for resource, level in tank_levels.items()
    ]

    # Wrap in rows of 3
    tank_rows = [
        dbc.Row(tank_gauges[i:i+3])
        for i in range(0, len(tank_gauges), 3)
    ]
    
    return dbc.Card([
        dbc.CardHeader([
            html.H5("Resource Tanks", className="mb-0"),
            html.Small("Tank levels and status", className="text-muted")
        ]),
        dbc.CardBody([
            *tank_rows,  # Spread the rows directly into CardBody
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.H6("Tank Temperatures"),
                        *[
                            html.P([
                                html.Span(f"{resource}: ", className="text-muted"),
                                f"{data_provider.plant.tanks[resource_map[resource]].state.temperature_K:.1f} K"
                            ])
                            for resource in tank_levels.keys()
                        ]
                    ])
                ], width=6),
                dbc.Col([
                    html.Div([
                        html.H6("Tank Pressures"),
                        *[
                            html.P([
                                html.Span(f"{resource}: ", className="text-muted"),
                                f"{data_provider.plant.tanks[resource_map[resource]].state.pressure_Pa/1e5:.2f} bar"  # Changed to bar
                            ])
                            for resource in tank_levels.keys()
                        ]
                    ])
                ], width=6)
            ])
        ])
    ], className="mb-4") 