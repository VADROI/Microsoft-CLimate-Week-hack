"""
Wildfire → Timber Supply Chain Impact Simulator
=================================================

An interactive Streamlit app that lets you explore how wildfire severity,
region, and duration might affect lumber prices, mill capacity, and
construction costs over the following 18 months.

The model is a simplified, illustrative simulation calibrated loosely to
historical events (2017 Tubbs Fire: ~50% price spike in a few months;
2023 Canada wildfires: ~15% national lumber price rise over 15 months;
2025 CA Eaton/Palisades fires: ~3.5-15% national impact; 2023 Canada
single-day futures spike: ~10%). It is meant for scenario exploration and
intuition-building, NOT for financial forecasting or trading decisions.

Run with:
    pip install streamlit pandas numpy plotly
    streamlit run wildfire_supply_chain_simulator.py
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# -----------------------------------------------------------------------
# Page setup
# -----------------------------------------------------------------------
st.set_page_config(
    page_title="Wildfire → Timber Supply Chain Simulator",
    page_icon="🔥",
    layout="wide",
)

st.title("🔥 Wildfire → Timber Supply Chain Simulator")
st.caption(
    "Explore how wildfire severity, region, and duration could ripple "
    "through lumber prices, mill capacity, and construction costs. "
    "Illustrative model, calibrated to historical patterns — not a forecast."
)

# -----------------------------------------------------------------------
# Sidebar controls
# -----------------------------------------------------------------------
st.sidebar.header("Scenario Controls")

region = st.sidebar.selectbox(
    "Region affected",
    ["Western Canada (Alberta/Quebec)", "California / US West", "US Southeast"],
    help="Different regions have different supply-chain leverage. Canada "
    "supplies ~80% of U.S. softwood lumber imports, so fires there tend "
    "to hit national prices harder.",
)

acres_burned = st.sidebar.slider(
    "Acres burned (millions)",
    min_value=0.1,
    max_value=15.0,
    value=2.0,
    step=0.1,
    help="2021 US wildfires: ~5.6M acres. 2023 Canada wildfires: ~10M acres (record).",
)

duration_weeks = st.sidebar.slider(
    "Active fire duration (weeks)",
    min_value=1,
    max_value=26,
    value=8,
)

mill_closures_pct = st.sidebar.slider(
    "Sawmills/harvest operations paused (%)",
    min_value=0,
    max_value=100,
    value=20,
    help="Share of regional mill & logging capacity temporarily shut down.",
)

rail_road_disruption = st.sidebar.slider(
    "Rail/road logistics disruption severity",
    min_value=0,
    max_value=10,
    value=3,
    help="0 = no infrastructure damage, 10 = major rail lines/bridges knocked out (like 2023 BC).",
)

rebuild_demand_shock = st.sidebar.slider(
    "Post-fire rebuild demand shock",
    min_value=0,
    max_value=10,
    value=4,
    help="How much local reconstruction spikes lumber demand once the fire is contained.",
)

months_horizon = st.sidebar.slider(
    "Forecast horizon (months)", min_value=3, max_value=24, value=15
)

st.sidebar.markdown("---")
st.sidebar.caption(
    "Model calibration reference points: Tubbs Fire 2017 (~+50%, few months), "
    "Canada 2023 (~+15% nat'l over 15mo), CA 2025 (~+3.5-15% nat'l), "
    "single-day futures spikes up to +10%."
)

# -----------------------------------------------------------------------
# Simplified simulation model
# -----------------------------------------------------------------------
REGION_LEVERAGE = {
    "Western Canada (Alberta/Quebec)": 1.6,   # highest: ~80% of US softwood imports
    "California / US West": 1.1,              # CA ~10% of US lumber supply
    "US Southeast": 0.6,                      # salvage glut can even depress prices short-term
}

region_factor = REGION_LEVERAGE[region]

# Base severity index combines acreage, duration, mill closures, logistics
severity_index = (
    (acres_burned / 10.0) * 0.35
    + (duration_weeks / 26.0) * 0.20
    + (mill_closures_pct / 100.0) * 0.25
    + (rail_road_disruption / 10.0) * 0.20
)

# Peak price shock (%) — scaled against historical anchors, capped at a
# plausible ceiling based on observed single-day/short-term spikes.
peak_shock_pct = min(severity_index * region_factor * 70, 90)

# Southeast-style salvage glut can create an initial price *dip* before
# recovery, when mill closures are low but acreage/timber glut is high.
initial_dip = 0.0
if region == "US Southeast" and mill_closures_pct < 30:
    initial_dip = -min(severity_index * 40, 35)

months = np.arange(0, months_horizon + 1)

# Build a price trajectory: sharp rise (or dip) during active fire weeks,
# partial correction, then a longer secondary rise driven by rebuild demand
# and constrained supply (mirrors the Canada 2023 pattern of price
# persistence well beyond the fire season itself).
trajectory = []
fire_month_frac = duration_weeks / 4.345  # weeks -> months
for m in months:
    if m <= fire_month_frac:
        # ramp up (or down, for glut scenario) during active fire period
        frac = m / max(fire_month_frac, 0.5)
        if initial_dip < 0:
            val = initial_dip * frac
        else:
            val = peak_shock_pct * frac
    else:
        months_since_fire = m - fire_month_frac
        if initial_dip < 0:
            # glut recovers, then modest rebound as salvage wood is used up
            recovery = initial_dip * np.exp(-months_since_fire / 3.0)
            rebound = (rebuild_demand_shock / 10.0) * 5 * (
                1 - np.exp(-months_since_fire / 6.0)
            )
            val = recovery + rebound
        else:
            # partial correction from peak, then secondary rise from
            # rebuild demand + persistent supply constraint
            correction = peak_shock_pct * np.exp(-months_since_fire / 4.0)
            secondary_rise = (rebuild_demand_shock / 10.0) * region_factor * 12 * (
                1 - np.exp(-months_since_fire / 8.0)
            )
            val = correction + secondary_rise
    trajectory.append(val)

df = pd.DataFrame({"Month": months, "Lumber price change (%)": trajectory})

# Mill capacity recovery (simple linear-ish recovery curve)
capacity_loss = mill_closures_pct * (1 - months / (months_horizon * 1.3))
capacity_loss = np.clip(capacity_loss, 0, 100)
df["Mill capacity offline (%)"] = capacity_loss

# Estimated added cost to a standard single-family home build
# (very rough illustrative figure, anchored to reports of ~$30,000
# added cost during the 2021 pandemic-era lumber spike at its peak ~500%+)
df["Est. added cost to a new home ($)"] = (
    df["Lumber price change (%)"] / 100.0
) * 30000 / 5.0  # scaled down since 500% was an extreme outlier year

# -----------------------------------------------------------------------
# Layout: headline metrics
# -----------------------------------------------------------------------
col1, col2, col3, col4 = st.columns(4)
col1.metric("Peak lumber price shock", f"{peak_shock_pct:+.0f}%" if initial_dip == 0 else f"{initial_dip:+.0f}%")
col2.metric("Severity index (0-1)", f"{severity_index:.2f}")
col3.metric("Peak mill capacity offline", f"{mill_closures_pct:.0f}%")
col4.metric(
    "Est. added cost, new home",
    f"${df['Est. added cost to a new home ($)'].max():,.0f}",
)

st.markdown("---")

# -----------------------------------------------------------------------
# Charts
# -----------------------------------------------------------------------
tab1, tab2, tab3 = st.tabs(
    ["📈 Lumber Price Trajectory", "🏭 Mill Capacity", "🏠 Construction Cost Impact"]
)

with tab1:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["Month"],
            y=df["Lumber price change (%)"],
            mode="lines+markers",
            line=dict(color="#d9480f", width=3),
            name="Projected price change",
        )
    )
    fig.add_hline(y=0, line_dash="dot", line_color="gray")
    fig.update_layout(
        title=f"Projected Lumber Price Change — {region}",
        xaxis_title="Months from fire onset",
        yaxis_title="Price change vs. baseline (%)",
        height=450,
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "Positive values = price increase (scarcity-driven, typical of Western/"
        "Canadian fires). Negative values = short-term price dip from a salvage "
        "wood glut (more typical of Southeast fires with low mill closures)."
    )

with tab2:
    fig2 = go.Figure()
    fig2.add_trace(
        go.Bar(
            x=df["Month"],
            y=df["Mill capacity offline (%)"],
            marker_color="#495057",
            name="Capacity offline",
        )
    )
    fig2.update_layout(
        title="Regional Mill & Harvest Capacity Offline Over Time",
        xaxis_title="Months from fire onset",
        yaxis_title="% of regional capacity offline",
        height=450,
    )
    st.plotly_chart(fig2, use_container_width=True)

with tab3:
    fig3 = go.Figure()
    fig3.add_trace(
        go.Scatter(
            x=df["Month"],
            y=df["Est. added cost to a new home ($)"],
            mode="lines+markers",
            line=dict(color="#2f9e44", width=3),
            fill="tozeroy",
            name="Added home cost",
        )
    )
    fig3.update_layout(
        title="Estimated Added Lumber Cost per New Single-Family Home",
        xaxis_title="Months from fire onset",
        yaxis_title="Added cost ($)",
        height=450,
    )
    st.plotly_chart(fig3, use_container_width=True)

st.markdown("---")

# -----------------------------------------------------------------------
# Data table + download
# -----------------------------------------------------------------------
with st.expander("📋 View underlying data table"):
    st.dataframe(df.style.format({
        "Lumber price change (%)": "{:.1f}",
        "Mill capacity offline (%)": "{:.1f}",
        "Est. added cost to a new home ($)": "${:,.0f}",
    }), use_container_width=True)

csv = df.to_csv(index=False).encode("utf-8")
st.download_button(
    "⬇️ Download scenario data as CSV",
    data=csv,
    file_name="wildfire_supply_chain_scenario.csv",
    mime="text/csv",
)

st.markdown("---")
st.caption(
    "⚠️ This is a simplified educational model built from a handful of "
    "historical reference points (2017 Tubbs Fire, 2021 Western US/Canada "
    "fires, 2023 Canada wildfires, 2025 California fires). It is not a "
    "validated econometric forecast — use it to build intuition about "
    "directional relationships, not to make purchasing or investment decisions."
)