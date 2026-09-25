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

# CO2 emission factors (metric tons CO2 per acre burned), calibrated to:
# - CA/US West: CARB 2020 report (4.2M acres -> 106.7 MMT CO2 = ~25.4 t/acre)
# - Western Canada: WRI/Global Forest Watch 2023 (7.8M ha / 19.3M acres -> ~3B tons CO2
#   = ~155 t/acre; boreal peat soils store far more carbon per acre than western US forest)
# - US Southeast: derived from EPA fuel-loading caps (5 tons/acre fuel East vs.
#   20 tons/acre West), scaled down proportionally from the CA factor (~6-7 t/acre)
CO2_FACTOR_TONS_PER_ACRE = {
    "Western Canada (Alberta/Quebec)": 155,
    "California / US West": 25,
    "US Southeast": 7,
}

region_factor = REGION_LEVERAGE[region]
co2_factor = CO2_FACTOR_TONS_PER_ACRE[region]

# Total CO2 released for this scenario (metric tons), scaled by acres burned
# and up/down slightly by mill closure % as a rough proxy for fire intensity/
# duration (more prolonged, intense burns consume more fuel per acre).
intensity_multiplier = 0.7 + (duration_weeks / 26.0) * 0.6
total_co2_tons = acres_burned * 1_000_000 * co2_factor * intensity_multiplier

# Reference comparisons (EPA average passenger vehicle ~4.6 metric tons
# CO2/year; global aviation ~2024 ~1 billion tons CO2/year)
AVG_CAR_TONS_PER_YEAR = 4.6
GLOBAL_AVIATION_TONS_PER_YEAR = 1_000_000_000
car_equivalent = total_co2_tons / AVG_CAR_TONS_PER_YEAR
aviation_pct = (total_co2_tons / GLOBAL_AVIATION_TONS_PER_YEAR) * 100

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

col5, col6, col7 = st.columns(3)
col5.metric("Total CO2 released", f"{total_co2_tons/1e6:,.1f} MMT")
col6.metric("≈ Cars driven for a year", f"{car_equivalent/1e6:,.1f} million")
col7.metric("≈ % of global aviation's annual CO2", f"{aviation_pct:.2f}%")

st.markdown("---")

# -----------------------------------------------------------------------
# Charts
# -----------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs(
    ["📈 Lumber Price Trajectory", "🏭 Mill Capacity", "🏠 Construction Cost Impact", "🌫️ CO2 Emissions"]
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

with tab4:
    # Cumulative CO2 release curve, following the same active-fire ramp
    # used for the price trajectory (most combustion happens while the
    # fire is actively burning, then tapers to near-zero after containment).
    co2_curve = []
    for m in months:
        if m <= fire_month_frac:
            frac = m / max(fire_month_frac, 0.5)
            co2_curve.append(total_co2_tons * min(frac, 1.0) * 0.95)
        else:
            co2_curve.append(total_co2_tons * 0.95 + total_co2_tons * 0.05 * min(
                (m - fire_month_frac) / 3.0, 1.0
            ))  # smoldering/residual burn tail
    df["Cumulative CO2 released (MMT)"] = np.array(co2_curve) / 1e6

    fig4 = go.Figure()
    fig4.add_trace(
        go.Scatter(
            x=df["Month"],
            y=df["Cumulative CO2 released (MMT)"],
            mode="lines+markers",
            line=dict(color="#5c636a", width=3),
            fill="tozeroy",
            fillcolor="rgba(92,99,106,0.15)",
            name="Cumulative CO2",
        )
    )
    fig4.update_layout(
        title=f"Cumulative CO2 Released — {region}",
        xaxis_title="Months from fire onset",
        yaxis_title="Cumulative CO2 (million metric tons)",
        height=450,
    )
    st.plotly_chart(fig4, use_container_width=True)

    st.markdown(
        f"""
**Scenario total: {total_co2_tons/1e6:,.1f} million metric tons of CO2**
(using a **{co2_factor} tons CO2/acre** factor for {region}, adjusted for
fire intensity/duration)

- Equivalent to roughly **{car_equivalent/1e6:,.1f} million cars** driven for a year
  (EPA avg. ~4.6 tons CO2/vehicle/year)
- Roughly **{aviation_pct:.2f}%** of global aviation's annual CO2 (~1 billion tons/year)

**Real-world reference points used to calibrate this model:**
- California 2020: 4.2M acres → 106.7 MMT CO2 ([CARB](https://ww2.arb.ca.gov/sites/default/files/2021-07/Wildfire%20Emission%20Estimates%20for%202020%20_Final.pdf))
- California 2021: 2.5M acres → 85.2 MMT CO2, Dixie Fire alone = 37.4 MMT ([CARB](https://ww2.arb.ca.gov/sites/default/files/classic/cc/inventory/Wildfire%20Emission%20Estimates%202000-2021.pdf))
- Canada 2023: 7.8M hectares → ~3 billion tons CO2, ~4x global aviation ([WRI/Global Forest Watch](https://www.wri.org/insights/canada-wildfire-emissions))
- Canada 2023 (satellite-based): 647 TgC, ~23% of global wildfire carbon emissions ([Nature](https://www.nature.com/articles/s41586-024-07878-z); [Copernicus/CAMS](https://atmosphere.copernicus.eu/copernicus-canada-produced-23-global-wildfire-carbon-emissions-2023))
- Regional fuel-load basis (East vs. West): EPA fire emissions methodology ([EPA](https://gaftp.epa.gov/AIR/nei/fire_summit/Raffuse.pdf))
        """
    )

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
    "historical reference points (2017 Tubbs Fire, 2020-2023 California/Canada "
    "wildfire seasons, 2025 California fires) and CARB/WRI/Nature/EPA emissions "
    "data. It is not a validated econometric or climate forecast — use it to "
    "build intuition about directional relationships, not to make purchasing, "
    "investment, or policy decisions."
)
