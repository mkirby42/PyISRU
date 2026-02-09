"""
Dash callbacks for the Fleet Simulator.
- Simulation callback (sliders -> charts + tables + KPIs)
- Preset / reset callback
- URL sync callbacks (shareable state)
"""

from urllib.parse import urlencode, parse_qs
from dash import Input, Output, State, callback_context, no_update
from .constants import (
    SLIDER_DEFS, DROPDOWN_DEFAULTS, DEFAULTS, ALL_CONTROL_IDS,
    SIM_PARAM_IDS, get_preset_values,
)
from .charts import (
    build_people_chart, build_cargo_chart, build_fleet_chart,
    build_fuel_depot_chart, build_mars_fuel_chart,
    build_methane_chart, build_lox_chart,
)
from fleet_size import simulate_mars_transport


def register_callbacks(dash_app):
    """Attach all callbacks to the given Dash app."""

    # ------------------------------------------------------------------
    # 1. Main simulation callback
    # ------------------------------------------------------------------
    sim_inputs = [Input(sid, "value") for sid in ALL_CONTROL_IDS]

    sim_outputs = [
        Output("people_graph", "figure"),
        Output("cargo_graph", "figure"),
        Output("fleet_graph", "figure"),
        Output("fuel_depot_graph", "figure"),
        Output("mars_fuel_graph", "figure"),
        Output("methane_graph", "figure"),
        Output("lox_graph", "figure"),
        Output("production_table", "data"),
        Output("operations_table", "data"),
        Output("mars_table", "data"),
        Output("kpi_people", "children"),
        Output("kpi_cargo", "children"),
        Output("kpi_tankers", "children"),
        Output("kpi_ships", "children"),
    ]

    @dash_app.callback(sim_outputs, sim_inputs)
    def update_simulation(*values):
        # Map positional args back to a dict keyed by control id
        val_map = dict(zip(ALL_CONTROL_IDS, values))

        # Build params dict for simulate_mars_transport
        params = {sid: val_map[sid] for sid in SIM_PARAM_IDS}
        df, production_data, operations_data, mars_data = simulate_mars_transport(params)

        # Display-only controls
        methane_units = val_map["methane_units"]
        methane_price = val_map["methane_price_mmbtu"]
        lox_units = val_map["lox_units"]
        lox_price = val_map["lox_price_per_ton"]

        # Build figures
        people_fig = build_people_chart(df)
        cargo_fig = build_cargo_chart(df)
        fleet_fig = build_fleet_chart(df)
        fuel_fig = build_fuel_depot_chart(df)
        mars_fuel_fig = build_mars_fuel_chart(df)
        methane_fig = build_methane_chart(df, methane_units, methane_price)
        lox_fig = build_lox_chart(df, lox_units, lox_price)

        # KPIs
        people_final = f"{int(df['People at Mars'].iloc[-1]):,}"
        cargo_final = f"{int(df['Cargo at Mars (tons)'].iloc[-1]):,} t"
        peak_tankers = f"{int(df['Tankers Available'].max()):,}"
        total_built = sum(
            r.get("Crew Built", 0) + r.get("Cargo Built", 0) + r.get("Tanker Built", 0)
            for r in production_data
        )
        total_built_str = f"{int(total_built):,}"

        return (
            people_fig, cargo_fig, fleet_fig, fuel_fig, mars_fuel_fig,
            methane_fig, lox_fig,
            production_data, operations_data, mars_data,
            people_final, cargo_final, peak_tankers, total_built_str,
        )

    # ------------------------------------------------------------------
    # 2. Preset / Reset callback
    # ------------------------------------------------------------------
    preset_outputs = [Output(sid, "value") for sid in ALL_CONTROL_IDS]

    @dash_app.callback(
        preset_outputs,
        Input("preset_dropdown", "value"),
        Input("reset_button", "n_clicks"),
        prevent_initial_call=True,
    )
    def apply_preset(preset_key, _n_clicks):
        ctx = callback_context
        triggered_id = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else None

        if triggered_id == "reset_button":
            preset_key = "default"

        vals = get_preset_values(preset_key or "default")
        return [vals[sid] for sid in ALL_CONTROL_IDS]

    # ------------------------------------------------------------------
    # 3. URL -> Controls (on page load)
    # ------------------------------------------------------------------
    url_init_outputs = [Output(sid, "value", allow_duplicate=True) for sid in ALL_CONTROL_IDS]

    @dash_app.callback(
        url_init_outputs,
        Input("url", "search"),
        prevent_initial_call=True,
    )
    def load_from_url(search):
        if not search:
            return [no_update] * len(ALL_CONTROL_IDS)

        qs = parse_qs(search.lstrip("?"))
        result = []
        for sid in ALL_CONTROL_IDS:
            if sid in qs:
                raw = qs[sid][0]
                # Try numeric conversion for sliders
                if sid in SLIDER_DEFS:
                    try:
                        val = float(raw)
                        # Use int if step is int-like
                        if SLIDER_DEFS[sid]["step"] == int(SLIDER_DEFS[sid]["step"]):
                            val = int(val)
                        result.append(val)
                        continue
                    except (ValueError, TypeError):
                        pass
                result.append(raw)
            else:
                result.append(no_update)
        return result

    # ------------------------------------------------------------------
    # 4. Controls -> URL (keep URL in sync)
    # ------------------------------------------------------------------
    @dash_app.callback(
        Output("url", "search"),
        [Input(sid, "value") for sid in ALL_CONTROL_IDS],
        prevent_initial_call=True,
    )
    def sync_url_from_controls(*values):
        params = {}
        for sid, val in zip(ALL_CONTROL_IDS, values):
            if val is not None and val != DEFAULTS.get(sid):
                params[sid] = val
        if params:
            return "?" + urlencode(params)
        return ""
