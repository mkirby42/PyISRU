from dash import html, dcc
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

def format_value(value: float, unit: str, precision: int = 2) -> str:
    return f"{value:.{precision}f} {unit}"

def create_key_metrics_panel(data_provider):
    status = data_provider.plant.get_status_report()
    
    # Create production rate gauge figures
    ch4_gauge = go.Figure(go.Indicator(
        mode="gauge+number",
        value=data_provider.production_rates['CH4'].values[-1] if data_provider.production_rates['CH4'].values else 0,
        title={'text': "CH4 Production Rate", 'font': {'color': 'white', 'size': 16}},
        domain={'x': [0, 1], 'y': [0, 1]},
        gauge={'axis': {'range': [0, 0.1]}, 'bar': {'color': "lightgreen"}},
        number={'suffix': " mol/s"}
    ))
    
    o2_gauge = go.Figure(go.Indicator(
        mode="gauge+number",
        value=data_provider.production_rates['O2'].values[-1] if data_provider.production_rates['O2'].values else 0,
        title={'text': "O2 Production Rate", 'font': {'color': 'white', 'size': 16}},
        domain={'x': [0, 1], 'y': [0, 1]},
        gauge={'axis': {'range': [0, 0.1]}, 'bar': {'color': "lightblue"}},
        number={'suffix': " mol/s"}
    ))
    
    # Style the gauges
    for gauge in [ch4_gauge, o2_gauge]:
        gauge.update_layout(
            height=200,
            margin=dict(l=10, r=10, t=50, b=50),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font={'color': 'white'}
        )

    return dbc.Card([
        dbc.CardHeader("Key Metrics"),
        dbc.CardBody([
            dbc.Row([
                dbc.Col(dcc.Graph(figure=ch4_gauge), width=6),
                dbc.Col(dcc.Graph(figure=o2_gauge), width=6),
            ]),
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.H6("Total Production"),
                        html.P([
                            html.Span("CH4: ", className="text-muted"),
                            format_value(status['total_CH4_produced_mol'], "mol"),
                        ]),
                        html.P([
                            html.Span("O2: ", className="text-muted"),
                            format_value(status['total_O2_produced_mol'], "mol"),
                        ]),
                    ])
                ], width=4),
                dbc.Col([
                    html.Div([
                        html.H6("Power"),
                        html.P([
                            html.Span("Available: ", className="text-muted"),
                            format_value(status['power_systems']['solar']['output_W'], "W"),
                        ]),
                        html.P([
                            html.Span("Consumed: ", className="text-muted"),
                            format_value(status['total_energy_consumed_J'] / status['uptime_s'] if status['uptime_s'] != 0 else 0, "W"),
                        ]),
                    ])
                ], width=4),
                dbc.Col([
                    html.Div([
                        html.H6("Status"),
                        html.P([
                            html.Span("Plant: ", className="text-muted"),
                            html.Span(status['plant_status'], 
                                    className=f"badge bg-{'success' if status['plant_status']=='RUNNING' else 'warning'}")
                        ]),
                        html.P([
                            html.Span("Uptime: ", className="text-muted"),
                            format_value(status['uptime_s'] / 3600 if status['uptime_s'] != 0 else 0, "hours", 1),
                        ]),
                    ])
                ], width=4),
            ]),
        ])
    ], className="mb-4") 