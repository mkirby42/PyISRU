"""
Chart figure builders -- one function per graph.
All return a plotly Figure object.
"""

import plotly.graph_objs as go
from .constants import BASE_LAYOUT, LEGEND_STYLE, TITLE_FONT, TONS_TO_MMCF, TON_TO_MMBTU


def _base_layout(**overrides):
    """Merge BASE_LAYOUT with per-chart overrides."""
    layout = dict(BASE_LAYOUT)
    for key in ("xaxis", "yaxis"):
        if key in overrides:
            merged = dict(layout.get(key, {}))
            merged.update(overrides.pop(key))
            layout[key] = merged
    layout.update(overrides)
    return layout


def _title(text):
    return {"text": text, "x": 0.5, "xanchor": "center", "font": TITLE_FONT}


def _hover(label, unit=""):
    suffix = (" " + unit) if unit else ""
    tpl = "Year %{x:.1f}<br>" + label + ": %{y:,.0f}" + suffix + "<extra></extra>"
    return tpl


def build_people_chart(df):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["Year"], y=df["People at Mars"],
        name="People at Mars",
        line=dict(color="#3498db", width=3),
        fill="tozeroy", fillcolor="rgba(52, 152, 219, 0.1)",
        hovertemplate=_hover("People"),
    ))
    fig.update_layout(**_base_layout(
        title=_title("People at Mars"),
        xaxis_title="Year", yaxis_title="Cumulative People",
        showlegend=False,
    ))
    return fig


def build_cargo_chart(df):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["Year"], y=df["Cargo at Mars (tons)"],
        name="Cargo at Mars",
        line=dict(color="#e74c3c", width=3),
        fill="tozeroy", fillcolor="rgba(231, 76, 60, 0.1)",
        hovertemplate=_hover("Cargo", "t"),
    ))
    fig.update_layout(**_base_layout(
        title=_title("Cargo at Mars"),
        xaxis_title="Year", yaxis_title="Cumulative Cargo (tons)",
        showlegend=False,
    ))
    return fig


def build_fleet_chart(df):
    fig = go.Figure()
    traces = [
        ("Crew Ships Available", "Crew Ships", "#3498db"),
        ("Cargo Ships Available", "Cargo Ships", "#2ecc71"),
        ("Tankers Available", "Tankers", "#f39c12"),
    ]
    for col, name, color in traces:
        fig.add_trace(go.Scatter(
            x=df["Year"], y=df[col], name=name,
            line=dict(color=color, width=3),
            hovertemplate=_hover(name),
        ))
    fig.update_layout(**_base_layout(
        title=_title("Available Fleet Size"),
        xaxis_title="Year", yaxis_title="Ships Available on Earth",
        legend=LEGEND_STYLE,
    ))
    return fig


def build_fuel_depot_chart(df):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["Year"], y=df["LEO Fuel Depot"],
        name="LEO Fuel Storage",
        line=dict(color="#9b59b6", width=3),
        fill="tozeroy", fillcolor="rgba(155, 89, 182, 0.1)",
        hovertemplate=_hover("Depot", "t"),
    ))
    fig.add_trace(go.Scatter(
        x=df["Year"], y=df["Fuel Needed for Fleet"],
        name="Fuel Needed for Fleet",
        line=dict(color="#e74c3c", width=2, dash="dash"),
        hovertemplate=_hover("Need", "t"),
    ))
    fig.update_layout(**_base_layout(
        title=_title("LEO Fuel Depot vs Fleet Needs"),
        xaxis_title="Year", yaxis_title="Fuel (tons LOX & CH4)",
        legend=LEGEND_STYLE,
    ))
    return fig


def build_mars_fuel_chart(df):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["Year"], y=df["Mars Fuel Demand"],
        name="Cumulative Mars Fuel Demand",
        line=dict(color="#f39c12", width=3),
        fill="tozeroy", fillcolor="rgba(243, 156, 18, 0.1)",
        hovertemplate=_hover("Demand", "t"),
    ))
    fig.update_layout(**_base_layout(
        title=_title("Mars ISRU Fuel Demand"),
        xaxis_title="Year", yaxis_title="Cumulative Fuel Demand (tons)",
        showlegend=False,
    ))
    return fig


def _hover_money(label):
    return "Year %{x:.1f}<br>" + label + ": $%{y:,.2f}M<extra></extra>"


def _hover_mmcf(label):
    return "Year %{x:.1f}<br>" + label + ": %{y:,.1f} MMcf<extra></extra>"


def build_methane_chart(df, methane_units, methane_price_mmbtu):
    if methane_units == "tons":
        y1 = df["CH4 Withdrawn (tons)"]
        y2 = df["CH4 Delivered to Depot (tons)"]
        y_title = "Cumulative CH4 (tons)"
        ht_w = _hover("Withdrawn", "t")
        ht_d = _hover("Delivered", "t")
    elif methane_units == "mmcf":
        y1 = df["CH4 Withdrawn (tons)"] * TONS_TO_MMCF
        y2 = df["CH4 Delivered to Depot (tons)"] * TONS_TO_MMCF
        y_title = "Cumulative CH4 (MMcf)"
        ht_w = _hover_mmcf("Withdrawn")
        ht_d = _hover_mmcf("Delivered")
    else:
        y1 = df["CH4 Withdrawn (tons)"] * TON_TO_MMBTU * methane_price_mmbtu / 1e6
        y2 = df["CH4 Delivered to Depot (tons)"] * TON_TO_MMBTU * methane_price_mmbtu / 1e6
        y_title = "Cumulative CH4 Cost (USD, millions)"
        ht_w = _hover_money("Withdrawn")
        ht_d = _hover_money("Delivered")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["Year"], y=y1, name="CH4 Withdrawn (Earth)",
        line=dict(color="#16a085", width=3),
        hovertemplate=ht_w,
    ))
    fig.add_trace(go.Scatter(
        x=df["Year"], y=y2, name="CH4 Delivered to Depot",
        line=dict(color="#8e44ad", width=2, dash="dash"),
        hovertemplate=ht_d,
    ))
    fig.update_layout(**_base_layout(
        title=_title("Methane Withdrawn vs Delivered"),
        xaxis_title="Year", yaxis_title=y_title,
        legend=LEGEND_STYLE,
    ))
    return fig


def build_lox_chart(df, lox_units, lox_price_per_ton):
    if lox_units == "tons":
        y1 = df["LOX Withdrawn (tons)"]
        y2 = df["LOX Delivered to Depot (tons)"]
        y_title = "Cumulative LOX (tons)"
        ht_w = _hover("Withdrawn", "t")
        ht_d = _hover("Delivered", "t")
    else:
        y1 = df["LOX Withdrawn (tons)"] * (lox_price_per_ton / 1e6)
        y2 = df["LOX Delivered to Depot (tons)"] * (lox_price_per_ton / 1e6)
        y_title = "Cumulative LOX Cost (USD, millions)"
        ht_w = _hover_money("Withdrawn")
        ht_d = _hover_money("Delivered")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["Year"], y=y1, name="LOX Withdrawn (Earth)",
        line=dict(color="#2980b9", width=3),
        hovertemplate=ht_w,
    ))
    fig.add_trace(go.Scatter(
        x=df["Year"], y=y2, name="LOX Delivered to Depot",
        line=dict(color="#c0392b", width=2, dash="dash"),
        hovertemplate=ht_d,
    ))
    fig.update_layout(**_base_layout(
        title=_title("LOX Withdrawn vs Delivered"),
        xaxis_title="Year", yaxis_title=y_title,
        legend=LEGEND_STYLE,
    ))
    return fig
