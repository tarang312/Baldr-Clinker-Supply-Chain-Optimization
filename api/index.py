"""
FastAPI Serverless API Backend for Vercel Deployment
====================================================
Exposes Pyomo optimization engine, sample data, and Excel parser endpoints.
"""

import sys
import os
import io
import traceback
from typing import Optional, Dict, Any

# Ensure project root is in sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.data_loader import parse_excel_to_json
from app.model_builder import build_model
from app.solver_engine import solve_model
from app.postprocess import (
    calc_kpis,
    extract_production_plan,
    extract_shipment_flows,
    extract_inventory_status,
    allocate_costs_to_gus
)
from sample_data import generate_sample_data
from config import DEFAULT_PARAMS

app = FastAPI(
    title="Clinker Supply Chain Optimization API",
    description="Multi-Period MILP Optimization Engine API",
    version="1.0.0"
)

# Enable CORS for portfolio deployment
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def serialize_data(data: dict) -> dict:
    """Convert Python dataset with tuple keys and sets into JSON-safe dict."""
    if not data:
        return {}
    
    serialized = {
        "IUs": list(data.get("IUs", [])),
        "GUs": list(data.get("GUs", [])),
        "Routes": [list(r) if isinstance(r, (tuple, list)) else [r] for r in data.get("Routes", [])],
        "Periods": list(data.get("Periods", [])),
        "prod_cost": {f"{k[0]}|{k[1]}": float(v) for k, v in data.get("prod_cost", {}).items()},
        "prod_cap": {f"{k[0]}|{k[1]}": float(v) for k, v in data.get("prod_cap", {}).items()},
        "demand": {f"{k[0]}|{k[1]}": float(v) for k, v in data.get("demand", {}).items()},
        "min_close_stock": {f"{k[0]}|{k[1]}": float(v) for k, v in data.get("min_close_stock", {}).items()},
        "holding_cost": {str(k): float(v) for k, v in data.get("holding_cost", {}).items()},
        "init_inv": {str(k): float(v) for k, v in data.get("init_inv", {}).items()},
        "mode_cost": {f"{k[0][0]}|{k[0][1]}|{k[1]}|{k[2]}": float(v) for k, v in data.get("mode_cost", {}).items()},
        "modes_available": {f"{k[0]}|{k[1]}": list(v) for k, v in data.get("modes_available", {}).items()}
    }
    return serialized


def deserialize_data(data: dict) -> dict:
    """Reconstruct Python dataset with tuple keys and sets for Pyomo model builder."""
    if not data:
        return {}
        
    deserialized = {
        "IUs": list(data.get("IUs", [])),
        "GUs": list(data.get("GUs", [])),
        "Routes": [tuple(r) if isinstance(r, (list, tuple)) else tuple(r.split("|")) for r in data.get("Routes", [])],
        "Periods": [int(p) for p in data.get("Periods", [])],
        "prod_cost": {},
        "prod_cap": {},
        "demand": {},
        "min_close_stock": {},
        "holding_cost": {str(k): float(v) for k, v in data.get("holding_cost", {}).items()},
        "init_inv": {str(k): float(v) for k, v in data.get("init_inv", {}).items()},
        "mode_cost": {},
        "modes_available": {}
    }
    
    for k, v in data.get("prod_cost", {}).items():
        parts = k.split("|")
        deserialized["prod_cost"][(parts[0], int(parts[1]))] = float(v)
        
    for k, v in data.get("prod_cap", {}).items():
        parts = k.split("|")
        deserialized["prod_cap"][(parts[0], int(parts[1]))] = float(v)
        
    for k, v in data.get("demand", {}).items():
        parts = k.split("|")
        deserialized["demand"][(parts[0], int(parts[1]))] = float(v)
        
    for k, v in data.get("min_close_stock", {}).items():
        parts = k.split("|")
        deserialized["min_close_stock"][(parts[0], int(parts[1]))] = float(v)
        
    for k, v in data.get("mode_cost", {}).items():
        parts = k.split("|")
        from_iu, to_gu, mode, p = parts[0], parts[1], parts[2], int(parts[3])
        deserialized["mode_cost"][((from_iu, to_gu), mode, p)] = float(v)
        
    for k, v in data.get("modes_available", {}).items():
        parts = k.split("|")
        route = (parts[0], parts[1])
        deserialized["modes_available"][route] = set(v)
        
    return deserialized


