"""
Layout components for the Fleet Simulator Dash app.
Uses dash-bootstrap-components for responsive grid, accordion, tabs, and cards.
"""

from dash import html, dcc, dash_table
import dash_bootstrap_components as dbc

from .constants import SLIDER_DEFS, DROPDOWN_DEFAULTS, ACCORDION_SECTIONS, PRESETS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_slider(sid):
    """Build a dcc.Slider from SLIDER_DEFS entry."""
    d = SLIDER_DEFS[sid]
    children = [
        html.Label(d["label"], style={"fontWeight": "500", "color": "#2c3e50"}),
    ]
    if d["desc"]:
        children.append(
            html.P(d["desc"],
                   style={"fontSize": "12px", "color": "#95a5a6", "margin": "4px 0 8px 0"})
        )
    children.append(
        dcc.Slider(
            id=sid,
            min=d["min"], max=d["max"], step=d["step"], value=d["default"],
            marks={d["min"]: str(d["min"]), d["max"]: str(d["max"])},
            tooltip={"placement": "bottom", "always_visible": True},
        )
    )
    return html.Div(children, style={"marginBottom": "16px"})


def _make_dropdown(sid):
    """Build the methane_units or lox_units dropdown."""
    if sid == "methane_units":
        options = [
            {"label": "MMcf", "value": "mmcf"},
            {"label": "tons", "value": "tons"},
            {"label": "USD (millions)", "value": "usd"},
        ]
        default = DROPDOWN_DEFAULTS["methane_units"]
        label_text = "Methane Units"
    elif sid == "lox_units":
        options = [
            {"label": "tons", "value": "tons"},
            {"label": "USD (millions)", "value": "usd"},
        ]
        default = DROPDOWN_DEFAULTS["lox_units"]
        label_text = "LOX Units"
    else:
        return html.Div()

    return html.Div([
        html.Label(label_text, style={"fontWeight": "500", "color": "#2c3e50"}),
        dcc.Dropdown(
            id=sid, options=options, value=default,
            clearable=False,
            style={"marginTop": "5px", "marginBottom": "10px"},
        ),
    ], style={"marginBottom": "16px"})


def _build_control(sid):
    if sid in SLIDER_DEFS:
        return _make_slider(sid)
    if sid in DROPDOWN_DEFAULTS:
        return _make_dropdown(sid)
    return html.Div()


# ---------------------------------------------------------------------------
# Accordion (collapsible controls)
# ---------------------------------------------------------------------------

def build_controls_panel():
    """Return the full left-hand controls column content."""
    accordion_items = []
    for idx, (title, ids) in enumerate(ACCORDION_SECTIONS):
        accordion_items.append(
            dbc.AccordionItem(
                [_build_control(sid) for sid in ids],
                title=title,
                item_id=str(idx),
            )
        )

    preset_options = [{"label": v["label"], "value": k} for k, v in PRESETS.items()]

    return html.Div([
        html.H5("Mission Parameters",
                style={"color": "#34495e", "marginBottom": "15px", "fontWeight": "400"}),

        # Preset row
        dbc.Row([
            dbc.Col(
                dcc.Dropdown(
                    id="preset_dropdown",
                    options=preset_options,
                    value="default",
                    clearable=False,
                    placeholder="Preset...",
                ),
                width=8,
            ),
            dbc.Col(
                dbc.Button("Reset", id="reset_button", color="secondary", size="sm",
                           style={"width": "100%"}),
                width=4,
            ),
        ], className="mb-3"),

        dbc.Accordion(
            accordion_items,
            active_item="0",
            always_open=True,
            flush=True,
        ),
    ])


# ---------------------------------------------------------------------------
# KPI cards
# ---------------------------------------------------------------------------

def _kpi_card(card_id, label, color):
    return dbc.Col(
        dbc.Card([
            dbc.CardBody([
                html.H4("--", id=card_id,
                         className="card-title mb-0",
                         style={"fontWeight": "600", "color": color}),
                html.Small(label, className="text-muted"),
            ])
        ], className="shadow-sm"),
        lg=3, md=6, xs=6,
    )


def build_kpi_row():
    return dbc.Row([
        _kpi_card("kpi_people", "People on Mars (final)", "#3498db"),
        _kpi_card("kpi_cargo", "Cargo Delivered (final)", "#e74c3c"),
        _kpi_card("kpi_tankers", "Peak Tanker Fleet", "#f39c12"),
        _kpi_card("kpi_ships", "Total Ships Built", "#2ecc71"),
    ], className="g-3 mb-3")


# ---------------------------------------------------------------------------
# Chart tabs
# ---------------------------------------------------------------------------

