"""
Clinker Supply Chain Optimization Platform
===========================================
Main Streamlit UI Application

Author: AI Architect
Version: 1.0.0
"""

import streamlit as st
import pandas as pd
import traceback

# Import custom modules
from app.data_loader import parse_excel_to_json
from app.model_builder import build_model
from app.solver_engine import solve_model, get_solver_info
from app.postprocess import (calc_kpis, extract_production_plan, 
                              extract_shipment_flows, extract_inventory_status,
                              allocate_costs_to_gus)
from app.visuals import (create_cost_donut_chart, create_production_bar_chart,
                         create_sankey_diagram, create_inventory_chart,
                         create_service_level_gauge, create_capacity_utilization_chart)
from sample_data import generate_sample_data
from config import (COLOR_PALETTE, DEFAULT_PARAMS, APP_TITLE, APP_ICON, TAGLINE, THEMES)

# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title=APP_TITLE,
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# SIDEBAR - CONTROL PANEL
# ============================================================

with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2821/2821637.png", width=60)
    st.markdown("## ⚙️ Control Panel")
    
    st.markdown("---")
    
    # Theme Switcher
    st.markdown("### 🎨 UI Theme")
    theme_choice = st.radio(
        "Appearance",
        options=["Light", "Dark"],
        index=0,
        format_func=lambda x: "☀️ Light Mode" if x == "Light" else "🌙 Dark Mode",
        help="Toggle between Light Mode and Dark Mode"
    )
    
    st.markdown("---")

theme_cfg = THEMES[theme_choice]

# ============================================================
# DYNAMIC HIGH-CONTRAST CSS STYLING
# ============================================================

st.markdown(f"""
<style>
    /* Main Background & Text */
    .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {{
        background-color: {theme_cfg['bg']} !important;
        color: {theme_cfg['text']} !important;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }}
    
    /* Sidebar Styling */
    [data-testid="stSidebar"] {{
        background-color: {theme_cfg['sidebar_bg']} !important;
        border-right: 1px solid {theme_cfg['card_border']} !important;
    }}
    [data-testid="stSidebar"] *, [data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] label {{
        color: {theme_cfg['text']} !important;
    }}
    
    /* Headings & Text */
    h1, h2, h3, h4, h5, h6, p, label, span, div {{
        color: {theme_cfg['text']};
    }}
    
    .main-header {{
        font-size: 2.5rem;
        color: {theme_cfg['primary']};
        font-weight: 700;
        margin-bottom: 0.5rem;
        border-bottom: 3px solid {theme_cfg['secondary']};
        padding-bottom: 15px;
    }}
    
    .section-header {{
        font-size: 1.8rem;
        color: {theme_cfg['primary']};
        font-weight: 600;
        margin-top: 2rem;
        margin-bottom: 1rem;
        border-left: 5px solid {theme_cfg['accent']};
        padding-left: 15px;
    }}
    
    /* Metrics High Contrast Fix */
    [data-testid="stMetric"] {{
        background-color: {theme_cfg['card_bg']} !important;
        border: 1px solid {theme_cfg['card_border']} !important;
        padding: 1rem !important;
        border-radius: 10px !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05) !important;
    }}
    [data-testid="stMetricLabel"] {{
        color: {theme_cfg['metric_label']} !important;
        font-weight: 600 !important;
        font-size: 0.95rem !important;
    }}
    [data-testid="stMetricValue"] {{
        color: {theme_cfg['metric_value']} !important;
        font-weight: 700 !important;
    }}
    
    /* Tabs Styling */
    button[data-baseweb="tab"] {{
        color: {theme_cfg['text_secondary']} !important;
        font-weight: 600 !important;
        font-size: 1rem !important;
    }}
    button[data-baseweb="tab"][aria-selected="true"] {{
        color: {theme_cfg['secondary']} !important;
        border-bottom-color: {theme_cfg['secondary']} !important;
    }}
    
    /* Expanders */
    [data-testid="stExpander"] {{
        background-color: {theme_cfg['card_bg']} !important;
        border: 1px solid {theme_cfg['card_border']} !important;
        border-radius: 8px !important;
    }}
    [data-testid="stExpander"] summary * {{
        color: {theme_cfg['text']} !important;
        font-weight: 600 !important;
    }}
    
    /* Info & Success Boxes */
    .info-box {{
        background-color: {theme_cfg['card_bg']};
        border-left: 5px solid {theme_cfg['secondary']};
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
        color: {theme_cfg['text']};
    }}
    
    .success-box {{
        background-color: {theme_cfg['card_bg']};
        border-left: 5px solid {theme_cfg['success']};
        padding: 1rem;
        border-radius: 8px;
        color: {theme_cfg['text']};
    }}
    
    /* Buttons */
    .stButton>button {{
        background-color: {theme_cfg['secondary']};
        color: #FFFFFF !important;
        font-size: 1.1rem;
        padding: 0.75rem 2rem;
        border-radius: 8px;
        border: none;
        font-weight: 600;
    }}
    
    .stButton>button:hover {{
        background-color: {theme_cfg['primary']};
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }}
</style>
""", unsafe_allow_html=True)

