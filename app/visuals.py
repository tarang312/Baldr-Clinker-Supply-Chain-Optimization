"""
Visualization Module
====================
Executive-grade charts and diagrams using Plotly.
"""

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from typing import Dict, List


def _get_theme_settings(theme_mode: str):
    is_light = (theme_mode == "Light")
    return {
        "template": "plotly_white" if is_light else "plotly_dark",
        "font_color": "#1E293B" if is_light else "#F8FAFC",
        "sankey_iu_color": "#1E3A8A" if is_light else "#3B82F6",
        "sankey_gu_color": "#0D9488" if is_light else "#14B8A6",
        "sankey_link_color": "rgba(37, 99, 235, 0.3)" if is_light else "rgba(96, 165, 250, 0.3)"
    }


def create_cost_donut_chart(cost_breakdown: Dict[str, float], theme_mode: str = "Dark") -> go.Figure:
    """
    Create donut chart showing cost composition.
    """
    theme = _get_theme_settings(theme_mode)
    labels = list(cost_breakdown.keys())
    values = list(cost_breakdown.values())
    
    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=0.4,
        marker=dict(colors=px.colors.sequential.Blues_r),
        textinfo='label+percent',
        textposition='outside'
    )])
    
    fig.update_layout(
        title="Cost Distribution",
        showlegend=True,
        height=400,
        margin=dict(t=50, b=50, l=50, r=50),
        template=theme["template"],
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=theme["font_color"])
    )
    
    return fig


def create_production_bar_chart(df: pd.DataFrame, theme_mode: str = "Dark") -> go.Figure:
    """
    Create bar chart showing production by IU across periods.
    """
    theme = _get_theme_settings(theme_mode)
    fig = px.bar(
        df,
        x="Period",
        y="Production",
        color="IU",
        barmode="group",
        title="Production by Period and IU",
        labels={"Production": "Production (tons)", "Period": "Time Period"},
        color_discrete_sequence=px.colors.qualitative.Set2
    )
    
    fig.update_layout(
        xaxis_title="Period",
        yaxis_title="Production (tons)",
        legend_title="Integrated Unit",
        hovermode="x unified",
        height=400,
        template=theme["template"],
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=theme["font_color"])
    )
    
    return fig


def create_sankey_diagram(df_shipments: pd.DataFrame, theme_mode: str = "Dark") -> go.Figure:
    """
    Create Sankey diagram showing IU → GU flows.
    """
    theme = _get_theme_settings(theme_mode)
    flow_agg = df_shipments.groupby(['From_IU', 'To_GU'])['Quantity'].sum().reset_index()
    
    ius = flow_agg['From_IU'].unique().tolist()
    gus = flow_agg['To_GU'].unique().tolist()
    all_nodes = ius + gus
    
    node_map = {node: idx for idx, node in enumerate(all_nodes)}
    
    source = [node_map[row['From_IU']] for _, row in flow_agg.iterrows()]
    target = [node_map[row['To_GU']] for _, row in flow_agg.iterrows()]
    value = flow_agg['Quantity'].tolist()
    
    node_colors = [theme["sankey_iu_color"]] * len(ius) + [theme["sankey_gu_color"]] * len(gus)
    
    fig = go.Figure(data=[go.Sankey(
        node=dict(
            pad=15,
            thickness=20,
            line=dict(color="white" if theme_mode == "Dark" else "black", width=0.5),
            label=all_nodes,
            color=node_colors
        ),
        link=dict(
            source=source,
            target=target,
            value=value,
            color=theme["sankey_link_color"]
        )
    )])
    
    fig.update_layout(
        title="Supply Chain Flow: IU → GU",
        font=dict(size=12, color=theme["font_color"]),
        height=500,
        margin=dict(t=50, b=50, l=50, r=50),
        template=theme["template"],
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)"
    )
    
    return fig