class OptimizationRequest(BaseModel):
    safety_stock_penalty: Optional[float] = DEFAULT_PARAMS["safety_stock_penalty"]
    unmet_demand_penalty: Optional[float] = DEFAULT_PARAMS["unmet_demand_penalty"]
    scenario: Optional[str] = "Base Case"
    custom_data: Optional[Dict[str, Any]] = None


@app.get("/")
def read_root():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    public_index = os.path.join(root_dir, "public", "index.html")
    if os.path.exists(public_index):
        return FileResponse(public_index)
    return {"status": "ok", "service": "Clinker Supply Chain Optimization API"}


@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "Clinker Supply Chain Optimization API"}


@app.get("/api/sample-data")
def get_sample_data():
    try:
        data = generate_sample_data()
        return {"status": "success", "data": serialize_data(data)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/upload")
async def upload_excel(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        file_obj = io.BytesIO(contents)
        raw_data = parse_excel_to_json(file_obj)
        if not raw_data:
            raise HTTPException(status_code=400, detail="Failed to parse Excel file.")
        serialized = serialize_data(raw_data)
        return {"status": "success", "data": serialized}
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"File parsing error: {str(e)}")


@app.post("/api/optimize")
def run_optimization(req: OptimizationRequest):
    try:
        # Load dataset (custom uploaded or default sample)
        if req.custom_data:
            data = deserialize_data(req.custom_data)
        else:
            data = generate_sample_data()

        # Apply scenario adjustment if sample data
        if req.scenario == "High Demand (+15%)":
            for key in data["demand"]:
                data["demand"][key] = float(data["demand"][key]) * 1.15
        elif req.scenario == "Low Demand (-15%)":
            for key in data["demand"]:
                data["demand"][key] = float(data["demand"][key]) * 0.85

        # Build Pyomo model
        params = {
            "safety_stock_penalty": req.safety_stock_penalty,
            "unmet_demand_penalty": req.unmet_demand_penalty
        }
        model = build_model(data, params)

        # Solve model
        model, results, status_msg = solve_model(model, verbose=False)

        # Extract KPIs & tables
        kpis = calc_kpis(model, data)
        df_production = extract_production_plan(model, data)
        df_shipments = extract_shipment_flows(model, data)
        df_inventory = extract_inventory_status(model, data)
        df_costs = allocate_costs_to_gus(model, data, req.unmet_demand_penalty, req.safety_stock_penalty)

        # Prepare Sankey flow format
        sankey_data = []
        if not df_shipments.empty:
            flow_agg = df_shipments.groupby(['From_IU', 'To_GU'])['Quantity'].sum().reset_index()
            for _, row in flow_agg.iterrows():
                sankey_data.append({
                    "source": str(row['From_IU']),
                    "target": str(row['To_GU']),
                    "value": float(row['Quantity'])
                })

        return {
            "status": "success",
            "status_msg": status_msg,
            "kpis": kpis,
            "production": df_production.to_dict(orient="records"),
            "shipments": df_shipments.to_dict(orient="records"),
            "inventory": df_inventory.to_dict(orient="records"),
            "costs": df_costs.to_dict(orient="records"),
            "sankey": sankey_data,
            "meta": {
                "ius": list(data["IUs"]),
                "gus": list(data["GUs"]),
                "periods": list(data["Periods"])
            }
        }

    except Exception as e:
        error_trace = traceback.format_exc()
        print(error_trace)
        raise HTTPException(status_code=500, detail=f"Optimization failed: {str(e)}")