# ============================================================
# HEADER
# ============================================================

st.markdown(f'<div class="main-header">{APP_ICON} {APP_TITLE}</div>', unsafe_allow_html=True)
st.markdown(f"**{TAGLINE}**")

# Continued Sidebar Controls
with st.sidebar:
    # File Upload
    st.markdown("### 📂 Data Source")
    uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx", "xls"],
                                    help="Upload Excel with required sheets: ClinkerDemand, ClinkerCapacity, etc.")
    
    use_sample = st.checkbox("Use Sample Data", value=(uploaded_file is None),
                            help="Generate and use built-in sample data for testing")
    
    st.markdown("---")
    
    # Model Parameters
    st.markdown("### 🎛️ Model Parameters")
    
    safety_stock_penalty = st.number_input(
        "Safety Stock Violation Penalty (₹/ton)",
        min_value=0,
        value=DEFAULT_PARAMS["safety_stock_penalty"],
        step=500,
        help="Penalty cost when ending inventory falls below minimum safety stock"
    )
    
    unmet_demand_penalty = st.number_input(
        "Unmet Demand Penalty (₹/ton)",
        min_value=0,
        value=DEFAULT_PARAMS["unmet_demand_penalty"],
        step=1000,
        help="Penalty cost for not meeting customer demand"
    )
    
    st.markdown("---")
    
    # Scenario Settings
    st.markdown("### 🎯 Scenario Settings")
    scenario = st.selectbox(
        "Demand Scenario",
        ["Base Case", "High Demand (+15%)", "Low Demand (-15%)"],
        help="Adjust demand levels for what-if analysis"
    )
    
    st.markdown("---")
    st.caption("💡 Built with Streamlit + Pyomo")

# ============================================================
# DATA LOADING
# ============================================================

data = None

if use_sample and uploaded_file is None:
    with st.spinner("Generating sample data..."):
        data = generate_sample_data()
        
        # Apply scenario adjustment
        if scenario == "High Demand (+15%)":
            for key in data["demand"]:
                data["demand"][key] *= 1.15
        elif scenario == "Low Demand (-15%)":
            for key in data["demand"]:
                data["demand"][key] *= 0.85
        
    st.success("✅ Sample data loaded successfully")
    
    # Show data summary
    with st.expander("📊 Data Summary"):
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Integrated Units", len(data["IUs"]))
        col2.metric("Grinding Units", len(data["GUs"]))
        col3.metric("Transport Routes", len(data["Routes"]))
        col4.metric("Time Periods", len(data["Periods"]))

elif uploaded_file:
    with st.spinner("Parsing Excel file..."):
        data = parse_excel_to_json(uploaded_file)
    
    if data:
        st.success("✅ Excel file parsed successfully")
        
        # Show data summary
        with st.expander("📊 Data Summary"):
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Integrated Units", len(data["IUs"]))
            col2.metric("Grinding Units", len(data["GUs"]))
            col3.metric("Transport Routes", len(data["Routes"]))
            col4.metric("Time Periods", len(data["Periods"]))