def create_inventory_chart(df: pd.DataFrame, theme_mode: str = "Dark") -> go.Figure:
    """
    Create chart showing inventory vs safety stock.
    """
    theme = _get_theme_settings(theme_mode)
    fig = go.Figure()
    
    for gu in df['GU'].unique():
        df_gu = df[df['GU'] == gu]
        
        fig.add_trace(go.Scatter(
            x=df_gu['Period'],
            y=df_gu['Ending_Inventory'],
            mode='lines+markers',
            name=f'{gu} Inventory',
            line=dict(width=2)
        ))
        
        fig.add_trace(go.Scatter(
            x=df_gu['Period'],
            y=df_gu['Min_Safety_Stock'],
            mode='lines',
            name=f'{gu} Safety Stock',
            line=dict(dash='dash', width=1),
            opacity=0.6
        ))
    
    fig.update_layout(
        title="Inventory Levels vs Safety Stock",
        xaxis_title="Period",
        yaxis_title="Inventory (tons)",
        hovermode="x unified",
        height=450,
        legend=dict(orientation="v", x=1.05, y=1),
        template=theme["template"],
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=theme["font_color"])
    )
    
    return fig


def create_service_level_gauge(service_level: float, theme_mode: str = "Dark") -> go.Figure:
    """
    Create gauge chart for service level %.
    """
    theme = _get_theme_settings(theme_mode)
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=service_level,
        title={'text': "Service Level %"},
        delta={'reference': 95},
        gauge={
            'axis': {'range': [None, 100]},
            'bar': {'color': "#1ABC9C"},
            'steps': [
                {'range': [0, 70], 'color': "#E74C3C"},
                {'range': [70, 90], 'color': "#F39C12"},
                {'range': [90, 100], 'color': "#2ECC71"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 95
            }
        }
    ))
    
    fig.update_layout(
        height=300,
        margin=dict(t=50, b=50, l=50, r=50),
        template=theme["template"],
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=theme["font_color"])
    )
    
    return fig


def create_capacity_utilization_chart(df: pd.DataFrame, theme_mode: str = "Dark") -> go.Figure:
    """
    Create stacked bar chart for capacity utilization.
    """
    theme = _get_theme_settings(theme_mode)
    fig = go.Figure()
    
    for iu in df['IU'].unique():
        df_iu = df[df['IU'] == iu]
        
        fig.add_trace(go.Bar(
            x=df_iu['Period'],
            y=df_iu['Production'],
            name=iu,
            text=df_iu['Utilization_%'].round(1).astype(str) + '%',
            textposition='auto'
        ))
    
    fig.update_layout(
        title="Capacity Utilization by IU",
        xaxis_title="Period",
        yaxis_title="Production (tons)",
        barmode='group',
        height=400,
        hovermode="x unified",
        template=theme["template"],
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=theme["font_color"])
    )
    
    return fig


def create_logistics_flow_chart(df: pd.DataFrame, theme_mode: str = "Dark") -> go.Figure:
    """
    Create bar chart showing shipment volume by transport mode across periods.
    """
    theme = _get_theme_settings(theme_mode)
    fig = go.Figure()
    
    if not df.empty and 'Mode' in df.columns:
        period_col = ' Period' if ' Period' in df.columns else 'Period'
        modes = df['Mode'].unique().tolist()
        
        for mode in modes:
            df_mode = df[df['Mode'] == mode]
            flow_by_period = df_mode.groupby(period_col)['Quantity'].sum().reset_index()
            
            fig.add_trace(go.Bar(
                x=flow_by_period[period_col],
                y=flow_by_period['Quantity'],
                name=f"Mode: {mode}"
            ))
            
    fig.update_layout(
        title="Shipment Volume by Transport Mode across Periods",
        xaxis_title="Time Period",
        yaxis_title="Quantity (tons)",
        barmode='group',
        height=400,
        hovermode="x unified",
        template=theme["template"],
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=theme["font_color"])
    )
    
    return fig
