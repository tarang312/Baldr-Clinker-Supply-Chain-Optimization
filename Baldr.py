import streamlit as st
import pandas as pd
import io
import traceback
from pyomo.environ import *
from pyomo.opt import SolverFactory, SolverStatus, TerminationCondition

# ============================================================
# PAGE CONFIGURATION & STYLING (Adani Style)
# ============================================================
st.set_page_config(
    page_title="Clinker Logistics Optimizer",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Adani-inspired Color Palette & Custom CSS
st.markdown("""
<style>
    /* Main Background & Text */
    .stApp {
        background-color: #F4F7F9;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    
    /* Headers */
    .main-header {
        font-size: 2.2rem;
        color: #2C3E50; /* Slate Blue/Dark Gray */
        font-weight: 700;
        margin-bottom: 0.5rem;
        border-bottom: 3px solid #2C3E50;
        padding-bottom: 10px;
    }
    .sub-header {
        font-size: 1.5rem;
        color: #34495E;
        font-weight: 600;
        margin-top: 1.5rem;
        margin-bottom: 1rem;
        border-left: 5px solid #2980B9; /* Adani Blue-ish */
        padding-left: 10px;
    }
    
    /* Metric Cards */
    .metric-card {
        background-color: #FFFFFF;
        padding: 1.5rem;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        border: 1px solid #E0E0E0;
        text-align: center;
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: bold;
        color: #2C3E50;
    }
    .metric-label {
        font-size: 0.9rem;
        color: #7F8C8D;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    /* Success/Info Boxes */
    .success-box {
        background-color: #E8F8F5;
        border: 1px solid #D1F2EB;
        border-left: 5px solid #1ABC9C;
        padding: 1rem;
        border-radius: 5px;
        color: #0E6251;
    }
    .info-box {
        background-color: #EBF5FB;
        border: 1px solid #D6EAF8;
        border-left: 5px solid #3498DB;
        padding: 1rem;
        border-radius: 5px;
        color: #21618C;
    }
    
    /* Tables */
    .dataframe {
        font-size: 0.9rem !important;
    }
</style>
""", unsafe_allow_html=True)

# Helper for width
def get_width(stretch=True):
    return 'stretch' if stretch else 'content'

# ============================================================
# EXCEL PARSING FUNCTION
# ============================================================
def parse_excel_to_data(uploaded_file):
    """Parse Excel file into Multi-Period Data Structure."""
    try:
        data = {
            "IUs": set(),
            "GUs": set(),
            "Routes": set(),
            "Periods": set(),
            "prod_cost": {},        # (iu, t)
            "prod_cap": {},         # (iu, t)
            "demand": {},           # (gu, t)
            "min_close_stock": {},  # (gu, t)
            "holding_cost": {},     # gu (constant over time usually, or (gu, t))
            "init_inv": {},         # gu (t=0 stock) & iu (t=0 stock)
            "mode_cost": {},        # (route_tuple, mode, t) -> cost
            "mode_handling": {},    # (route_tuple, mode, t) -> handling cost
            "modes_available": {}   # (route_tuple) -> list of modes
        }
        
        # Read Excel
        excel_data = pd.read_excel(uploaded_file, sheet_name=None)
        
        # Clean column names logic
        def clean_cols(df):
            df.columns = [str(col).strip() for col in df.columns]
            return df

        # 1. ClinkerDemand
        if 'ClinkerDemand' in excel_data:
            df = clean_cols(excel_data['ClinkerDemand'])
            for _, row in df.iterrows():
                code = str(row.get('IUGU CODE', '')).strip()
                period = int(row.get('TIME PERIOD', 1))
                val = float(row.get('DEMAND', 0))
                
                if code:
                    data["Periods"].add(period)
                    if code.startswith('GU_'):
                        data["GUs"].add(code)
                        data["demand"][(code, period)] = val
                    elif code.startswith('IU_'):
                        # IUs technically don't have demand but we track if present
                        data["IUs"].add(code)

        # 2. ClinkerCapacity
        if 'ClinkerCapacity' in excel_data:
            df = clean_cols(excel_data['ClinkerCapacity'])
            for _, row in df.iterrows():
                code = str(row.get('IU CODE', '')).strip()
                period = int(row.get('TIME PERIOD', 1))
                val = float(row.get('CAPACITY', 0))
                
                if code:
                    data["IUs"].add(code)
                    data["Periods"].add(period)
                    data["prod_cap"][(code, period)] = val

        # 3. ProductionCost
        if 'ProductionCost' in excel_data:
            df = clean_cols(excel_data['ProductionCost'])
            for _, row in df.iterrows():
                code = str(row.get('IU CODE', '')).strip()
                period = int(row.get('TIME PERIOD', 1))
                val = float(row.get('PRODUCTION COST', 0))
                
                if code:
                    data["IUs"].add(code)
                    data["Periods"].add(period)
                    data["prod_cost"][(code, period)] = val

        # 4. LogisticsIUGU
        if 'LogisticsIUGU' in excel_data:
            df = clean_cols(excel_data['LogisticsIUGU'])
            for _, row in df.iterrows():
                f = str(row.get('FROM IU CODE', '')).strip()
                t_to = str(row.get('TO IUGU CODE', '')).strip()
                mode = str(row.get('TRANSPORT CODE', 'T1')).strip()
                period = int(row.get('TIME PERIOD', 1))
                freight = float(row.get('FREIGHT COST', 0))
                handling = float(row.get('HANDLING COST', 0))
                
                if f and t_to:
                    route = (f, t_to)
                    data["Periods"].add(period)
                    
                    if f.startswith('IU_'): data["IUs"].add(f)
                    if t_to.startswith('GU_'): data["GUs"].add(t_to)
                    elif t_to.startswith('IU_'): data["IUs"].add(t_to) # IU transfer possibility
                    
                    if route not in data["Routes"]:
                        data["Routes"].add(route)
                        data["modes_available"][route] = set()
                    
                    data["modes_available"][route].add(mode)
                    # Store total cost
                    data["mode_cost"][(route, mode, period)] = freight + handling

        # 5. IUGUOpeningStock (Initial Inventory)
        if 'IUGUOpeningStock' in excel_data:
            df = clean_cols(excel_data['IUGUOpeningStock'])
            for _, row in df.iterrows():
                code = str(row.get('IUGU CODE', '')).strip()
                val = float(row.get('OPENING STOCK', 0))
                if code:
                    data["init_inv"][code] = val
                    if code.startswith('IU_'): data["IUs"].add(code)
                    if code.startswith('GU_'): data["GUs"].add(code)

        # 6. IUGUClosingStock (Min Close Stock / Safety Stock)
        if 'IUGUClosingStock' in excel_data:
            df = clean_cols(excel_data['IUGUClosingStock'])
            for _, row in df.iterrows():
                code = str(row.get('IUGU CODE', '')).strip()
                period = int(row.get('TIME PERIOD', 1))
                val = row.get('MIN CLOSE STOCK', 0)
                if pd.isna(val): val = 0
                val = float(val)
                
                if code:
                    data["Periods"].add(period)
                    data["min_close_stock"][(code, period)] = val

        # Final Cleanup & Defaults
        data["IUs"] = sorted(list(data["IUs"]))
        data["GUs"] = sorted(list(data["GUs"]))
        data["Routes"] = sorted(list(data["Routes"]))
        data["Periods"] = sorted(list(data["Periods"]))
        
        # Default Holding Cost (Hardcoded per requirement context or default)
        # Assuming 10 for all GUs if not specified
        for gu in data["GUs"]:
            data["holding_cost"][gu] = 10.0

        # Validate Continuity
        if not data["Periods"]:
            st.error("No Time Periods found in data!")
            return None

        return data

    except Exception as e:
        st.error(f"Error parsing Excel: {e}")
        st.error(traceback.format_exc())
        return None

# ============================================================
# LAYOUT & SIDEBAR
# ============================================================
st.markdown('<div class="main-header">🏗️ Clinker Allocation & Transportation Optimizer</div>', unsafe_allow_html=True)

with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2821/2821637.png", width=50) # Generic Logistics Icon
    st.markdown("### ⚙️ Control Panel")
    
    # File Upload
    uploaded_file = st.file_uploader("Upload Supply Chain Excel", type=["xlsx", "xls"])
    
    # Generate Sample Data Option
    use_sample = st.checkbox("Use Sample Data", value=(uploaded_file is None))
    
    st.markdown("---")
    st.markdown("### 🔧 Model Parameters")
    safety_stock_penalty = st.number_input("Safety Stock Violation Penalty (₹/Ton)", min_value=0, value=5000, step=100)
    unmet_demand_penalty = st.number_input("Unmet Demand Penalty (₹/Ton)", min_value=0, value=20000, step=1000)

# ============================================================
# DATA LOADING / GENERATION
# ============================================================
data = None

if use_sample and uploaded_file is None:
    # Generate robust multi-period sample data
    periods = [1, 2, 3]
    ius = ["IU_Alpha", "IU_Beta"]
    gus = ["GU_North", "GU_South", "GU_East"]
    routes = [
        ("IU_Alpha", "GU_North"), ("IU_Alpha", "GU_South"),
        ("IU_Beta", "GU_South"), ("IU_Beta", "GU_East")
    ]
    
    data = {
        "IUs": ius, "GUs": gus, "Routes": routes, "Periods": periods,
        "prod_cost": {}, "prod_cap": {}, "demand": {}, "min_close_stock": {},
        "holding_cost": {g: 15 for g in gus},
        "init_inv": {"GU_North": 500, "GU_South": 600, "GU_East": 400, "IU_Alpha": 1000, "IU_Beta": 1000},
        "mode_cost": {}, "modes_available": {}
    }
    
    # Populate Time-Variant Data
    for t in periods:
        data["prod_cost"][("IU_Alpha", t)] = 1200 + (t*10)
        data["prod_cost"][("IU_Beta", t)] = 1100 + (t*15)
        
        data["prod_cap"][("IU_Alpha", t)] = 50000
        data["prod_cap"][("IU_Beta", t)] = 60000
        
        data["demand"][("GU_North", t)] = 20000 + (t*500)
        data["demand"][("GU_South", t)] = 30000 - (t*200)
        data["demand"][("GU_East", t)] = 15000 + (t*1000)
        
        data["min_close_stock"][("GU_North", t)] = 2000
        data["min_close_stock"][("GU_South", t)] = 3000
        data["min_close_stock"][("GU_East", t)] = 1500
        
        # Modes
        for r in routes:
            data["modes_available"][r] = {"Road", "Rail"}
            base_dist = 500 if r[0]=="IU_Alpha" else 700
            data["mode_cost"][(r, "Road", t)] = base_dist * 2.5
            data["mode_cost"][(r, "Rail", t)] = base_dist * 1.8 # Cheaper but maybe limited?
            
    st.info("Using Multi-Period Sample Data")

elif uploaded_file:
    data = parse_excel_to_data(uploaded_file)
    if data:
        st.success("File Loaded Successfully")

if not data:
    st.stop()

# ============================================================
# OPTIMIZATION MODEL CORE
# ============================================================
def run_optimization(d, p_ss_viol, p_unmet):
    status_text = st.empty()
    progress = st.progress(0)
    
    status_text.text("Initializing Model...")
    
    m = ConcreteModel()
    
    # Sets
    m.T = Set(initialize=d["Periods"])
    m.I = Set(initialize=d["IUs"])
    m.G = Set(initialize=d["GUs"])
    m.Routes = Set(initialize=d["Routes"]) # (i, g) tuples
    
    # Flatten Modes Set: (i, g, mode)
    route_mode_list = []
    for r in d["Routes"]:
        modes = d["modes_available"].get(r, set())
        for mode in modes:
            route_mode_list.append((r[0], r[1], mode))
    m.RouteModes = Set(initialize=route_mode_list) # (i, g, mode)
    
    # Variables
    # 1. Production
    m.P = Var(m.I, m.T, domain=NonNegativeReals)
    # 2. Inventory (End of Period)
    m.Inv_G = Var(m.G, m.T, domain=NonNegativeReals)
    m.Inv_I = Var(m.I, m.T, domain=NonNegativeReals)
    # 3. Shipment Flow
    m.Ship = Var(m.RouteModes, m.T, domain=NonNegativeReals)
    # 4. Slack Variables (Soft Constraints)
    m.UnmetDemand = Var(m.G, m.T, domain=NonNegativeReals)
    m.SS_Viol = Var(m.G, m.T, domain=NonNegativeReals) # Violation of safety stock
    
    # Parameters Helper
    def get_p(param_dict, key, default=0):
        return param_dict.get(key, default)
    
    status_text.text("Building Constraints...")
    progress.progress(20)
    
    # Constraints
    
    # 1. Production Capacity
    def rule_cap(m, i, t):
        return m.P[i, t] <= get_p(d["prod_cap"], (i, t), 1e9)
    m.C_Cap = Constraint(m.I, m.T, rule=rule_cap)
    
    # 2. Inventory Balance @ IU
    # Inv(t) = Inv(t-1) + Prod(t) - Sum(Ship_Out)
    def rule_bal_i(m, i, t):
        prev_inv = d["init_inv"].get(i, 0) if t == min(d["Periods"]) else m.Inv_I[i, t-1]
        
        # Outflow: Sum of shipments from i to any g via any mode
        outflow = sum(m.Ship[i_curr, g, mode, t] for (i_curr, g, mode) in m.RouteModes if i_curr == i)
        
        return m.Inv_I[i, t] == prev_inv + m.P[i, t] - outflow
    m.C_Bal_I = Constraint(m.I, m.T, rule=rule_bal_i)
    
    # 3. Inventory Balance @ GU
    # Inv(t) = Inv(t-1) + Sum(Inbound) - Demand(t) + Unmet(t)
    def rule_bal_g(m, g, t):
        prev_inv = d["init_inv"].get(g, 0) if t == min(d["Periods"]) else m.Inv_G[g, t-1]
        
        # Inflow: Sum of shipments to g
        inflow = sum(m.Ship[i, g_curr, mode, t] for (i, g_curr, mode) in m.RouteModes if g_curr == g)
        
        demand_val = get_p(d["demand"], (g, t), 0)
        
        return m.Inv_G[g, t] == prev_inv + inflow - demand_val + m.UnmetDemand[g, t]
    m.C_Bal_G = Constraint(m.G, m.T, rule=rule_bal_g)
    
    # 4. Safety Stock (Soft Constraint)
    # Inv(t) + SS_Viol(t) >= MinStock(t)
    def rule_ss(m, g, t):
        min_stock = get_p(d["min_close_stock"], (g, t), 0)
        return m.Inv_G[g, t] + m.SS_Viol[g, t] >= min_stock
    m.C_SS = Constraint(m.G, m.T, rule=rule_ss)
    
    # Objective Function
    def rule_obj(m):
        # 1. Production Cost
        cost_prod = sum(m.P[i, t] * get_p(d["prod_cost"], (i, t), 0) for i in m.I for t in m.T)
        
        # 2. Transport Cost
        cost_trans = sum(m.Ship[i, g, mode, t] * get_p(d["mode_cost"], ((i,g), mode, t), 0) 
                         for (i, g, mode) in m.RouteModes for t in m.T)
        
        # 3. Holding Cost (At GUs)
        cost_hold = sum(m.Inv_G[g, t] * d["holding_cost"].get(g, 10) for g in m.G for t in m.T)
        
        # 4. Penalties
        cost_unmet = sum(m.UnmetDemand[g, t] * p_unmet for g in m.G for t in m.T)
        cost_ss = sum(m.SS_Viol[g, t] * p_ss_viol for g in m.G for t in m.T)
        
        return cost_prod + cost_trans + cost_hold + cost_unmet + cost_ss
        
    m.Obj = Objective(rule=rule_obj, sense=minimize)
    
    status_text.text("Solving (Multi-Stage)...")
    progress.progress(50)
    
    # Solver Wrapper Logic
    solvers_to_try = ['highs', 'glpk', 'cbc']
    results = None
    solved = False
    
    # Import solver module for custom path if needed
    try:
        from solver import solver as custom_solver
        # Try custom solver first if available
        try:
            status_text.text("Attempting solve with Configured Solver...")
            results = custom_solver.solve(m, tee=False)
            if (results.solver.status == SolverStatus.ok) and \
               (results.solver.termination_condition in [TerminationCondition.optimal, TerminationCondition.feasible]):
                solved = True
                st.toast("Solved with Configured Solver", icon="✅")
        except:
            pass
    except:
        pass

    if not solved:
        for s_name in solvers_to_try:
            if not SolverFactory(s_name).available():
                continue
                
            try:
                status_text.text(f"Attempting solve with {s_name.upper()}...")
                opt = SolverFactory(s_name)
                results = opt.solve(m, tee=False)
                
                if (results.solver.status == SolverStatus.ok) and \
                   (results.solver.termination_condition in [TerminationCondition.optimal, TerminationCondition.feasible]):
                    solved = True
                    st.toast(f"Solved with {s_name.upper()}", icon="✅")
                    break
            except Exception as e:
                print(f"Solver {s_name} failed: {e}")
                continue
            
    if not solved:
        st.error("❌ Highs, GLPK, and CBC all failed. Optimization cannot proceed.")
        st.stop()
        
    progress.progress(100)
    status_text.empty()
    
    return m

# ============================================================
# RESULTS PROCESSING & DASHBOARD
# ============================================================

def safe_val(v):
    if v is None: return 0
    try:
        return value(v)
    except:
        return 0

st.markdown("---")
# Run Button
if st.button("🚀 Run Multi-Period Optimization", type="primary"):
    
    # 1. Run optimization
    model = run_optimization(data, safety_stock_penalty, unmet_demand_penalty)
    
    # 2. Extract Data for DataFrame
    
    # KPI Summary Data
    total_cost = value(model.Obj)
    total_demand = sum(data["demand"].get((g, t), 0) for g in data["GUs"] for t in data["Periods"])
    total_unmet = sum(safe_val(model.UnmetDemand[g, t]) for g in data["GUs"] for t in data["Periods"])
    service_level = 100 * (1 - (total_unmet / total_demand)) if total_demand > 0 else 100
    
    # --- Executive Summary ---
    st.markdown('<div class="sub-header">📊 Executive Summary</div>', unsafe_allow_html=True)
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Optimized Cost", f"₹{total_cost:,.0f}")
    k2.metric("Service Level", f"{service_level:.2f}%")
    k3.metric("Unmet Demand", f"{total_unmet:,.0f} Tons", delta_color="inverse")
    k4.metric("Time Horizon", f"{len(data['Periods'])} Periods")
    
    # --- Detail Tabs ---
    tab1, tab2, tab3, tab4 = st.tabs(["🏭 Production Hub", "🚚 Logistics Matrix", "💰 Financial Deep Dive", "📉 Inventory Analysis"])
    
    with tab1:
        # Production Capability vs Actual
        prod_rows = []
        for i in data["IUs"]:
            for t in data["Periods"]:
                prod = safe_val(model.P[i, t])
                cap = data["prod_cap"].get((i, t), 0)
                util = (prod/cap)*100 if cap > 0 else 0
                prod_rows.append({"IU": i, "Period": t, "Production": prod, "Capacity": cap, "Utilization %": util})
        
        df_prod = pd.DataFrame(prod_rows)
        
        col1, col2 = st.columns([2, 1])
        with col1:
            st.bar_chart(df_prod, x="Period", y="Production", color="IU", stack=False)
        with col2:
            st.dataframe(df_prod.style.format({"Production": "{:,.0f}", "Capacity": "{:,.0f}", "Utilization %": "{:.1f}%"}))
            
    with tab2:
        # Logistics Flows
        # Need: From, To, Mode, Period, Qty, Cost
        ship_rows = []
        
        for (i, g, mode) in model.RouteModes:
            for t in model.T:
                qty = safe_val(model.Ship[i, g, mode, t])
                if qty > 0.1: # Filter small values
                    cost_per = data["mode_cost"].get(((i,g), mode, t), 0)
                    ship_rows.append({
                        "Period": t,
                        "From IU": i,
                        "To GU": g,
                        "Mode": mode,
                        "Quantity": qty,
                        "Unit Cost": cost_per,
                        "Total Cost": qty * cost_per
                    })
        
        df_ship = pd.DataFrame(ship_rows)
        if not df_ship.empty:
            # filters
            f_period = st.multiselect("Filter Period", options=data["Periods"], default=data["Periods"])
            df_view = df_ship[df_ship["Period"].isin(f_period)]
            
            st.dataframe(df_view, use_container_width=True)
            
            # Pivot view
            st.markdown("**Route Volume Matrix**")
            pivot = df_view.pivot_table(index=["From IU", "To GU"], columns="Period", values="Quantity", aggfunc="sum").fillna(0)
            st.dataframe(pivot.style.background_gradient(cmap="Blues"))
        else:
            st.info("No shipments required - check demand levels.")
            
    with tab3:
        # Financial Breakdown (GU Wise)
        # Cost Components: Prod + Transport + Holding + Penalty
        # This requires attribution. 
        # For simplicity, we calculate Prod Cost allocated by volume, Transport is direct.
        
        gu_fin_rows = []
        
        # Pre-calc totals for allocation
        total_prod_cost_iu_t = {}
        total_prod_vol_iu_t = {}
        for i in data["IUs"]:
            for t in data["Periods"]:
                p_vol = safe_val(model.P[i, t])
                p_cost = p_vol * data["prod_cost"].get((i, t), 0)
                total_prod_vol_iu_t[(i, t)] = p_vol
                total_prod_cost_iu_t[(i, t)] = p_cost

        for g in data["GUs"]:
            for t in data["Periods"]:
                # 1. Holding
                h_cost = safe_val(model.Inv_G[g, t]) * data["holding_cost"].get(g, 10)
                
                # 2. Penalty
                pen_cost = (safe_val(model.UnmetDemand[g, t]) * unmet_demand_penalty) + \
                           (safe_val(model.SS_Viol[g, t]) * safety_stock_penalty)
                           
                # 3. Transport (Direct)
                t_cost = 0
                # 4. Production Allocation
                allocated_p_cost = 0
                
                # Find all incoming shipments
                inbound_qty = 0
                for (i, g_curr, mode) in model.RouteModes:
                    if g_curr == g:
                        qty = safe_val(model.Ship[i, g, mode, t])
                        if qty > 0:
                            # Transport add
                            unit_t_cost = data["mode_cost"].get(((i,g), mode, t), 0)
                            t_cost += qty * unit_t_cost
                            
                            # Prod Allocation: (Qty / Total_IU_Prod) * Total_IU_Cost
                            iu_prod_vol = total_prod_vol_iu_t.get((i, t), 1)
                            if iu_prod_vol > 0:
                                ratio = qty / iu_prod_vol
                                allocated_p_cost += ratio * total_prod_cost_iu_t.get((i, t), 0)
                            
                            inbound_qty += qty
                
                gu_fin_rows.append({
                    "GU": g,
                    "Period": t,
                    "Production Cost": allocated_p_cost,
                    "Transport Cost": t_cost,
                    "Holding Cost": h_cost,
                    "Penalty Cost": pen_cost,
                    "Total Cost": allocated_p_cost + t_cost + h_cost + pen_cost,
                    "Inbound Qty": inbound_qty, 
                    "Sourcing Cost/Ton": (allocated_p_cost + t_cost)/inbound_qty if inbound_qty>0 else 0
                })
        
        df_fin = pd.DataFrame(gu_fin_rows)
        st.dataframe(df_fin.style.format({"Total Cost": "₹{:,.0f}", "Sourcing Cost/Ton": "₹{:.2f}"}), use_container_width=True)
        
        st.markdown("**Cost Composition**")
        cost_agg = df_fin.groupby("GU")[["Production Cost", "Transport Cost", "Holding Cost", "Penalty Cost"]].sum()
        st.bar_chart(cost_agg)
        
    with tab4:
        # Inventory & Safety Stock
        inv_rows = []
        for g in data["GUs"]:
            for t in data["Periods"]:
                end_inv = safe_val(model.Inv_G[g, t])
                min_s = data["min_close_stock"].get((g, t), 0)
                viol = safe_val(model.SS_Viol[g, t])
                inv_rows.append({
                    "GU": g,
                    "Period": t,
                    "Closing Stock": end_inv,
                    "Min Requirement": min_s,
                    "Violation": viol,
                    "Status": "⚠️ Risk" if viol > 0 else "✅ OK"
                })
        df_inv = pd.DataFrame(inv_rows)
        st.dataframe(df_inv)
        
else:
    st.info("👋 Upload data or use sample to begin optimization.")