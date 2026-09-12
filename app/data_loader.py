"""
Data Loader Module
==================
Parses Excel files into standardized JSON schema for optimization.

This module ensures backward compatibility by maintaining a fixed data contract.
"""

import pandas as pd
import streamlit as st
from typing import Dict, List, Tuple, Set, Any
import traceback


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean DataFrame column names and handle NaN values.
    
    Args:
        df: Input DataFrame
        
    Returns:
        Cleaned DataFrame with stripped column names
    """
    df.columns = [str(col).strip() for col in df.columns]
    return df


def validate_schema(data: Dict[str, Any]) -> bool:
    """
    Validate that data conforms to required schema.
    
    Required keys:
    - IUs, GUs, Routes, Periods
    - prod_cost, prod_cap, demand, min_close_stock
    - holding_cost, init_inv, mode_cost, modes_available
    
    Args:
        data: Data dictionary to validate
        
    Returns:
        True if valid, raises exception otherwise
    """
    required_keys = [
        "IUs", "GUs", "Routes", "Periods",
        "prod_cost", "prod_cap", "demand", "min_close_stock",
        "holding_cost", "init_inv", "mode_cost", "modes_available"
    ]
    
    for key in required_keys:
        if key not in data:
            raise ValueError(f"Missing required key in schema: {key}")
    
    # Type checks
    assert isinstance(data["IUs"], list), "IUs must be a list"
    assert isinstance(data["GUs"], list), "GUs must be a list"
    assert isinstance(data["Periods"], list), "Periods must be a list"
    
    return True


def parse_excel_to_json(uploaded_file) -> Dict[str, Any]:
    """
    Parse uploaded Excel file into standardized JSON schema.
    
    Expected Excel sheets:
    - ClinkerDemand: Demand by GU and period
    - ClinkerCapacity: Production capacity by IU and period
    - ProductionCost: Production cost by IU and period
    - LogisticsIUGU: Transport costs by route, mode, and period
    - IUGUOpeningStock: Initial inventory levels
    - IUGUClosingStock: Minimum closing stock requirements
    
    Args:
        uploaded_file: Streamlit uploaded file object
        
    Returns:
        Dictionary conforming to fixed JSON schema
    """
    try:
        # Initialize data structure (FIXED SCHEMA - DO NOT MODIFY)
        data = {
            "IUs": set(),
            "GUs": set(),
            "Routes": set(),
            "Periods": set(),
            "prod_cost": {},        # (iu, t) -> cost
            "prod_cap": {},         # (iu, t) -> capacity
            "demand": {},           # (gu, t) -> demand
            "min_close_stock": {},  # (iugu, t) -> min_stock
            "holding_cost": {},     # gu -> holding_cost
            "init_inv": {},         # iugu -> opening_stock
            "mode_cost": {},        # ((i,g), mode, t) -> cost
            "modes_available": {}   # (i,g) -> {mode1, mode2, ...}
        }
        
        # Read all sheets
        excel_data = pd.read_excel(uploaded_file, sheet_name=None)
        
        # 1. Parse ClinkerDemand
        if 'ClinkerDemand' in excel_data:
            df = clean_dataframe(excel_data['ClinkerDemand'])
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
                        data["IUs"].add(code)

        # 2. Parse ClinkerCapacity
        if 'ClinkerCapacity' in excel_data:
            df = clean_dataframe(excel_data['ClinkerCapacity'])
            for _, row in df.iterrows():
                code = str(row.get('IU CODE', '')).strip()
                period = int(row.get('TIME PERIOD', 1))
                val = float(row.get('CAPACITY', 0))
                
                if code:
                    data["IUs"].add(code)
                    data["Periods"].add(period)
                    data["prod_cap"][(code, period)] = val

        # 3. Parse ProductionCost
        if 'ProductionCost' in excel_data:
            df = clean_dataframe(excel_data['ProductionCost'])
            for _, row in df.iterrows():
                code = str(row.get('IU CODE', '')).strip()
                period = int(row.get('TIME PERIOD', 1))
                val = float(row.get('PRODUCTION COST', 0))
                
                if code:
                    data["IUs"].add(code)
                    data["Periods"].add(period)
                    data["prod_cost"][(code, period)] = val

        # 4. Parse LogisticsIUGU (Transport Costs)
        if 'LogisticsIUGU' in excel_data:
            df = clean_dataframe(excel_data['LogisticsIUGU'])
            for _, row in df.iterrows():
                from_iu = str(row.get('FROM IU CODE', '')).strip()
                to_gu = str(row.get('TO IUGU CODE', '')).strip()
                mode = str(row.get('TRANSPORT CODE', 'T1')).strip()
                period = int(row.get('TIME PERIOD', 1))
                freight = float(row.get('FREIGHT COST', 0))
                handling = float(row.get('HANDLING COST', 0))
                
                if from_iu and to_gu:
                    route = (from_iu, to_gu)
                    data["Periods"].add(period)
                    
                    # Track nodes
                    if from_iu.startswith('IU_'): 
                        data["IUs"].add(from_iu)
                    if to_gu.startswith('GU_'): 
                        data["GUs"].add(to_gu)
                    elif to_gu.startswith('IU_'): 
                        data["IUs"].add(to_gu)
                    
                    # Add route
                    if route not in data["Routes"]:
                        data["Routes"].add(route)
                        data["modes_available"][route] = set()
                    
                    data["modes_available"][route].add(mode)
                    data["mode_cost"][(route, mode, period)] = freight + handling

        # 5. Parse IUGUOpeningStock
        if 'IUGUOpeningStock' in excel_data:
            df = clean_dataframe(excel_data['IUGUOpeningStock'])
            for _, row in df.iterrows():
                code = str(row.get('IUGU CODE', '')).strip()
                val = float(row.get('OPENING STOCK', 0))
                
                if code:
                    data["init_inv"][code] = val
                    if code.startswith('IU_'): 
                        data["IUs"].add(code)
                    if code.startswith('GU_'): 
                        data["GUs"].add(code)

        # 6. Parse IUGUClosingStock
        if 'IUGUClosingStock' in excel_data:
            df = clean_dataframe(excel_data['IUGUClosingStock'])
            for _, row in df.iterrows():
                code = str(row.get('IUGU CODE', '')).strip()
                period = int(row.get('TIME PERIOD', 1))
                val = row.get('MIN CLOSE STOCK', 0)
                if pd.isna(val): 
                    val = 0
                val = float(val)
                
                if code:
                    data["Periods"].add(period)
                    data["min_close_stock"][(code, period)] = val

        # Convert sets to sorted lists
        data["IUs"] = sorted(list(data["IUs"]))
        data["GUs"] = sorted(list(data["GUs"]))
        data["Routes"] = sorted(list(data["Routes"]))
        data["Periods"] = sorted(list(data["Periods"]))
        
        # Set default holding costs
        for gu in data["GUs"]:
            if gu not in data["holding_cost"]:
                data["holding_cost"][gu] = 10.0
        
        # Validate
        if not data["Periods"]:
            raise ValueError("No time periods found in data!")
        
        validate_schema(data)
        
        return data

    except Exception as e:
        st.error(f"❌ Error parsing Excel file: {str(e)}")
        st.error(traceback.format_exc())
        return None
