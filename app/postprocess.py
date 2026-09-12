"""
Post-Processing Module
======================
Extract KPIs, allocate costs, and prepare results for visualization.
"""

import pandas as pd
from pyomo.environ import value
from typing import Dict, Any
from pyomo.environ import ConcreteModel


def safe_value(var):
    """Safely extract value from Pyomo variable."""
    if var is None:
        return 0
    try:
        return value(var)
    except:
        return 0


def calc_kpis(model: ConcreteModel, data: Dict[str, Any]) -> Dict[str, float]:
    """
    Calculate key performance indicators.
    
    Args:
        model: Solved Pyomo model
        data: Data dictionary
        
    Returns:
        Dictionary of KPIs
    """
    
    # Total cost
    total_cost = value(model.TotalCost)
    
    # Total demand vs fulfilled
    total_demand = sum(data["demand"].get((g, t), 0) 
                      for g in data["GUs"] for t in data["Periods"])
    total_unmet = sum(safe_value(model.UnmetDemand[g, t]) 
                     for g in data["GUs"] for t in data["Periods"])
    total_fulfilled = total_demand - total_unmet
    
    # Service level (%)
    service_level = 100 * (total_fulfilled / total_demand) if total_demand > 0 else 100
    
    # Production vs capacity
    total_production = sum(safe_value(model.Production[i, t]) 
                          for i in data["IUs"] for t in data["Periods"])
    total_capacity = sum(data["prod_cap"].get((i, t), 0) 
                        for i in data["IUs"] for t in data["Periods"])
    capacity_utilization = 100 * (total_production / total_capacity) if total_capacity > 0 else 0
    
    # Total shipments
    total_shipments = sum(safe_value(model.Shipment[i, g, m, t])
                         for (i, g, m) in model.RouteModes for t in model.T)
    
    # Safety stock violations
    total_ss_violations = sum(safe_value(model.SafetyStockViolation[g, t])
                             for g in data["GUs"] for t in data["Periods"])
    
    kpis = {
        "total_cost": total_cost,
        "total_demand": total_demand,
        "total_fulfilled": total_fulfilled,
        "total_unmet": total_unmet,
        "service_level_pct": service_level,
        "total_production": total_production,
        "total_capacity": total_capacity,
        "capacity_utilization_pct": capacity_utilization,
        "total_shipments": total_shipments,
        "total_ss_violations": total_ss_violations
    }
    
    return kpis


def extract_production_plan(model: ConcreteModel, data: Dict[str, Any]) -> pd.DataFrame:
    """Extract production plan by IU and period."""
    
    rows = []
    for i in data["IUs"]:
        for t in data["Periods"]:
            prod = safe_value(model.Production[i, t])
            cap = data["prod_cap"].get((i, t), 0)
            util = (prod / cap * 100) if cap > 0 else 0
            inv = safe_value(model.Inventory_IU[i, t])
            
            rows.append({
                "IU": i,
                "Period": t,
                "Production": prod,
                "Capacity": cap,
                "Utilization_%": util,
                "Ending_Inventory": inv
            })
    
    return pd.DataFrame(rows)


def extract_shipment_flows(model: ConcreteModel, data: Dict[str, Any]) -> pd.DataFrame:
    """Extract shipment flows with transport mode details."""
    
    rows = []
    for (i, g, mode) in model.RouteModes:
        for t in model.T:
            qty = safe_value(model.Shipment[i, g, mode, t])
            if qty > 0.01:  # Filter negligible amounts
                unit_cost = data["mode_cost"].get(((i, g), mode, t), 0)
                total_cost = qty * unit_cost
                
                rows.append({
                    " Period": t,
                    "From_IU": i,
                    "To_GU": g,
                    "Mode": mode,
                    "Quantity": qty,
                    "Unit_Cost": unit_cost,
                    "Total_Cost": total_cost
                })
    
    return pd.DataFrame(rows)


