"""
Default parameter values, preset configurations, slider definitions, and style tokens.
"""

# ---------------------------------------------------------------------------
# Slider / control definitions
# Each entry: (id, label, description, min, max, step, default, marks)
# ---------------------------------------------------------------------------

SLIDER_DEFS = {
    # Ship Capacity
    "n_people_per_ship": {
        "label": "People per Ship",
        "desc": "Crew capacity for each crew-class Starship",
        "min": 10, "max": 200, "step": 10, "default": 100,
    },
    "cargo_mass_per_ship": {
        "label": "Cargo Mass per Ship (tons)",
        "desc": "Cargo capacity for each cargo-class Starship",
        "min": 10, "max": 200, "step": 10, "default": 100,
    },
    # Manufacturing
    "crew_build_time_months": {
        "label": "Crew Ship Build Time (months)",
        "desc": "Time to build each crew ship from start to finish",
        "min": 1, "max": 12, "step": 1, "default": 6,
    },
    "cargo_build_time_months": {
        "label": "Cargo Ship Build Time (months)",
        "desc": "Time to build each cargo ship from start to finish",
        "min": 1, "max": 12, "step": 1, "default": 4,
    },
    "tanker_build_time_months": {
        "label": "Tanker Build Time (months)",
        "desc": "Time to build each tanker ship from start to finish",
        "min": 1, "max": 12, "step": 1, "default": 3,
    },
    "crew_line_capacity": {
        "label": "Crew Line Capacity",
        "desc": "Max crew ships building simultaneously. Production rate emerges from capacity x build time.",
        "min": 1, "max": 300, "step": 5, "default": 8,
    },
    "cargo_line_capacity": {
        "label": "Cargo Line Capacity",
        "desc": "Max cargo ships building simultaneously",
        "min": 1, "max": 500, "step": 5, "default": 15,
    },
    "tanker_line_capacity": {
        "label": "Tanker Line Capacity",
        "desc": "Max tanker ships building simultaneously",
        "min": 1, "max": 500, "step": 5, "default": 20,
    },
    # Operations
    "tanker_turnaround_days": {
        "label": "Tanker Turnaround (days)",
        "desc": "Days between flights for each tanker",
        "min": 1, "max": 30, "step": 1, "default": 7,
    },
    "fuel_per_tanker": {
        "label": "Fuel per Tanker (tons)",
        "desc": "Fuel load carried by each tanker to LEO depot",
        "min": 10, "max": 500, "step": 10, "default": 100,
    },
    "fuel_per_mars_mission": {
        "label": "Fuel per Mars Mission (tons)",
        "desc": "Fuel needed for complete round trip",
        "min": 100, "max": 2000, "step": 100, "default": 1600,
    },
    # Methane Accounting
    "o_f_ratio": {
        "label": "O/F Ratio (LOX/CH4)",
        "desc": None,
        "min": 2.5, "max": 4.5, "step": 0.1, "default": 3.75,
    },
    "methane_price_mmbtu": {
        "label": "Henry Hub Price ($/MMBtu)",
        "desc": None,
        "min": 1.0, "max": 10.0, "step": 0.1, "default": 2.69,
    },
    "tanker_ascent_ch4_tons": {
        "label": "Tanker Ascent CH4 per launch (tons)",
        "desc": None,
        "min": 0, "max": 2000, "step": 10, "default": 1030,
    },
    "crew_ascent_ch4_tons": {
        "label": "Crew Ascent CH4 per launch (tons)",
        "desc": None,
        "min": 0, "max": 2000, "step": 10, "default": 1030,
    },
    "cargo_ascent_ch4_tons": {
        "label": "Cargo Ascent CH4 per launch (tons)",
        "desc": None,
        "min": 0, "max": 2000, "step": 10, "default": 1030,
    },
    # LOX Accounting
    "lox_price_per_ton": {
        "label": "LOX Price ($/ton)",
        "desc": None,
        "min": 0, "max": 2000, "step": 50, "default": 500,
    },
    # Ship Lifespan
    "crew_ship_lifespan": {
        "label": "Crew Ship Lifespan (missions)",
        "desc": "Mars round trips before retirement",
        "min": 1, "max": 20, "step": 1, "default": 10,
    },
    "cargo_ship_lifespan": {
        "label": "Cargo Ship Lifespan (missions)",
        "desc": "Mars round trips before retirement",
        "min": 1, "max": 20, "step": 1, "default": 10,
    },
    "tanker_lifespan": {
        "label": "Tanker Lifespan (missions)",
        "desc": "LEO fuel runs before retirement",
        "min": 2, "max": 50, "step": 2, "default": 20,
    },
}

# Dropdown defaults (not sliders)
DROPDOWN_DEFAULTS = {
    "methane_units": "mmcf",
    "lox_units": "tons",
}

# Combined default dict for quick lookup
DEFAULTS = {sid: d["default"] for sid, d in SLIDER_DEFS.items()}
DEFAULTS.update(DROPDOWN_DEFAULTS)

# Ordered list of all control IDs (sliders + dropdowns) for callback wiring
ALL_CONTROL_IDS = list(SLIDER_DEFS.keys()) + list(DROPDOWN_DEFAULTS.keys())

