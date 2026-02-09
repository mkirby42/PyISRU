"""
Fleet Simulator Dash App Integration
Handles the Dash app for fleet simulation within the Flask application
"""

from dash import Dash, html, dcc, Input, Output, dash_table
import plotly.graph_objs as go
import pandas as pd

# Import the simulation logic from fleet_size
from fleet_size import simulate_mars_transport

def create_fleet_dash_app(flask_app):
    """
    Create and configure the Fleet Simulator Dash app
    
    Args:
        flask_app: The Flask application instance
        
    Returns:
        Dash app instance
    """
    
    # Create Dash app integrated with Flask
    dash_app = Dash(__name__, server=flask_app, url_base_pathname='/fleet-simulator/')
    dash_app.title = "Mars Transport Simulator"
    
    # Define the complete layout (copied exactly from fleet_size.py with back button added)
    dash_app.layout = html.Div([
        # Header with back button
        html.Div([
            html.Div([
                html.A("← Back to Blog", href="/", 
                       style={
                           "textDecoration": "none", 
                           "color": "#007bff", 
                           "fontSize": "16px",
                           "fontWeight": "500",
                           "marginBottom": "20px",
                           "display": "inline-block"
                       })
            ]),
            html.H1("Mars Settlement Transport Simulator", 
                    style={
                        "textAlign": "center", 
                        "color": "#2c3e50", 
                        "marginBottom": "30px",
                        "fontFamily": "system-ui, -apple-system, sans-serif",
                        "fontWeight": "300",
                        "fontSize": "2.5rem"
                    })
        ], style={
            "backgroundColor": "#ffffff",
            "padding": "20px 20px 0 20px",
            "borderBottom": "1px solid #e9ecef",
            "marginBottom": "0"
        }),
        
        # Main content
        html.Div([
            # Controls Panel
            html.Div([
                html.H3("Mission Parameters", 
                       style={
                           "color": "#34495e", 
                           "marginBottom": "25px",
                           "fontFamily": "system-ui, -apple-system, sans-serif",
                           "fontWeight": "400",
                           "fontSize": "1.3rem"
                       }),
                
                # Ship Capacity Section
                html.Div([
                    html.H4("Ship Capacity", style={"color": "#7f8c8d", "fontSize": "1rem", "marginBottom": "15px"}),
                    
                    html.Div([
                        html.Label("People per Ship", style={"fontWeight": "500", "color": "#2c3e50"}),
                        html.P("Crew capacity for each crew-class Starship", 
                               style={"fontSize": "12px", "color": "#95a5a6", "margin": "5px 0 10px 0"}),
                        dcc.Slider(10, 200, 10, value=100, id="n_people_per_ship",
                                  marks={i: str(i) for i in range(10, 201, 50)},
                                  tooltip={"placement": "bottom", "always_visible": False})
                    ], style={"marginBottom": "20px"}),
                    
                    html.Div([
                        html.Label("Cargo Mass per Ship (tons)", style={"fontWeight": "500", "color": "#2c3e50"}),
                        html.P("Cargo capacity for each cargo-class Starship", 
                               style={"fontSize": "12px", "color": "#95a5a6", "margin": "5px 0 10px 0"}),
                        dcc.Slider(10, 200, 10, value=100, id="cargo_mass_per_ship",
                                  marks={i: str(i) for i in range(10, 201, 50)},
                                  tooltip={"placement": "bottom", "always_visible": False})
                    ], style={"marginBottom": "25px"}),
                ]),
                
                # Manufacturing Section
                html.Div([
                    html.H4("Manufacturing", style={"color": "#7f8c8d", "fontSize": "1rem", "marginBottom": "15px"}),
                    
                    html.Div([
                        html.Label("Crew Ship Build Time (months)", style={"fontWeight": "500", "color": "#2c3e50"}),
                        html.P("Time to build each crew ship from start to finish", 
                               style={"fontSize": "12px", "color": "#95a5a6", "margin": "5px 0 10px 0"}),
                        dcc.Slider(1, 12, 1, value=6, id="crew_build_time_months",
                                  marks={i: str(i) for i in range(1, 13, 3)},
                                  tooltip={"placement": "bottom", "always_visible": False})
                    ], style={"marginBottom": "20px"}),
                    
                    html.Div([
                        html.Label("Cargo Ship Build Time (months)", style={"fontWeight": "500", "color": "#2c3e50"}),
                        html.P("Time to build each cargo ship from start to finish", 
                               style={"fontSize": "12px", "color": "#95a5a6", "margin": "5px 0 10px 0"}),
                        dcc.Slider(1, 12, 1, value=4, id="cargo_build_time_months",
                                  marks={i: str(i) for i in range(1, 13, 3)},
                                  tooltip={"placement": "bottom", "always_visible": False})
                    ], style={"marginBottom": "20px"}),
                    
                    html.Div([
                        html.Label("Tanker Build Time (months)", style={"fontWeight": "500", "color": "#2c3e50"}),
                        html.P("Time to build each tanker ship from start to finish", 
                               style={"fontSize": "12px", "color": "#95a5a6", "margin": "5px 0 10px 0"}),
                        dcc.Slider(1, 12, 1, value=3, id="tanker_build_time_months",
                                  marks={i: str(i) for i in range(1, 13, 3)},
                                  tooltip={"placement": "bottom", "always_visible": False})
                    ], style={"marginBottom": "20px"}),
                    
                    html.Div([
                        html.Label("Crew Line Capacity", style={"fontWeight": "500", "color": "#2c3e50"}),
                        html.P("Max crew ships building simultaneously. Production rate emerges from capacity × build time.", 
                               style={"fontSize": "12px", "color": "#95a5a6", "margin": "5px 0 10px 0"}),
                        dcc.Slider(1, 300, 5, value=8, id="crew_line_capacity",
                                  marks={i: str(i) for i in range(1, 301, 50)},
                                  tooltip={"placement": "bottom", "always_visible": False})
                    ], style={"marginBottom": "20px"}),
                    
                    html.Div([
                        html.Label("Cargo Line Capacity", style={"fontWeight": "500", "color": "#2c3e50"}),
                        html.P("Max cargo ships building simultaneously", 
                               style={"fontSize": "12px", "color": "#95a5a6", "margin": "5px 0 10px 0"}),
                        dcc.Slider(1, 500, 5, value=15, id="cargo_line_capacity",
                                  marks={i: str(i) for i in range(1, 501, 100)},
                                  tooltip={"placement": "bottom", "always_visible": False})
                    ], style={"marginBottom": "20px"}),
                    
                    html.Div([
                        html.Label("Tanker Line Capacity", style={"fontWeight": "500", "color": "#2c3e50"}),
                        html.P("Max tanker ships building simultaneously", 
                               style={"fontSize": "12px", "color": "#95a5a6", "margin": "5px 0 10px 0"}),
                        dcc.Slider(1, 500, 5, value=20, id="tanker_line_capacity",
                                  marks={i: str(i) for i in range(1, 501, 100)},
                                  tooltip={"placement": "bottom", "always_visible": False})
                    ], style={"marginBottom": "25px"}),
                ]),
                
                # Operations Section
                html.Div([
                    html.H4("Operations", style={"color": "#7f8c8d", "fontSize": "1rem", "marginBottom": "15px"}),
                    
                    html.Div([
                        html.Label("Tanker Turnaround (days)", style={"fontWeight": "500", "color": "#2c3e50"}),
                        html.P("Days between flights for each tanker", 
                               style={"fontSize": "12px", "color": "#95a5a6", "margin": "5px 0 10px 0"}),
                        dcc.Slider(1, 30, 1, value=7, id="tanker_turnaround_days",
                                  marks={i: str(i) for i in range(1, 31, 7)},
                                  tooltip={"placement": "bottom", "always_visible": False})
                    ], style={"marginBottom": "20px"}),
                    
                    html.Div([
                        html.Label("Fuel per Tanker (tons)", style={"fontWeight": "500", "color": "#2c3e50"}),
                        html.P("Fuel load carried by each tanker to LEO depot", 
                               style={"fontSize": "12px", "color": "#95a5a6", "margin": "5px 0 10px 0"}),
                        dcc.Slider(10, 500, 10, value=100, id="fuel_per_tanker",
                                  marks={i: str(i) for i in range(10, 501, 100)},
                                  tooltip={"placement": "bottom", "always_visible": False})
                    ], style={"marginBottom": "20px"}),
                    
                    html.Div([
                        html.Label("Fuel per Mars Mission (tons)", style={"fontWeight": "500", "color": "#2c3e50"}),
                        html.P("Fuel needed for complete round trip", 
                               style={"fontSize": "12px", "color": "#95a5a6", "margin": "5px 0 10px 0"}),
                        dcc.Slider(100, 2000, 100, value=1600, id="fuel_per_mars_mission",
                                  marks={i: str(i) for i in range(100, 2001, 500)},
                                  tooltip={"placement": "bottom", "always_visible": False})
                    ], style={"marginBottom": "25px"}),
                ]),

                # Methane accounting controls
                html.Div([
                    html.H4("Methane Accounting", style={"color": "#7f8c8d", "fontSize": "1rem", "marginBottom": "15px"}),
                    html.Label("O/F Ratio (LOX/CH4)", style={"fontWeight": "500", "color": "#2c3e50"}),
                    dcc.Slider(2.5, 4.5, 0.1, value=3.75, id="o_f_ratio",
                              marks={i: str(i) for i in [2.5, 3.0, 3.6, 3.75, 4.0, 4.5]},
                              tooltip={"placement": "bottom", "always_visible": False}),
                    html.Div(style={"height": "10px"}),
                    html.Label("Methane Units", style={"fontWeight": "500", "color": "#2c3e50"}),
                    dcc.Dropdown(id="methane_units",
                                 options=[
                                     {"label": "MMcf", "value": "mmcf"},
                                     {"label": "tons", "value": "tons"},
                                     {"label": "USD (millions)", "value": "usd"}
                                 ],
                                 value="mmcf",
                                 clearable=False,
                                 style={"marginTop": "5px", "marginBottom": "10px"}),
                    html.Label("Henry Hub Price ($/MMBtu)", style={"fontWeight": "500", "color": "#2c3e50"}),
                    dcc.Slider(1.0, 10.0, 0.1, value=2.69, id="methane_price_mmbtu",
                              marks={i: str(i) for i in range(1, 11, 1)},
                              tooltip={"placement": "bottom", "always_visible": False}),
                    html.Div(style={"height": "10px"}),
                    html.Label("Tanker Ascent CH4 per launch (tons)", style={"fontWeight": "500", "color": "#2c3e50"}),
                    dcc.Slider(0, 2000, 10, value=1030, id="tanker_ascent_ch4_tons",
                              marks={i: str(i) for i in [0, 500, 1000, 1500, 2000]},
                              tooltip={"placement": "bottom", "always_visible": False}),
                    html.Div(style={"height": "10px"}),
                    html.Label("Crew Ascent CH4 per launch (tons)", style={"fontWeight": "500", "color": "#2c3e50"}),
                    dcc.Slider(0, 2000, 10, value=1030, id="crew_ascent_ch4_tons",
                              marks={i: str(i) for i in [0, 500, 1000, 1500, 2000]},
                              tooltip={"placement": "bottom", "always_visible": False}),
                    html.Div(style={"height": "10px"}),
                    html.Label("Cargo Ascent CH4 per launch (tons)", style={"fontWeight": "500", "color": "#2c3e50"}),
                    dcc.Slider(0, 2000, 10, value=1030, id="cargo_ascent_ch4_tons",
                              marks={i: str(i) for i in [0, 500, 1000, 1500, 2000]},
                              tooltip={"placement": "bottom", "always_visible": False}),
                ]),

                # LOX controls
                html.Div([
                    html.H4("LOX Accounting", style={"color": "#7f8c8d", "fontSize": "1rem", "marginBottom": "15px"}),
                    html.Label("LOX Units", style={"fontWeight": "500", "color": "#2c3e50"}),
                    dcc.Dropdown(id="lox_units",
                                 options=[
                                     {"label": "tons", "value": "tons"},
                                     {"label": "USD (millions)", "value": "usd"}
                                 ],
                                 value="tons",
                                 clearable=False,
                                 style={"marginTop": "5px", "marginBottom": "10px"}),
                    html.Label("LOX Price ($/ton)", style={"fontWeight": "500", "color": "#2c3e50"}),
                    dcc.Slider(0, 2000, 50, value=500, id="lox_price_per_ton",
                              marks={i: str(i) for i in range(0, 2001, 500)},
                              tooltip={"placement": "bottom", "always_visible": False}),
                ]),
                
                # Lifespan Section
                html.Div([
                    html.H4("Ship Lifespan", style={"color": "#7f8c8d", "fontSize": "1rem", "marginBottom": "15px"}),
                    
                    html.Div([
                        html.Label("Crew Ship Lifespan (missions)", style={"fontWeight": "500", "color": "#2c3e50"}),
                        html.P("Mars round trips before retirement", 
                               style={"fontSize": "12px", "color": "#95a5a6", "margin": "5px 0 10px 0"}),
                        dcc.Slider(1, 20, 1, value=10, id="crew_ship_lifespan",
                                  marks={i: str(i) for i in range(1, 21, 5)},
                                  tooltip={"placement": "bottom", "always_visible": False})
                    ], style={"marginBottom": "20px"}),
                    
                    html.Div([
                        html.Label("Cargo Ship Lifespan (missions)", style={"fontWeight": "500", "color": "#2c3e50"}),
                        html.P("Mars round trips before retirement", 
                               style={"fontSize": "12px", "color": "#95a5a6", "margin": "5px 0 10px 0"}),
                        dcc.Slider(1, 20, 1, value=10, id="cargo_ship_lifespan",
                                  marks={i: str(i) for i in range(1, 21, 5)},
                                  tooltip={"placement": "bottom", "always_visible": False})
                    ], style={"marginBottom": "20px"}),
                    
                    html.Div([
                        html.Label("Tanker Lifespan (missions)", style={"fontWeight": "500", "color": "#2c3e50"}),
                        html.P("LEO fuel runs before retirement", 
                               style={"fontSize": "12px", "color": "#95a5a6", "margin": "5px 0 10px 0"}),
                        dcc.Slider(2, 50, 2, value=20, id="tanker_lifespan",
                                  marks={i: str(i) for i in range(2, 51, 12)},
                                  tooltip={"placement": "bottom", "always_visible": False})
                    ], style={"marginBottom": "20px"}),
                ])
                
            ], style={
                "flex": "0 0 300px",  # Fixed width for params
                "padding": "25px",
                "backgroundColor": "#f8f9fa",
                "borderRadius": "8px",
                "margin": "10px",
                "boxShadow": "0 2px 4px rgba(0,0,0,0.1)",
                "fontFamily": "system-ui, -apple-system, sans-serif"
            }),

            # Right Column: Charts + Table
            html.Div([
                # Charts Panel
                html.Div([
                    dcc.Graph(id="people_graph", style={"marginBottom": "15px"}),
                    dcc.Graph(id="cargo_graph", style={"marginBottom": "15px"}),
                    dcc.Graph(id="fleet_graph", style={"marginBottom": "15px"}),
                    dcc.Graph(id="fuel_depot_graph", style={"marginBottom": "15px"}),
                    dcc.Graph(id="mars_fuel_graph"),
                    dcc.Graph(id="methane_graph"),
                    dcc.Graph(id="lox_graph")
                ], style={
                    "padding": "25px",
                    "backgroundColor": "#ffffff",
                    "borderRadius": "8px",
                    "margin": "10px 10px 20px 10px",
                    "boxShadow": "0 2px 4px rgba(0,0,0,0.1)",
                    "height": "600px",
                    "overflowY": "auto",
                    "overflowX": "hidden"
                }),
                
                # Three Data Tables Panel
                html.Div([
                    # Production Table
                    html.Div([
                        html.H3("Production & Fleet Status (Quarterly)", 
                               style={
                                   "color": "#34495e", 
                                   "marginBottom": "15px",
                                   "fontFamily": "system-ui, -apple-system, sans-serif",
                                   "fontWeight": "400",
                                   "fontSize": "1.1rem"
                               }),
                        dash_table.DataTable(
                            id="production_table",
                            columns=[
                                {"name": "Quarter", "id": "Quarter", "type": "text"},
                                {"name": "Year", "id": "Year", "type": "text"},
                                {"name": "Crew Built", "id": "Crew Built", "type": "numeric"},
                                {"name": "Cargo Built", "id": "Cargo Built", "type": "numeric"},
                                {"name": "Tanker Built", "id": "Tanker Built", "type": "numeric"},
                                {"name": "CH4 Delivered (quarter, t)", "id": "CH4 Delivered (quarter, t)", "type": "text"},
                                {"name": "LOX Delivered (quarter, t)", "id": "LOX Delivered (quarter, t)", "type": "text"},
                                {"name": "CH4 Delivered (cumulative, t)", "id": "CH4 Delivered (cumulative, t)", "type": "text"},
                                {"name": "LOX Delivered (cumulative, t)", "id": "LOX Delivered (cumulative, t)", "type": "text"},
                                {"name": "Crew Fleet", "id": "Crew Fleet", "type": "numeric"},
                                {"name": "Cargo Fleet", "id": "Cargo Fleet", "type": "numeric"},
                                {"name": "Tanker Fleet", "id": "Tanker Fleet", "type": "numeric"},
                                {"name": "Building", "id": "Building", "type": "numeric"},
                                {"name": "Depot Fuel", "id": "Depot Fuel", "type": "text"},
                                {"name": "Depot CH4 (current, t)", "id": "Depot CH4 (current, t)", "type": "text"},
                                {"name": "Depot LOX (current, t)", "id": "Depot LOX (current, t)", "type": "text"}
                            ],
                            data=[],
                            style_table={"height": "300px", "overflowY": "auto", "borderRadius": "6px"},
                            style_cell={"textAlign": "center", "fontSize": "10px", "padding": "4px"},
                            style_header={"backgroundColor": "#3498db", "color": "white", "fontWeight": "600"},
                            style_data_conditional=[
                                {"if": {"row_index": "odd"}, "backgroundColor": "#f8f9fa"},
                                {"if": {"row_index": "even"}, "backgroundColor": "#ffffff"}
                            ]
                        )
                    ], style={"marginBottom": "20px"}),
                    
                    # Operations Table
                    html.Div([
                        html.H3("Launch Operations (Launch Windows)", 
                               style={
                                   "color": "#34495e", 
                                   "marginBottom": "15px",
                                   "fontFamily": "system-ui, -apple-system, sans-serif",
                                   "fontWeight": "400",
                                   "fontSize": "1.1rem"
                               }),
                        dash_table.DataTable(
                            id="operations_table",
                            columns=[
                                {"name": "Window", "id": "Window", "type": "numeric"},
                                {"name": "Year", "id": "Year", "type": "text"},
                                {"name": "Crew Avail", "id": "Crew Avail", "type": "numeric"},
                                {"name": "Cargo Avail", "id": "Cargo Avail", "type": "numeric"},
                                {"name": "Crew Launch", "id": "Crew Launch", "type": "numeric"},
                                {"name": "Cargo Launch", "id": "Cargo Launch", "type": "numeric"},
                                {"name": "Crew Util %", "id": "Crew Util %", "type": "text"},
                                {"name": "Cargo Util %", "id": "Cargo Util %", "type": "text"},
                                {"name": "Limiting Factor", "id": "Limiting Factor", "type": "text"},
                                {"name": "CH4 Used (t)", "id": "CH4 Used (t)", "type": "text"},
                                {"name": "LOX Used (t)", "id": "LOX Used (t)", "type": "text"},
                                {"name": "Depot CH4 (t)", "id": "Depot CH4 (t)", "type": "text"},
                                {"name": "Depot LOX (t)", "id": "Depot LOX (t)", "type": "text"},
                                {"name": "Ships Returning", "id": "Ships Returning", "type": "numeric"}
                            ],
                            data=[],
                            style_table={"height": "300px", "overflowY": "auto", "borderRadius": "6px"},
                            style_cell={"textAlign": "center", "fontSize": "10px", "padding": "4px"},
                            style_header={"backgroundColor": "#e74c3c", "color": "white", "fontWeight": "600"},
                            style_data_conditional=[
                                {"if": {"row_index": "odd"}, "backgroundColor": "#f8f9fa"},
                                {"if": {"row_index": "even"}, "backgroundColor": "#ffffff"}
                            ]
                        )
                    ], style={"marginBottom": "20px"}),
                    
                    # Mars Table
                    html.Div([
                        html.H3("Mars Settlement Status (Quarterly)", 
                               style={
                                   "color": "#34495e", 
                                   "marginBottom": "15px",
                                   "fontFamily": "system-ui, -apple-system, sans-serif",
                                   "fontWeight": "400",
                                   "fontSize": "1.1rem"
                               }),
                        dash_table.DataTable(
                            id="mars_table",
                            columns=[
                                {"name": "Quarter", "id": "Quarter", "type": "text"},
                                {"name": "Year", "id": "Year", "type": "text"},
                                {"name": "People Delivered", "id": "People Delivered", "type": "numeric"},
                                {"name": "Cargo Delivered", "id": "Cargo Delivered", "type": "text"},
                                {"name": "Ships on Mars", "id": "Ships on Mars", "type": "text"},
                                {"name": "Total People", "id": "Total People", "type": "text"},
                                {"name": "Total Cargo", "id": "Total Cargo", "type": "text"},
                                {"name": "Cumulative Fuel Demand", "id": "Cumulative Fuel Demand", "type": "text"}
                            ],
                            data=[],
                            style_table={"height": "300px", "overflowY": "auto", "borderRadius": "6px"},
                            style_cell={"textAlign": "center", "fontSize": "10px", "padding": "4px"},
                            style_header={"backgroundColor": "#f39c12", "color": "white", "fontWeight": "600"},
                            style_data_conditional=[
                                {"if": {"row_index": "odd"}, "backgroundColor": "#f8f9fa"},
                                {"if": {"row_index": "even"}, "backgroundColor": "#ffffff"}
                            ]
                        )
                    ])
                ], style={
                    "padding": "25px",
                    "backgroundColor": "#ffffff",
                    "borderRadius": "8px",
                    "margin": "10px",
                    "boxShadow": "0 2px 4px rgba(0,0,0,0.1)"
                })
            ], style={
                "flex": "1",  # Right column takes remaining space
                "minWidth": "0"  # Allow flex item to shrink to container width
            })
        ], style={
            "padding": "0 20px 20px 20px",
            "backgroundColor": "#f1f3f4",
            "fontFamily": "system-ui, -apple-system, sans-serif",
            "display": "flex",
            "gap": "10px"
        })
    ], style={
        "backgroundColor": "#f1f3f4",
        "minHeight": "100vh",
        "margin": "0",
        "fontFamily": "system-ui, -apple-system, sans-serif"
    })

    # Complete callback with all parameters and charts (copied exactly from fleet_size.py)
    @dash_app.callback(
        [Output("people_graph", "figure"), Output("cargo_graph", "figure"), Output("fleet_graph", "figure"), Output("fuel_depot_graph", "figure"), Output("mars_fuel_graph", "figure"), Output("methane_graph", "figure"), Output("lox_graph", "figure"), Output("production_table", "data"), Output("operations_table", "data"), Output("mars_table", "data")],
        Input("n_people_per_ship", "value"),
        Input("cargo_mass_per_ship", "value"),
        Input("crew_build_time_months", "value"),
        Input("cargo_build_time_months", "value"),
        Input("tanker_build_time_months", "value"),
        Input("crew_line_capacity", "value"),
        Input("cargo_line_capacity", "value"),
        Input("tanker_line_capacity", "value"),
        Input("tanker_turnaround_days", "value"),
        Input("fuel_per_tanker", "value"),
        Input("fuel_per_mars_mission", "value"),
        Input("crew_ship_lifespan", "value"),
        Input("cargo_ship_lifespan", "value"),
        Input("tanker_lifespan", "value"),
        Input("o_f_ratio", "value"),
        Input("methane_units", "value"),
        Input("methane_price_mmbtu", "value"),
        Input("tanker_ascent_ch4_tons", "value"),
        Input("crew_ascent_ch4_tons", "value"),
        Input("cargo_ascent_ch4_tons", "value"),
        Input("lox_units", "value"),
        Input("lox_price_per_ton", "value"),
    )
    def update_graphs(n_people, cargo_mass, crew_build_months, cargo_build_months, tanker_build_months, crew_capacity, cargo_capacity, tanker_capacity, tanker_turnaround_days, fuel_per_tanker, fuel_per_mission, crew_lifespan, cargo_lifespan, tanker_lifespan, o_f_ratio, methane_units, methane_price_mmbtu, tanker_ascent_ch4_tons, crew_ascent_ch4_tons, cargo_ascent_ch4_tons, lox_units, lox_price_per_ton):
        params = {
            "n_people_per_ship": n_people,
            "cargo_mass_per_ship": cargo_mass,
            "crew_build_time_months": crew_build_months,
            "cargo_build_time_months": cargo_build_months,
            "tanker_build_time_months": tanker_build_months,
            "crew_line_capacity": crew_capacity,
            "cargo_line_capacity": cargo_capacity,
            "tanker_line_capacity": tanker_capacity,
            "tanker_turnaround_days": tanker_turnaround_days,
            "fuel_per_tanker": fuel_per_tanker,
            "fuel_per_mars_mission": fuel_per_mission,
            "crew_ship_lifespan": crew_lifespan,
            "cargo_ship_lifespan": cargo_lifespan,
            "tanker_lifespan": tanker_lifespan,
            "o_f_ratio": o_f_ratio,
            "tanker_ascent_ch4_tons": tanker_ascent_ch4_tons,
            "crew_ascent_ch4_tons": crew_ascent_ch4_tons,
            "cargo_ascent_ch4_tons": cargo_ascent_ch4_tons,
        }
        df, production_data, operations_data, mars_data = simulate_mars_transport(params)

        # People chart
        people_fig = go.Figure()
        people_fig.add_trace(go.Scatter(
            x=df["Year"], 
            y=df["People at Mars"],
            name="People at Mars", 
            line=dict(color="#3498db", width=3),
            fill='tozeroy',
            fillcolor='rgba(52, 152, 219, 0.1)'
        ))
        people_fig.update_layout(
            title={
                'text': "People at Mars",
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 18, 'color': '#2c3e50', 'family': 'system-ui, -apple-system, sans-serif'}
            },
            xaxis_title="Year",
            yaxis_title="Cumulative People",
            margin=dict(l=60, r=30, t=60, b=50),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(family='system-ui, -apple-system, sans-serif', color='#2c3e50'),
            xaxis=dict(gridcolor='rgba(0,0,0,0.1)', showgrid=True),
            yaxis=dict(gridcolor='rgba(0,0,0,0.1)', showgrid=True),
            showlegend=False
        )

        # LOX graph (tons or USD millions)
        if lox_units == "tons":
            lox_y1 = df["LOX Withdrawn (tons)"]
            lox_y2 = df["LOX Delivered to Depot (tons)"]
            lox_yaxis = "Cumulative LOX (tons)"
        else:
            lox_y1 = df["LOX Withdrawn (tons)"] * (lox_price_per_ton / 1e6)
            lox_y2 = df["LOX Delivered to Depot (tons)"] * (lox_price_per_ton / 1e6)
            lox_yaxis = "Cumulative LOX Cost (USD, millions)"

        lox_fig = go.Figure()
        lox_fig.add_trace(go.Scatter(x=df["Year"], y=lox_y1, name="LOX Withdrawn (Earth)", line=dict(color="#2980b9", width=3)))
        lox_fig.add_trace(go.Scatter(x=df["Year"], y=lox_y2, name="LOX Delivered to Depot", line=dict(color="#c0392b", width=2, dash='dash')))
        lox_fig.update_layout(
            title={'text': "LOX Withdrawn vs Delivered", 'x': 0.5, 'xanchor': 'center', 'font': {'size': 18, 'color': '#2c3e50', 'family': 'system-ui, -apple-system, sans-serif'}},
            xaxis_title="Year",
            yaxis_title=lox_yaxis,
            margin=dict(l=60, r=30, t=60, b=50),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(family='system-ui, -apple-system, sans-serif', color='#2c3e50'),
            xaxis=dict(gridcolor='rgba(0,0,0,0.1)', showgrid=True),
            yaxis=dict(gridcolor='rgba(0,0,0,0.1)', showgrid=True),
            legend=dict(x=0.02, y=0.98, bgcolor='rgba(255,255,255,0.8)', bordercolor='rgba(0,0,0,0.1)', borderwidth=1, font=dict(size=12))
        )

        # Cargo chart
        cargo_fig = go.Figure()
        cargo_fig.add_trace(go.Scatter(
            x=df["Year"], 
            y=df["Cargo at Mars (tons)"],
            name="Cargo at Mars", 
            line=dict(color="#e74c3c", width=3),
            fill='tozeroy',
            fillcolor='rgba(231, 76, 60, 0.1)'
        ))
        cargo_fig.update_layout(
            title={
                'text': "Cargo at Mars",
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 18, 'color': '#2c3e50', 'family': 'system-ui, -apple-system, sans-serif'}
            },
            xaxis_title="Year",
            yaxis_title="Cumulative Cargo (tons)",
            margin=dict(l=60, r=30, t=60, b=50),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(family='system-ui, -apple-system, sans-serif', color='#2c3e50'),
            xaxis=dict(gridcolor='rgba(0,0,0,0.1)', showgrid=True),
            yaxis=dict(gridcolor='rgba(0,0,0,0.1)', showgrid=True),
            showlegend=False
        )

        # Fleet chart
        fleet_fig = go.Figure()
        fleet_fig.add_trace(go.Scatter(
            x=df["Year"], 
            y=df["Crew Ships Available"],
            name="Crew Ships", 
            line=dict(color="#3498db", width=3)
        ))
        fleet_fig.add_trace(go.Scatter(
            x=df["Year"], 
            y=df["Cargo Ships Available"],
            name="Cargo Ships", 
            line=dict(color="#2ecc71", width=3)
        ))
        fleet_fig.add_trace(go.Scatter(
            x=df["Year"], 
            y=df["Tankers Available"],
            name="Tankers", 
            line=dict(color="#f39c12", width=3)
        ))
        fleet_fig.update_layout(
            title={
                'text': "Available Fleet Size",
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 18, 'color': '#2c3e50', 'family': 'system-ui, -apple-system, sans-serif'}
            },
            xaxis_title="Year",
            yaxis_title="Ships Available on Earth",
            margin=dict(l=60, r=30, t=60, b=50),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(family='system-ui, -apple-system, sans-serif', color='#2c3e50'),
            xaxis=dict(gridcolor='rgba(0,0,0,0.1)', showgrid=True),
            yaxis=dict(gridcolor='rgba(0,0,0,0.1)', showgrid=True),
            legend=dict(
                x=0.02, 
                y=0.98,
                bgcolor='rgba(255,255,255,0.8)',
                bordercolor='rgba(0,0,0,0.1)',
                borderwidth=1,
                font=dict(size=12)
            )
        )

        # LEO Fuel Depot chart
        fuel_fig = go.Figure()
        fuel_fig.add_trace(go.Scatter(
            x=df["Year"], 
            y=df["LEO Fuel Depot"],
            name="LEO Fuel Storage", 
            line=dict(color="#9b59b6", width=3),
            fill='tozeroy',
            fillcolor='rgba(155, 89, 182, 0.1)'
        ))
        fuel_fig.add_trace(go.Scatter(
            x=df["Year"], 
            y=df["Fuel Needed for Fleet"],
            name="Fuel Needed for Fleet", 
            line=dict(color="#e74c3c", width=2, dash='dash')
        ))
        fuel_fig.update_layout(
            title={
                'text': "LEO Fuel Depot vs Fleet Needs",
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 18, 'color': '#2c3e50', 'family': 'system-ui, -apple-system, sans-serif'}
            },
            xaxis_title="Year",
            yaxis_title="Fuel (tons LOX & CH4)",
            margin=dict(l=60, r=30, t=60, b=50),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(family='system-ui, -apple-system, sans-serif', color='#2c3e50'),
            xaxis=dict(gridcolor='rgba(0,0,0,0.1)', showgrid=True),
            yaxis=dict(gridcolor='rgba(0,0,0,0.1)', showgrid=True),
            legend=dict(
                x=0.02, 
                y=0.98,
                bgcolor='rgba(255,255,255,0.8)',
                bordercolor='rgba(0,0,0,0.1)',
                borderwidth=1,
                font=dict(size=12)
            )
        )

        # Mars Fuel Demand chart
        mars_fuel_fig = go.Figure()
        mars_fuel_fig.add_trace(go.Scatter(
            x=df["Year"], 
            y=df["Mars Fuel Demand"],
            name="Cumulative Mars Fuel Demand", 
            line=dict(color="#f39c12", width=3),
            fill='tozeroy',
            fillcolor='rgba(243, 156, 18, 0.1)'
        ))
        mars_fuel_fig.update_layout(
            title={
                'text': "Mars ISRU Fuel Demand",
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 18, 'color': '#2c3e50', 'family': 'system-ui, -apple-system, sans-serif'}
            },
            xaxis_title="Year",
            yaxis_title="Cumulative Fuel Demand (tons)",
            margin=dict(l=60, r=30, t=60, b=50),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(family='system-ui, -apple-system, sans-serif', color='#2c3e50'),
            xaxis=dict(gridcolor='rgba(0,0,0,0.1)', showgrid=True),
            yaxis=dict(gridcolor='rgba(0,0,0,0.1)', showgrid=True),
            showlegend=False
        )

        # Methane graph (unit conversions)
        TONS_TO_MMCF = 0.0493
        TON_TO_MMBTU = 52.6
        if methane_units == "tons":
            y1 = df["CH4 Withdrawn (tons)"]
            y2 = df["CH4 Delivered to Depot (tons)"]
            y_axis_title = "Cumulative CH4 (tons)"
        elif methane_units == "mmcf":
            y1 = df["CH4 Withdrawn (tons)"] * TONS_TO_MMCF
            y2 = df["CH4 Delivered to Depot (tons)"] * TONS_TO_MMCF
            y_axis_title = "Cumulative CH4 (MMcf)"
        else:
            y1 = df["CH4 Withdrawn (tons)"] * TON_TO_MMBTU * methane_price_mmbtu / 1e6
            y2 = df["CH4 Delivered to Depot (tons)"] * TON_TO_MMBTU * methane_price_mmbtu / 1e6
            y_axis_title = "Cumulative CH4 Cost (USD, millions)"

        methane_fig = go.Figure()
        methane_fig.add_trace(go.Scatter(
            x=df["Year"], y=y1, name="CH4 Withdrawn (Earth)", line=dict(color="#16a085", width=3)
        ))
        methane_fig.add_trace(go.Scatter(
            x=df["Year"], y=y2, name="CH4 Delivered to Depot", line=dict(color="#8e44ad", width=2, dash='dash')
        ))
        methane_fig.update_layout(
            title={
                'text': "Methane Withdrawn vs Delivered",
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 18, 'color': '#2c3e50', 'family': 'system-ui, -apple-system, sans-serif'}
            },
            xaxis_title="Year",
            yaxis_title=y_axis_title,
            margin=dict(l=60, r=30, t=60, b=50),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(family='system-ui, -apple-system, sans-serif', color='#2c3e50'),
            xaxis=dict(gridcolor='rgba(0,0,0,0.1)', showgrid=True),
            yaxis=dict(gridcolor='rgba(0,0,0,0.1)', showgrid=True),
            legend=dict(x=0.02, y=0.98, bgcolor='rgba(255,255,255,0.8)', bordercolor='rgba(0,0,0,0.1)', borderwidth=1, font=dict(size=12))
        )
        
        # Return all graphs and table data
        return people_fig, cargo_fig, fleet_fig, fuel_fig, mars_fuel_fig, methane_fig, lox_fig, production_data, operations_data, mars_data

    return dash_app 