from dash import html
import dash_bootstrap_components as dbc
from py_isru.lib.isru_plant import PlantStatus
from py_isru.lib.reactor import OperationalStatus
from dash import Output, Input, State
import dash

def create_control_panel(plant):
    """Create the control panel component."""
    return html.Div([
        html.H3("Control Panel"),
        html.Div([
            dbc.Button(
                "Start Plant",
                id="start-button",
                color="success",
                className="mr-1",
                disabled=False
            ),
            dbc.Button(
                "Stop Plant",
                id="stop-button",
                color="danger",
                className="mr-1",
                disabled=True
            ),
            dbc.Button(
                "Toggle Dust Storm",
                id="dust-storm-button",
                color="warning",
                className="mr-1"
            ),
        ], className="d-flex justify-content-start")
    ])

def register_callbacks(app, plant, data_provider):
    @app.callback(
        [Output("start-button", "disabled"),
         Output("stop-button", "disabled")],
        [Input("start-button", "n_clicks"),
         Input("stop-button", "n_clicks")],
        [State("start-button", "disabled"),
         State("stop-button", "disabled")]
    )
    def handle_control_buttons(start_clicks, stop_clicks, start_disabled, stop_disabled):
        ctx = dash.callback_context
        if not ctx.triggered:
            return start_disabled, stop_disabled
        
        button_id = ctx.triggered[0]["prop_id"].split(".")[0]
        
        if button_id == "start-button" and not start_disabled:
            success = plant.start()
            if success:
                return True, False  # Disable start, enable stop
            return False, True  # Keep start enabled if startup failed
            
        elif button_id == "stop-button" and not stop_disabled:
            success = plant.shutdown()
            if success:
                return False, True  # Enable start, disable stop
            return True, False  # Keep stop enabled if shutdown failed
            
        return start_disabled, stop_disabled

    @app.callback(
        Output("dust-storm-button", "children"),
        Input("dust-storm-button", "n_clicks"),
        State("dust-storm-button", "children")
    )
    def toggle_dust_storm(n_clicks, current_text):
        if n_clicks is None:
            return "Toggle Dust Storm"
        
        if current_text == "Toggle Dust Storm" or current_text == "Start Dust Storm":
            data_provider.dust_storm = True
            return "Stop Dust Storm"
        else:
            data_provider.dust_storm = False
            return "Start Dust Storm" 