# IDs that feed into simulate_mars_transport (exclude display-only controls)
SIM_PARAM_IDS = [
    "n_people_per_ship", "cargo_mass_per_ship",
    "crew_build_time_months", "cargo_build_time_months", "tanker_build_time_months",
    "crew_line_capacity", "cargo_line_capacity", "tanker_line_capacity",
    "tanker_turnaround_days", "fuel_per_tanker", "fuel_per_mars_mission",
    "crew_ship_lifespan", "cargo_ship_lifespan", "tanker_lifespan",
    "o_f_ratio",
    "tanker_ascent_ch4_tons", "crew_ascent_ch4_tons", "cargo_ascent_ch4_tons",
]

# ---------------------------------------------------------------------------
# Accordion section groupings: (section_title, list_of_control_ids)
# ---------------------------------------------------------------------------

ACCORDION_SECTIONS = [
    ("Ship Capacity", ["n_people_per_ship", "cargo_mass_per_ship"]),
    ("Manufacturing", [
        "crew_build_time_months", "cargo_build_time_months",
        "tanker_build_time_months", "crew_line_capacity",
        "cargo_line_capacity", "tanker_line_capacity",
    ]),
    ("Operations", [
        "tanker_turnaround_days", "fuel_per_tanker", "fuel_per_mars_mission",
    ]),
    ("Methane Accounting", [
        "o_f_ratio", "methane_units", "methane_price_mmbtu",
        "tanker_ascent_ch4_tons", "crew_ascent_ch4_tons", "cargo_ascent_ch4_tons",
    ]),
    ("LOX Accounting", ["lox_units", "lox_price_per_ton"]),
    ("Ship Lifespan", [
        "crew_ship_lifespan", "cargo_ship_lifespan", "tanker_lifespan",
    ]),
]

# ---------------------------------------------------------------------------
# Preset configurations  (only override keys that differ from DEFAULTS)
# ---------------------------------------------------------------------------

PRESETS = {
    "default": {
        "label": "Default",
        # uses DEFAULTS as-is
    },
    "conservative": {
        "label": "Conservative",
        "n_people_per_ship": 50,
        "cargo_mass_per_ship": 50,
        "crew_build_time_months": 9,
        "cargo_build_time_months": 7,
        "tanker_build_time_months": 5,
        "crew_line_capacity": 4,
        "cargo_line_capacity": 6,
        "tanker_line_capacity": 10,
        "tanker_turnaround_days": 14,
        "fuel_per_tanker": 80,
        "fuel_per_mars_mission": 1600,
        "crew_ship_lifespan": 5,
        "cargo_ship_lifespan": 5,
        "tanker_lifespan": 10,
    },
    "aggressive": {
        "label": "Aggressive Scaling",
        "n_people_per_ship": 200,
        "cargo_mass_per_ship": 200,
        "crew_build_time_months": 3,
        "cargo_build_time_months": 2,
        "tanker_build_time_months": 1,
        "crew_line_capacity": 50,
        "cargo_line_capacity": 80,
        "tanker_line_capacity": 120,
        "tanker_turnaround_days": 3,
        "fuel_per_tanker": 200,
        "fuel_per_mars_mission": 1600,
        "crew_ship_lifespan": 15,
        "cargo_ship_lifespan": 15,
        "tanker_lifespan": 40,
    },
    "spacex_cadence": {
        "label": "SpaceX Cadence",
        "n_people_per_ship": 100,
        "cargo_mass_per_ship": 150,
        "crew_build_time_months": 4,
        "cargo_build_time_months": 3,
        "tanker_build_time_months": 2,
        "crew_line_capacity": 20,
        "cargo_line_capacity": 30,
        "tanker_line_capacity": 50,
        "tanker_turnaround_days": 5,
        "fuel_per_tanker": 150,
        "fuel_per_mars_mission": 1600,
        "crew_ship_lifespan": 12,
        "cargo_ship_lifespan": 12,
        "tanker_lifespan": 30,
    },
}


def get_preset_values(preset_key: str) -> dict:
    """Return a full DEFAULTS dict with the chosen preset's overrides applied."""
    vals = dict(DEFAULTS)
    if preset_key in PRESETS:
        overrides = {k: v for k, v in PRESETS[preset_key].items() if k != "label"}
        vals.update(overrides)
    return vals


# ---------------------------------------------------------------------------
# Unit conversion constants (used in charts)
# ---------------------------------------------------------------------------

TONS_TO_MMCF = 0.0493
TON_TO_MMBTU = 52.6

# ---------------------------------------------------------------------------
# Common Plotly layout kwargs
# ---------------------------------------------------------------------------

BASE_LAYOUT = dict(
    margin=dict(l=60, r=30, t=60, b=50),
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    font=dict(family="system-ui, -apple-system, sans-serif", color="#2c3e50"),
    xaxis=dict(gridcolor="rgba(0,0,0,0.1)", showgrid=True),
    yaxis=dict(gridcolor="rgba(0,0,0,0.1)", showgrid=True),
    uirevision="constant",
)

LEGEND_STYLE = dict(
    x=0.02, y=0.98,
    bgcolor="rgba(255,255,255,0.8)",
    bordercolor="rgba(0,0,0,0.1)",
    borderwidth=1,
    font=dict(size=12),
)

TITLE_FONT = dict(size=18, color="#2c3e50", family="system-ui, -apple-system, sans-serif")
