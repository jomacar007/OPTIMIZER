"""Plotly chart builders for the Portfolio Optimizer.

Keeping chart construction separate from the Streamlit app makes it easy
to unit test the figures or reuse them in another context (e.g. exporting
to a report) without pulling in Streamlit itself.
"""

from __future__ import annotations

from typing import List

import plotly.graph_objects as go

from calculator import ScenarioResult

PROFIT_COLOR = "#1BAF7A"
LOSS_COLOR = "#E34948"


def build_profit_bar_chart(result: ScenarioResult) -> go.Figure:
    """Build a bar chart of net profit/loss for each market scenario.

    Bars are colored green for a positive outcome and red for a negative
    one, making the worst-case scenario immediately visible.

    Args:
        result: The computed scenario result to visualize.

    Returns:
        A Plotly Figure ready to be rendered with st.plotly_chart.
    """
    colors: List[str] = [
        PROFIT_COLOR if p >= 0 else LOSS_COLOR for p in result.profit_per_scenario
    ]

    fig = go.Figure(
        data=[
            go.Bar(
                x=result.labels,
                y=result.profit_per_scenario,
                marker_color=colors,
                text=[f"${p:,.2f}" for p in result.profit_per_scenario],
                textposition="outside",
                hovertemplate="%{x}<br>Ganancia: $%{y:,.2f}<extra></extra>",
            )
        ]
    )

    fig.update_layout(
        title="Ganancia neta por escenario",
        xaxis_title="Resultado del mercado",
        yaxis_title="Ganancia neta (USD)",
        showlegend=False,
        template="plotly_white",
        margin=dict(l=40, r=20, t=60, b=40),
    )
    fig.add_hline(y=0, line_width=1, line_color="#888780")

    return fig


def build_investment_pie_chart(result: ScenarioResult) -> go.Figure:
    """Build a pie chart showing how capital is distributed across outcomes.

    Args:
        result: The computed scenario result to visualize.

    Returns:
        A Plotly Figure ready to be rendered with st.plotly_chart.
    """
    fig = go.Figure(
        data=[
            go.Pie(
                labels=result.labels,
                values=result.investments,
                hole=0.45,
                hovertemplate="%{label}<br>$%{value:,.2f} (%{percent})<extra></extra>",
            )
        ]
    )
    fig.update_layout(
        title="Distribución del capital",
        template="plotly_white",
        margin=dict(l=20, r=20, t=60, b=20),
    )
    return fig