def extract_inventory_status(model: ConcreteModel, data: Dict[str, Any]) -> pd.DataFrame:
    """Extract inventory levels and safety stock compliance."""
    
    rows = []
    for g in data["GUs"]:
        for t in data["Periods"]:
            inv = safe_value(model.Inventory_GU[g, t])
            min_stock = data["min_close_stock"].get((g, t), 0)
            violation = safe_value(model.SafetyStockViolation[g, t])
            unmet = safe_value(model.UnmetDemand[g, t])
            demand = data["demand"].get((g, t), 0)
            fulfilled = demand - unmet
            
            rows.append({
                "GU": g,
                "Period": t,
                "Ending_Inventory": inv,
                "Min_Safety_Stock": min_stock,
                "SS_Violation": violation,
                "Demand": demand,
                "Fulfilled": fulfilled,
                "Unmet": unmet,
                "Fulfillment_%": (fulfilled / demand * 100) if demand > 0 else 100,
                "Status": "⚠️ Risk" if violation > 0.01 else "✅ OK"
            })
    
    return pd.DataFrame(rows)


def allocate_costs_to_gus(model: ConcreteModel, data: Dict[str, Any], 
                          unmet_penalty: float, ss_penalty: float) -> pd.DataFrame:
    """
    Allocate costs to each GU for financial deep dive.
    
    Cost allocation logic:
    - Production cost: Proportional to shipment volume received
    - Transport cost: Direct attribution
    - Holding cost: Direct (inventory * holding rate)
    - Penalties: Direct (unmet demand + safety stock violations)
    """
    
    rows = []
    
    # Pre-calculate IU production totals for cost allocation
    iu_production_cost = {}
    iu_production_volume = {}
    
    for i in data["IUs"]:
        for t in data["Periods"]:
            vol = safe_value(model.Production[i, t])
            cost_per_ton = data["prod_cost"].get((i, t), 0)
            iu_production_volume[(i, t)] = vol
            iu_production_cost[(i, t)] = vol * cost_per_ton
    
    # Allocate to each GU
    for g in data["GUs"]:
        for t in data["Periods"]:
            # 1. Holding cost (direct)
            holding_cost = safe_value(model.Inventory_GU[g, t]) * data["holding_cost"].get(g, 10)
            
            # 2. Penalty costs (direct)
            unmet_cost = safe_value(model.UnmetDemand[g, t]) * unmet_penalty
            ss_cost = safe_value(model.SafetyStockViolation[g, t]) * ss_penalty
            penalty_cost = unmet_cost + ss_cost
            
            # 3. Transport cost (direct) & Production cost (allocated)
            transport_cost = 0
            allocated_prod_cost = 0
            inbound_qty = 0
            
            for (i, g_curr, mode) in model.RouteModes:
                if g_curr == g:
                    qty = safe_value(model.Shipment[i, g, mode, t])
                    if qty > 0:
                        # Transport
                        unit_t_cost = data["mode_cost"].get(((i, g), mode, t), 0)
                        transport_cost += qty * unit_t_cost
                        inbound_qty += qty
                        
                        # Production allocation: (qty / total_iu_prod) * total_iu_cost
                        iu_vol = iu_production_volume.get((i, t), 1)
                        if iu_vol > 0:
                            ratio = qty / iu_vol
                            allocated_prod_cost += ratio * iu_production_cost.get((i, t), 0)
            
            total_cost = allocated_prod_cost + transport_cost + holding_cost + penalty_cost
            cost_per_ton = (allocated_prod_cost + transport_cost) / inbound_qty if inbound_qty > 0 else 0
            
            rows.append({
                "GU": g,
                "Period": t,
                "Production_Cost": allocated_prod_cost,
                "Transport_Cost": transport_cost,
                "Holding_Cost": holding_cost,
                "Penalty_Cost": penalty_cost,
                "Total_Cost": total_cost,
                "Inbound_Qty": inbound_qty,
                "Cost_per_Ton": cost_per_ton
            })
    
    return pd.DataFrame(rows)