def build_chart_tabs():
    graph_style = {"height": "400px"}
    return dcc.Loading(
        id="loading-charts",
        type="circle",
        children=dbc.Tabs([
            dbc.Tab([
                dcc.Graph(id="people_graph", style=graph_style),
                dcc.Graph(id="cargo_graph", style=graph_style),
            ], label="Settlement", tab_id="tab-settlement"),
            dbc.Tab([
                dcc.Graph(id="fleet_graph", style=graph_style),
                dcc.Graph(id="fuel_depot_graph", style=graph_style),
                dcc.Graph(id="mars_fuel_graph", style=graph_style),
            ], label="Fleet & Fuel", tab_id="tab-fleet"),
            dbc.Tab([
                dcc.Graph(id="methane_graph", style=graph_style),
                dcc.Graph(id="lox_graph", style=graph_style),
            ], label="Propellant Accounting", tab_id="tab-propellant"),
        ], active_tab="tab-settlement"),
    )


# ---------------------------------------------------------------------------
# Data tables (improved)
# ---------------------------------------------------------------------------

_CELL_STYLE = {"textAlign": "center", "fontSize": "12px", "padding": "6px 8px"}
_ZEBRA = [
    {"if": {"row_index": "odd"}, "backgroundColor": "#f8f9fa"},
    {"if": {"row_index": "even"}, "backgroundColor": "#ffffff"},
]


def _data_table(table_id, columns, header_color, extra_conditional=None):
    cond = list(_ZEBRA)
    if extra_conditional:
        cond.extend(extra_conditional)
    return dash_table.DataTable(
        id=table_id,
        columns=columns,
        data=[],
        style_table={
            "height": "320px",
            "overflowY": "auto",
            "overflowX": "auto",
            "borderRadius": "6px",
        },
        style_cell=_CELL_STYLE,
        style_header={
            "backgroundColor": header_color, "color": "white", "fontWeight": "600",
        },
        style_data_conditional=cond,
        fixed_columns={"headers": True, "data": 1},
    )


def build_tables():
    production_cols = [
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
        {"name": "Depot LOX (current, t)", "id": "Depot LOX (current, t)", "type": "text"},
    ]

    operations_cols = [
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
        {"name": "Ships Returning", "id": "Ships Returning", "type": "numeric"},
    ]

    ops_extra = [
        {
            "if": {
                "filter_query": '{Limiting Factor} = "Fuel"',
                "column_id": "Limiting Factor",
            },
            "backgroundColor": "#fce4e4",
            "color": "#c0392b",
        },
    ]

    mars_cols = [
        {"name": "Quarter", "id": "Quarter", "type": "text"},
        {"name": "Year", "id": "Year", "type": "text"},
        {"name": "People Delivered", "id": "People Delivered", "type": "numeric"},
        {"name": "Cargo Delivered", "id": "Cargo Delivered", "type": "text"},
        {"name": "Ships on Mars", "id": "Ships on Mars", "type": "text"},
        {"name": "Total People", "id": "Total People", "type": "text"},
        {"name": "Total Cargo", "id": "Total Cargo", "type": "text"},
        {"name": "Cumulative Fuel Demand", "id": "Cumulative Fuel Demand", "type": "text"},
    ]

    heading_style = {
        "color": "#34495e", "marginBottom": "12px",
        "fontFamily": "system-ui, -apple-system, sans-serif",
        "fontWeight": "400", "fontSize": "1.1rem",
    }

    return dcc.Loading(
        id="loading-tables",
        type="circle",
        children=html.Div([
            html.Div([
                html.H5("Production & Fleet Status (Quarterly)", style=heading_style),
                _data_table("production_table", production_cols, "#3498db"),
            ], className="mb-4"),
            html.Div([
                html.H5("Launch Operations (Launch Windows)", style=heading_style),
                _data_table("operations_table", operations_cols, "#e74c3c",
                            extra_conditional=ops_extra),
            ], className="mb-4"),
            html.Div([
                html.H5("Mars Settlement Status (Quarterly)", style=heading_style),
                _data_table("mars_table", mars_cols, "#f39c12"),
            ]),
        ]),
    )


# ---------------------------------------------------------------------------
# Full page layout
# ---------------------------------------------------------------------------

def build_layout():
    """Return the top-level Div for dash_app.layout."""
    return dbc.Container([
        # URL for shareable state
        dcc.Location(id="url", refresh=False),

        # Header
        dbc.Navbar(
            dbc.Container([
                html.A("Back to Blog", href="/",
                       className="navbar-brand",
                       style={"textDecoration": "none", "fontWeight": "500"}),
                dbc.NavbarBrand(
                    "Mars Settlement Transport Simulator",
                    className="mx-auto",
                    style={"fontWeight": "300", "fontSize": "1.6rem"},
                ),
                # spacer to balance the left link for centering
                html.Div(style={"width": "120px"}),
            ], fluid=True, className="d-flex align-items-center"),
            color="white",
            light=True,
            className="mb-3 shadow-sm",
        ),

        # KPI row
        build_kpi_row(),

        # Main content row
        dbc.Row([
            # Controls column
            dbc.Col(
                build_controls_panel(),
                lg=3, md=12,
                className="mb-3",
            ),
            # Charts + tables column
            dbc.Col([
                build_chart_tabs(),
                html.Hr(),
                build_tables(),
            ], lg=9, md=12),
        ]),
    ], fluid=True, style={
        "backgroundColor": "#f1f3f4",
        "minHeight": "100vh",
        "fontFamily": "system-ui, -apple-system, sans-serif",
    })
