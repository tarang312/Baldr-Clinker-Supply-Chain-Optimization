"""
Configuration Module
====================
Central configuration for the optimization platform.
"""

# ============================================================
# UI THEME CONFIGURATION
# ============================================================

COLOR_PALETTE = {
    "primary": "#2C3E50",      # Dark slate
    "secondary": "#2980B9",     # Blue
    "accent": "#1ABC9C",        # Turquoise
    "success": "#2ECC71",       # Green
    "warning": "#F39C12",       # Orange
    "danger": "#E74C3C",        # Red
    "light": "#ECF0F1",         # Light gray
    "background": "#F4F7F9"     # Off-white
}

THEMES = {
    "Light": {
        "bg": "#F8F9FA",
        "card_bg": "#FFFFFF",
        "card_border": "#E9ECEF",
        "sidebar_bg": "#FFFFFF",
        "text": "#1A202C",
        "text_secondary": "#4A5568",
        "primary": "#1E3A8A",
        "secondary": "#2563EB",
        "accent": "#0D9488",
        "success": "#16A34A",
        "warning": "#D97706",
        "danger": "#DC2626",
        "metric_value": "#0F172A",
        "metric_label": "#475569",
        "plotly_template": "plotly_white",
        "plotly_bg": "rgba(255,255,255,0)",
        "plotly_font": "#1E293B"
    },
    "Dark": {
        "bg": "#0E1117",
        "card_bg": "#1E2640",
        "card_border": "#2D3748",
        "sidebar_bg": "#161B22",
        "text": "#F8FAFC",
        "text_secondary": "#94A3B8",
        "primary": "#3B82F6",
        "secondary": "#60A5FA",
        "accent": "#14B8A6",
        "success": "#22C55E",
        "warning": "#F59E0B",
        "danger": "#EF4444",
        "metric_value": "#F8FAFC",
        "metric_label": "#CBD5E1",
        "plotly_template": "plotly_dark",
        "plotly_bg": "rgba(14,17,23,0)",
        "plotly_font": "#F8FAFC"
    }
}

# ============================================================
# MODEL DEFAULT PARAMETERS
# ============================================================

DEFAULT_PARAMS = {
    "safety_stock_penalty": 5000,    # ₹/ton violation
    "unmet_demand_penalty": 20000,   # ₹/ton unmet
    "min_fulfillment_pct": 95.0,     # Target service level
}

# ============================================================
# SOLVER CONFIGURATION
# ============================================================

SOLVER_PREFERENCES = ['highs', 'glpk', 'cbc']
SOLVER_TIMEOUT = 300  # seconds

# ============================================================
# DATA VALIDATION RULES
# ============================================================

MIN_PERIODS = 1
MAX_PERIODS = 12
MIN_IUS = 1
MAX_GUS = 50

# ============================================================
# UI TEXT CONSTANTS
# ============================================================

APP_TITLE = "Clinker Supply Chain Optimization Platform"
APP_ICON = "🏗️"
TAGLINE = "Executive Decision Support System for Multi-Period Planning"
