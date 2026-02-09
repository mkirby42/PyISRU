"""
Dash app creation and assembly.
"""

from dash import Dash
import dash_bootstrap_components as dbc

from .layout import build_layout
from .callbacks import register_callbacks


def create_fleet_dash_app(flask_app):
    """
    Create and configure the Fleet Simulator Dash app.

    Args:
        flask_app: The Flask application instance

    Returns:
        Dash app instance
    """
    dash_app = Dash(
        __name__,
        server=flask_app,
        url_base_pathname="/fleet-simulator/",
        external_stylesheets=[dbc.themes.FLATLY],
        suppress_callback_exceptions=True,
    )
    dash_app.title = "Mars Transport Simulator"
    dash_app.layout = build_layout()
    register_callbacks(dash_app)
    return dash_app