# ============================================================
# OPTIMIZATION ENGINE
# ============================================================

if data is not None:
    
    st.markdown("---")
    
    # Run Optimization Button
    if st.button("🚀 Run Multi-Period Optimization", type="primary"):
        
        try:
            # Build model
            with st.spinner("🔨 Building optimization model..."):
                params = {
                    "safety_stock_penalty": safety_stock_penalty,
                    "unmet_demand_penalty": unmet_demand_penalty
                }
                model = build_model(data, params)
                st.success("✅ Model constructed")
            
            # Solve model
            with st.spinner("⚙️ Solving optimization problem..."):
                model, results, status_msg = solve_model(model, verbose=False)
                st.success(status_msg)
                
                if results:
                    solver_info = get_solver_info(results)
                    with st.expander("🔍 Solver Details"):
                        st.json(solver_info)
            
            # Calculate KPIs
            with st.spinner("📊 Calculating KPIs..."):
                kpis = calc_kpis(model, data)
                df_production = extract_production_plan(model, data)
                df_shipments = extract_shipment_flows(model, data)
                df_inventory = extract_inventory_status(model, data)
                df_costs = allocate_costs_to_gus(model, data, unmet_demand_penalty, safety_stock_penalty)
            
            # ============================================================
            # EXECUTIVE SUMMARY - KPI CARDS
            # ============================================================
            
            st.markdown('<div class="section-header">📊 Executive Summary</div>', unsafe_allow_html=True)
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric(
                    "Total Cost",
                    f"₹{kpis['total_cost']:,.0f}",
                    help="Total optimized supply chain cost"
                )
            
            with col2:
                delta_sl = kpis['service_level_pct'] - 95
                st.metric(
                    "Service Level",
                    f"{kpis['service_level_pct']:.1f}%",
                    f"{delta_sl:+.1f}%",
                    delta_color="normal",
                    help="Percentage of demand fulfilled"
                )
            
            with col3:
                st.metric(
                    "Capacity Utilization",
                    f"{kpis['capacity_utilization_pct']:.1f}%",
                    help="Production capacity used"
                )
            
            with col4:
                st.metric(
                    "Unmet Demand",
                    f"{kpis['total_unmet']:,.0f} tons",
                    help="Total demand not fulfilled"
                )
            
            st.markdown("---")
            
            # ============================================================
            # TABS - DETAILED VIEWS
            # ============================================================
            
            tab1, tab2, tab3, tab4, tab5 = st.tabs([
                "🎯 Overview",
                "🏭 Production",
                "🚚 Logistics",
                "💰 Financial",
                "📦 Inventory"
            ])
            
            # TAB 1: Overview with Sankey
            with tab1:
                st.markdown("### Supply Chain Flow Visualization")
                
                if not df_shipments.empty:
                    fig_sankey = create_sankey_diagram(df_shipments, theme_mode=theme_choice)
                    st.plotly_chart(fig_sankey, use_container_width=True)
                else:
                    st.info("No shipments in solution")
                
                # Cost breakdown donut
                cost_breakdown = {
                    "Production": sum(df_costs["Production_Cost"]),
                    "Transport": sum(df_costs["Transport_Cost"]),
                    "Holding": sum(df_costs["Holding_Cost"]),
                    "Penalties": sum(df_costs["Penalty_Cost"])
                }
                
                col1, col2 = st.columns([1, 1])
                with col1:
                    fig_donut = create_cost_donut_chart(cost_breakdown, theme_mode=theme_choice)
                    st.plotly_chart(fig_donut, use_container_width=True)
                
                with col2:
                    fig_gauge = create_service_level_gauge(kpis['service_level_pct'], theme_mode=theme_choice)
                    st.plotly_chart(fig_gauge, use_container_width=True)
            
            # TAB 2: Production Hub
            with tab2:
                st.markdown("### Production Plan by Period")
                
                fig_prod = create_production_bar_chart(df_production, theme_mode=theme_choice)
                st.plotly_chart(fig_prod, use_container_width=True)
                
                fig_util = create_capacity_utilization_chart(df_production, theme_mode=theme_choice)
                st.plotly_chart(fig_util, use_container_width=True)
                
                st.markdown("#### Production Details")
                st.dataframe(
                    df_production.style.format({
                        "Production": "{:,.0f}",
                        "Capacity": "{:,.0f}",
                        "Utilization_%": "{:.1f}%",
                        "Ending_Inventory": "{:,.0f}"
                    }),
                    use_container_width=True
                )
            
            # TAB 3: Logistics Matrix
            with tab3:
                st.markdown("### Shipment Flows")
                
                # Filters
                col1, col2 = st.columns(2)
                with col1:
                    filter_period = st.multiselect(
                        "Filter Period",
                        options=data["Periods"],
                        default=data["Periods"]
                    )
                with col2:
                    filter_mode = st.multiselect(
                        "Filter Transport Mode",
                        options=df_shipments["Mode"].unique().tolist() if not df_shipments.empty else [],
                        default=df_shipments["Mode"].unique().tolist() if not df_shipments.empty else []
                    )
                
                # Apply filters
                df_filtered = df_shipments[
                    (df_shipments[" Period"].isin(filter_period)) &
                    (df_shipments["Mode"].isin(filter_mode))
                ] if not df_shipments.empty else df_shipments
                
                st.dataframe(
                    df_filtered.style.format({
                        "Quantity": "{:,.0f}",
                        "Unit_Cost": "₹{:.2f}",
                        "Total_Cost": "₹{:,.0f}"
                    }),
                    use_container_width=True
                )
                
                # Pivot table
                if not df_filtered.empty:
                    st.markdown("#### Route Volume Matrix")
                    pivot = df_filtered.pivot_table(
                        index=["From_IU", "To_GU"],
                        columns=" Period",
                        values="Quantity",
                        aggfunc="sum"
                    ).fillna(0)
                    st.dataframe(pivot.style.background_gradient(cmap="Blues"), use_container_width=True)
            
            # TAB 4: Financial Deep Dive
            with tab4:
                st.markdown("### GU-wise Cost Breakdown")
                
                st.dataframe(
                    df_costs.style.format({
                        "Production_Cost": "₹{:,.0f}",
                        "Transport_Cost": "₹{:,.0f}",
                        "Holding_Cost": "₹{:,.0f}",
                        "Penalty_Cost": "₹{:,.0f}",
                        "Total_Cost": "₹{:,.0f}",
                        "Inbound_Qty": "{:,.0f}",
                        "Cost_per_Ton": "₹{:.2f}"
                    }),
                    use_container_width=True
                )
                
                # Cost composition by GU
                st.markdown("#### Cost Composition by GU")
                cost_agg = df_costs.groupby("GU")[
                    ["Production_Cost", "Transport_Cost", "Holding_Cost", "Penalty_Cost"]
                ].sum()
                st.bar_chart(cost_agg)
            
            # TAB 5: Inventory Analysis
            with tab5:
                st.markdown("### Inventory Status")
                
                fig_inv = create_inventory_chart(df_inventory, theme_mode=theme_choice)
                st.plotly_chart(fig_inv, use_container_width=True)
                
                st.markdown("#### Inventory Details")
                st.dataframe(
                    df_inventory.style.format({
                        "Ending_Inventory": "{:,.0f}",
                        "Min_Safety_Stock": "{:,.0f}",
                        "SS_Violation": "{:,.0f}",
                        "Demand": "{:,.0f}",
                        "Fulfilled": "{:,.0f}",
                        "Unmet": "{:,.0f}",
                        "Fulfillment_%": "{:.1f}%"
                    }).applymap(
                        lambda v: 'color: red' if v == "⚠️ Risk" else '',
                        subset=['Status']
                    ),
                    use_container_width=True
                )
                
        except Exception as e:
            st.error(f"❌ Error during optimization: {str(e)}")
            st.error(traceback.format_exc())

else:
    st.info("👋 Please upload an Excel file or use sample data to begin optimization.")
