"""
Quick test script to verify modules load correctly
"""

import sys
print("Python version:", sys.version)
print("\nTesting imports...")

try:
    from app.data_loader import parse_excel_to_json
    print("[OK] data_loader imported")
except Exception as e:
    print("[FAIL] data_loader failed:", e)
    import traceback
    traceback.print_exc()

try:
    from app.model_builder import build_model
    print("[OK] model_builder imported")
except Exception as e:
    print("[FAIL] model_builder failed:", e)
    import traceback
    traceback.print_exc()

try:
    from app.solver_engine import solve_model
    print("[OK] solver_engine imported")
except Exception as e:
    print("[FAIL] solver_engine failed:", e)
    import traceback
    traceback.print_exc()

try:
    from app.postprocess import calc_kpis
    print("[OK] postprocess imported")
except Exception as e:
    print("[FAIL] postprocess failed:", e)
    import traceback
    traceback.print_exc()

try:
    from app.visuals import create_cost_donut_chart
    print("[OK] visuals imported")
except Exception as e:
    print("[FAIL] visuals failed:", e)
    import traceback
    traceback.print_exc()

try:
    from sample_data import generate_sample_data
    print("[OK] sample_data imported")
except Exception as e:
    print("[FAIL] sample_data failed:", e)
    import traceback
    traceback.print_exc()

print("\nTesting sample data generation...")
try:
    data = generate_sample_data()
    print(f"[OK] Generated data with {len(data['IUs'])} IUs, {len(data['GUs'])} GUs")
except Exception as e:
    print("[FAIL] Sample data generation failed:", e)
    import traceback
    traceback.print_exc()

print("\nTesting model build...")
try:
    from app.model_builder import build_model
    params = {"safety_stock_penalty": 5000, "unmet_demand_penalty": 20000}
    model = build_model(data, params)
    print("[OK] Model built successfully")
    print(f"  - {len(list(model.component_objects()))} components")
except Exception as e:
    print("[FAIL] Model build failed:", e)
    import traceback
    traceback.print_exc()

print("\nAll tests complete!")
