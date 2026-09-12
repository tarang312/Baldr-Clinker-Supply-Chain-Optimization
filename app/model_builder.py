"""
Model Builder Module
====================
Constructs Pyomo ConcreteModel for multi-period clinker optimization.

Business Logic:
- Minimize total cost (production + transport + holding + penalties)
- Multi-period inventory flow balance
- Soft safety stock constraints (violation allowed with penalty)
- Multiple transport modes per route
"""

from pyomo.environ import *
from typing import Dict, Any


def build_model(data: Dict[str, Any], params: Dict[str, float]) -> ConcreteModel:
    """
    Build Pyomo ConcreteModel from data schema.
    
    Args:
        data: Data dictionary conforming to fixed schema
        params: Model parameters
            - safety_stock_penalty: Penalty for violating safety stock (₹/ton)
            - unmet_demand_penalty: Penalty for unmet demand (₹/ton)
            
    Returns:
        Pyomo ConcreteModel ready for solving
    """
    
    m = ConcreteModel(name="ClinkerOptimization")
    
    # ============================================================
    # SETS
    # ============================================================
    
    m.T = Set(initialize=data["Periods"], doc="Time periods")
    m.I = Set(initialize=data["IUs"], doc="Integrated Units (production sites)")
    m.G = Set(initialize=data["GUs"], doc="Grinding Units (demand points)")
    m.Routes = Set(initialize=data["Routes"], dimen=2, doc="Valid IU → GU routes")
    
    # Flatten route-mode combinations: (i, g, mode)
    route_mode_list = []
    for route in data["Routes"]:
        modes = data["modes_available"].get(route, set())
        for mode in modes:
            route_mode_list.append((route[0], route[1], mode))
    
    m.RouteModes = Set(initialize=route_mode_list, dimen=3, 
                       doc="Route-Mode combinations: (IU, GU, TransportMode)")
    
    # ============================================================
    # PARAMETERS (Helper Function)
    # ============================================================
    
    def get_param(param_dict, key, default=0):
        """Safely retrieve parameter value with default."""
        return param_dict.get(key, default)
    
    # ============================================================
    # DECISION VARIABLES
    # ============================================================
    
    # Production at IU i in period t
    m.Production = Var(m.I, m.T, domain=NonNegativeReals, 
                       doc="Production quantity at each IU per period (tons)")
    
    # Inventory at end of period t
    m.Inventory_IU = Var(m.I, m.T, domain=NonNegativeReals,
                         doc="Ending inventory at IU (tons)")
    m.Inventory_GU = Var(m.G, m.T, domain=NonNegativeReals,
                         doc="Ending inventory at GU (tons)")
    
    # Shipment from IU i to GU g via mode m in period t
    m.Shipment = Var(m.RouteModes, m.T, domain=NonNegativeReals,
                     doc="Shipment quantity by route, mode, and period (tons)")
    
    # Demand fulfillment slack variables
    m.UnmetDemand = Var(m.G, m.T, domain=NonNegativeReals,
                        doc="Unmet demand at each GU per period (tons)")
    
    # Safety stock violation slack
    m.SafetyStockViolation = Var(m.G, m.T, domain=NonNegativeReals,
                                 doc="Safety stock shortfall (tons)")
    
    # ============================================================
    # CONSTRAINTS
    # ============================================================
    
    # 1. Production Capacity Constraint
    # Production cannot exceed available capacity
    def production_capacity_rule(m, i, t):
        """
        Business Rule: Each IU has a maximum production capacity per period
        based on plant specifications and maintenance schedules.
        """
        capacity = get_param(data["prod_cap"], (i, t), 1e9)
        return m.Production[i, t] <= capacity
    
    m.ProductionCapacity = Constraint(m.I, m.T, rule=production_capacity_rule,
                                     doc="Production <= Capacity")
    
    # 2. Inventory Flow Balance at IU
    # Inv(t) = Inv(t-1) + Prod(t) - Outbound(t)
    def iu_inventory_balance_rule(m, i, t):
        """
        Business Rule: Inventory balance at production site.
        Opening + Production - Shipments = Closing
        """
        # Previous period inventory (or initial if t=1)
        prev_inv = data["init_inv"].get(i, 0) if t == min(data["Periods"]) else m.Inventory_IU[i, t-1]
        
        # Total outbound shipments from this IU
        outflow = sum(m.Shipment[i_curr, g, mode, t] 
                     for (i_curr, g, mode) in m.RouteModes if i_curr == i)
        
        return m.Inventory_IU[i, t] == prev_inv + m.Production[i, t] - outflow
    
    m.IU_InventoryBalance = Constraint(m.I, m.T, rule=iu_inventory_balance_rule,
                                      doc="IU: Opening + Production - Shipments = Closing")
    
    # 3. Inventory Flow Balance at GU
    # Inv(t) = Inv(t-1) + Inbound(t) - Demand(t) + Unmet(t)
    def gu_inventory_balance_rule(m, g, t):
        """
        Business Rule: Inventory balance at demand point.
        Opening + Receipts - Demand (adjusted for shortfall) = Closing
        """
        # Previous period inventory (or initial if t=1)
        prev_inv = data["init_inv"].get(g, 0) if t == min(data["Periods"]) else m.Inventory_GU[g, t-1]
        
        # Total inbound shipments to this GU
        inflow = sum(m.Shipment[i, g_curr, mode, t] 
                    for (i, g_curr, mode) in m.RouteModes if g_curr == g)
        
        # Net demand (actual demand - what couldn't be met)
        demand_val = get_param(data["demand"], (g, t), 0)
        
        return m.Inventory_GU[g, t] == prev_inv + inflow - demand_val + m.UnmetDemand[g, t]
    
    m.GU_InventoryBalance = Constraint(m.G, m.T, rule=gu_inventory_balance_rule,
                                      doc="GU: Opening + Receipts - Demand + Unmet = Closing")
    
    # 4. Safety Stock Constraint (SOFT)
    # Inv(t) + Violation(t) >= MinStock(t)
    def safety_stock_rule(m, g, t):
        """
        Business Rule: Maintain minimum safety stock at demand points.
        This is a SOFT constraint - violations are allowed but penalized.
        Helps prevent infeasibility when demand spikes exceed supply.
        """
        min_stock = get_param(data["min_close_stock"], (g, t), 0)
        return m.Inventory_GU[g, t] + m.SafetyStockViolation[g, t] >= min_stock
    
    m.SafetyStock = Constraint(m.G, m.T, rule=safety_stock_rule,
                              doc="Inventory + Violation >= Safety Stock (soft)")
    
    # ============================================================
    # OBJECTIVE FUNCTION
    # ============================================================
    
    def total_cost_rule(m):
        """
        Minimize Total Supply Chain Cost.
        
        Components:
        1. Production Cost: Cost to manufacture clinker at each IU
        2. Transportation Cost: Freight + handling by mode and route
        3. Inventory Holding Cost: Storage cost at GUs
        4. Unmet Demand Penalty: Penalty for not meeting customer demand
        5. Safety Stock Violation Penalty: Penalty for falling below safety stock
        """
        
        # 1. Production Cost
        production_cost = sum(
            m.Production[i, t] * get_param(data["prod_cost"], (i, t), 0)
            for i in m.I for t in m.T
        )
        
        # 2. Transportation Cost (mode-specific)
        transport_cost = sum(
            m.Shipment[i, g, mode, t] * get_param(data["mode_cost"], ((i, g), mode, t), 0)
            for (i, g, mode) in m.RouteModes for t in m.T
        )
        
        # 3. Inventory Holding Cost (at GUs)
        holding_cost = sum(
            m.Inventory_GU[g, t] * data["holding_cost"].get(g, 10)
            for g in m.G for t in m.T
        )
        
        # 4. Unmet Demand Penalty
        unmet_penalty = sum(
            m.UnmetDemand[g, t] * params.get("unmet_demand_penalty", 20000)
            for g in m.G for t in m.T
        )
        
        # 5. Safety Stock Violation Penalty
        safety_penalty = sum(
            m.SafetyStockViolation[g, t] * params.get("safety_stock_penalty", 5000)
            for g in m.G for t in m.T
        )
        
        return production_cost + transport_cost + holding_cost + unmet_penalty + safety_penalty
    
    m.TotalCost = Objective(rule=total_cost_rule, sense=minimize,
                           doc="Minimize total supply chain cost")
    
    return m
