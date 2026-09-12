"""
Sample Data Generator
=====================
Generates realistic multi-period sample data for testing.
"""

from typing import Dict, Any


def generate_sample_data() -> Dict[str, Any]:
    """
    Generate comprehensive multi-period sample data.
    
    Returns:
        Data dictionary conforming to fixed schema
    """
    
    periods = [1, 2, 3]
    ius = ["IU_Mumbai", "IU_Gujarat", "IU_Rajasthan"]
    gus = ["GU_Delhi", "GU_Pune", "GU_Bangalore", "GU_Kolkata"]
    
    routes = [
        ("IU_Mumbai", "GU_Delhi"),
        ("IU_Mumbai", "GU_Pune"),
        ("IU_Mumbai", "GU_Bangalore"),
        ("IU_Gujarat", "GU_Delhi"),
        ("IU_Gujarat", "GU_Pune"),
        ("IU_Rajasthan", "GU_Delhi"),
        ("IU_Rajasthan", "GU_Kolkata"),
    ]
    
    data = {
        "IUs": ius,
        "GUs": gus,
        "Routes": routes,
        "Periods": periods,
        "prod_cost": {},
        "prod_cap": {},
        "demand": {},
        "min_close_stock": {},
        "holding_cost": {},
        "init_inv": {},
        "mode_cost": {},
        "modes_available": {}
    }
    
    # Production costs (vary by period - seasonal energy costs)
    base_prod_costs = {"IU_Mumbai": 1250, "IU_Gujarat": 1180, "IU_Rajasthan": 1220}
    for iu in ius:
        for t in periods:
            seasonal_factor = 1.0 + (t - 2) * 0.02  # Slight increase over time
            data["prod_cost"][(iu, t)] = base_prod_costs[iu] * seasonal_factor
    
    # Production capacities
    capacities = {"IU_Mumbai": 55000, "IU_Gujarat": 65000, "IU_Rajasthan": 50000}
    for iu in ius:
        for t in periods:
            data["prod_cap"][(iu, t)] = capacities[iu]
    
    # Demand (varies by period - Q1, Q2, Q3 construction seasonality)
    base_demands = {
        "GU_Delhi": 35000,
        "GU_Pune": 25000,
        "GU_Bangalore": 28000,
        "GU_Kolkata": 20000
    }
    demand_pattern = {1: 0.9, 2: 1.0, 3: 1.1}  # Increasing demand
    
    for gu in gus:
        for t in periods:
            data["demand"][(gu, t)] = base_demands[gu] * demand_pattern[t]
    
    # Safety stock requirements (15% of demand)
    for gu in gus:
        for t in periods:
            data["min_close_stock"][(gu, t)] = data["demand"][(gu, t)] * 0.15
    
    # Holding costs (storage cost per ton per period)
    for gu in gus:
        data["holding_cost"][gu] = 12.0
    
    # Initial inventories
    for iu in ius:
        data["init_inv"][iu] = 2000
    for gu in gus:
        data["init_inv"][gu] = base_demands[gu] * 0.1  # 10% of base demand
    
    # Transport modes and costs
    # Distance-based costs: Road (₹/ton-km), Rail (₹/ton-km)
    distances = {
        ("IU_Mumbai", "GU_Delhi"): 1400,
        ("IU_Mumbai", "GU_Pune"): 150,
        ("IU_Mumbai", "GU_Bangalore"): 980,
        ("IU_Gujarat", "GU_Delhi"): 950,
        ("IU_Gujarat", "GU_Pune"): 650,
        ("IU_Rajasthan", "GU_Delhi"): 650,
        ("IU_Rajasthan", "GU_Kolkata"): 1500,
    }
    
    for route in routes:
        dist = distances.get(route, 1000)
        data["modes_available"][route] = {"Road", "Rail"}
        
        for t in periods:
            # Road: More expensive but flexible
            data["mode_cost"][(route, "Road", t)] = dist * 2.5
            # Rail: Cheaper but requires volume
            data["mode_cost"][(route, "Rail", t)] = dist * 1.7
    
    return data
