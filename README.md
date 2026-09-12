# Clinker Supply Chain Optimization Platform - Adani Cement Hackathon

🏗️ **Executive Decision Support System for Multi-Period Planning**

## Overview

Production-grade Streamlit + Pyomo application for optimizing clinker allocation and transportation across Integrated Units (IUs) and Grinding Units (GUs). Features multi-period MILP optimization with soft constraints, executive dashboard, and modular backend architecture.

## Architecture

```
Baldr NN/
├── app/
│   ├── data_loader.py      # Excel → JSON schema parser
│   ├── model_builder.py    # Pyomo MILP model construction
│   ├── solver_engine.py    # Multi-stage solver (HiGHS/GLPK/CBC)
│   ├── postprocess.py      # KPI calculation & cost allocation
│   └── visuals.py          # Plotly charts & Sankey diagrams
├── run_app.py              # Main Streamlit UI
├── config.py               # Configuration constants
├── sample_data.py          # Sample data generator
└── solver.py               # (Optional) Custom solver wrapper
```

## Features

### Core Optimization

- **Multi-Period MILP**: Optimize across time horizons with inventory flow balance
- **Soft Constraints**: Safety stock violations allowed with penalty
- **Multi-Modal Transport**: Road/Rail with mode-specific costs
- **Demand Fulfillment**: Service level optimization with unmet demand penalties

### UI/UX

- **Executive Dashboard**: KPI cards, service level gauges
- **Sankey Diagrams**: Visual supply chain flows (IU → GU)
- **Interactive Charts**: Plotly-based visualizations
- **Scenario Analysis**: What-if scenarios (High/Low demand)

### Extensibility

- **Fixed Data Contract**: Backward-compatible JSON schema
- **Modular Backend**: Independent, testable modules
- **Plug-in Datasets**: Easy to add new data sources

## 🚀 Deploying to Streamlit Community Cloud

This repository is optimized for 1-click deployment on Streamlit Community Cloud.

1. Push this repository to GitHub.
2. Go to [Streamlit Community Cloud](https://streamlit.io/cloud).
3. Connect your GitHub repository.
4. Set the Main file path to `run_app.py`.
5. Click **Deploy**.

## Data Schema

### Required Excel Sheets

1. **ClinkerDemand**: Demand by GU and period
2. **ClinkerCapacity**: Production capacity by IU and period
3. **ProductionCost**: Production cost by IU and period
4. **LogisticsIUGU**: Transport costs by route, mode, and period
5. **IUGUOpeningStock**: Initial inventory levels
6. **IUGUClosingStock**: Minimum closing stock requirements

### JSON Schema (Internal)

```python
{
    "IUs": ["IU_001", ...],
    "GUs": ["GU_001", ...],
    "Routes": [("IU_001", "GU_001"), ...],
    "Periods": [1, 2, 3],
    "prod_cost": {("IU", period): cost},
    "prod_cap": {("IU", period): capacity},
    "demand": {("GU", period): demand},
    "min_close_stock": {("IUGU", period): min_stock},
    "holding_cost": {"GU": cost},
    "init_inv": {"IUGU": inventory},
    "mode_cost": {(("IU","GU"), "mode", period): cost},
    "modes_available": {("IU","GU"): {"Road", "Rail"}}
}
```

## Optimization Model

### Decision Variables

- `Production[i, t]`: Production at IU i in period t
- `Shipment[i, g, mode, t]`: Shipment from IU to GU via transport mode
- `Inventory_IU[i, t]`: Ending inventory at IU
- `Inventory_GU[g, t]`: Ending inventory at GU
- `UnmetDemand[g, t]`: Unmet demand (slack variable)
- `SafetyStockViolation[g, t]`: Safety stock shortfall (slack variable)

### Objective Function

```
Minimize:
  Production Cost
  + Transportation Cost
  + Inventory Holding Cost
  + Unmet Demand Penalty
  + Safety Stock Violation Penalty
```

### Key Constraints

1. **Production Capacity**: Production ≤ Available Capacity
2. **IU Inventory Balance**: Inv(t) = Inv(t-1) + Prod(t) - Shipments(t)
3. **GU Inventory Balance**: Inv(t) = Inv(t-1) + Receipts(t) - Demand(t) + Unmet(t)
4. **Safety Stock (Soft)**: Inv(t) + Violation(t) ≥ MinStock(t)

## Configuration

Edit `config.py` to customize:

- Default penalties (safety stock, unmet demand)
- Color palette
- Solver preferences
- Validation rules

## Sample Data

Use built-in sample data for testing:

- 3 IUs (Mumbai, Gujarat, Rajasthan)
- 4 GUs (Delhi, Pune, Bangalore, Kolkata)
- 3 Time periods
- 2 Transport modes (Road, Rail)

## Module Details

### `data_loader.py`

- Parses Excel files
- Validates schema
- Handles NaN values and column cleanup

### `model_builder.py`

- Constructs Pyomo ConcreteModel
- Defines sets, variables, constraints
- Documents business logic in code

### `solver_engine.py`

- Multi-stage solver fallback
- Attempts: Custom → HiGHS → GLPK → CBC
- Returns solve status and timing

### `postprocess.py`

- Calculates KPIs (cost, service level, utilization)
- Allocates costs to GUs
- Extracts production/shipment/inventory plans

### `visuals.py`

- Plotly charts (bar, donut, gauge)
- Sankey diagrams for flow visualization
- Inventory vs safety stock trends

## Future Enhancements

- [ ] Forecasting layer (ARIMA/Prophet)
- [ ] Multi-commodity support
- [ ] Supplier capacity constraints
- [ ] Real-time dashboard updates
- [ ] Export to PDF reports

## License

MIT License

## Author

Built by AI Architect for enterprise supply chain optimization.

---

**Version**: 1.0.0  
**Last Updated**: 2026-02-05
