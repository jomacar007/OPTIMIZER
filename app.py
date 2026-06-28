"""Portfolio Optimizer v3 — Streamlit app.

A calculator for splitting capital across a 3-outcome market
(Equipo A / Empate / Equipo B), inspired by Polymarket-style markets.

Four modes:
1. Manual (USD)       — exact dollar amounts per outcome.
2. Barras %           — three independent sliders, normalized to 100%.
3. Maximin            — scipy-optimized split maximizing the worst case
                         across all three outcomes.
4. Sacrificar uno      — sacrifice one outcome (cap its investment, often
                         zero) and let the optimizer maximize the worst
                         case across the other two only. Models the
                         common "go with the favorite, hedge the draw"
                         strategy.

Run with:
    streamlit run app.py
"""

from __future__ import annotations

from typing import List

import pandas as pd
import streamlit as st

from calculator import ScenarioResult, compute_scenario_result
from optimizer import solve_maximin, solve_maximin_sacrifice
from plots import build_investment_pie_chart, build_profit_bar_chart
from utils import (
    MarketPrices,
    OUTCOME_LABELS,
    normalize_percentages,
    percentages_to_investments,
    validate_capital,
    validate_investments,
    validate_minimums,
    validate_percentages,
    validate_prices,
)

st.set_page_config(
    page_title="Portfolio Optimizer v3",
    page_icon="📊",
    layout="wide",
)

MODE_MANUAL = "Manual (USD)"
MODE_PERCENT = "Barras de porcentaje"
MODE_MAXIMIN = "Maximin (3 resultados)"
MODE_SACRIFICE = "Sacrificar un resultado"


def render_sidebar() -> tuple[MarketPrices, float, str]:
    """Render the sidebar inputs and return the chosen configuration.

    Returns:
        A tuple of (prices, capital, mode).
    """
    st.sidebar.header("Configuración del mercado")

    capital = st.sidebar.number_input(
        "Capital disponible (USD)", min_value=0.0, value=100.0, step=10.0
    )

    st.sidebar.subheader("Precios (YES, entre 0 y 1)")
    price_a = st.sidebar.number_input(
        "Precio Equipo A", min_value=0.0, max_value=1.0, value=0.16, step=0.01
    )
    price_draw = st.sidebar.number_input(
        "Precio Empate", min_value=0.0, max_value=1.0, value=0.26, step=0.01
    )
    price_b = st.sidebar.number_input(
        "Precio Equipo B", min_value=0.0, max_value=1.0, value=0.59, step=0.01
    )

    st.sidebar.subheader("Modo")
    mode = st.sidebar.radio(
        "Selecciona el modo de cálculo",
        options=[MODE_MANUAL, MODE_PERCENT, MODE_MAXIMIN, MODE_SACRIFICE],
        help=(
            "Manual (USD): decides el monto exacto en dólares por resultado.\n"
            "Barras de porcentaje: tres sliders independientes normalizados "
            "a 100%.\n"
            "Maximin: el optimizador reparte el capital para maximizar el "
            "peor escenario posible entre los tres resultados.\n"
            "Sacrificar un resultado: tú eliges un resultado al que le pones "
            "un tope de inversión (a menudo 0), y el optimizador reparte el "
            "resto para maximizar el peor caso solo entre los otros dos."
        ),
    )

    prices = MarketPrices(price_a=price_a, price_draw=price_draw, price_b=price_b)
    return prices, capital, mode


def render_manual_inputs(capital: float) -> List[float]:
    """Render manual USD investment inputs and return the chosen amounts."""
    st.subheader("Inversión manual por resultado (USD)")
    cols = st.columns(3)
    default = capital / 3 if capital > 0 else 0.0
    with cols[0]:
        inv_a = st.number_input("Inversión en Equipo A", min_value=0.0, value=default)
    with cols[1]:
        inv_draw = st.number_input("Inversión en Empate", min_value=0.0, value=default)
    with cols[2]:
        inv_b = st.number_input("Inversión en Equipo B", min_value=0.0, value=default)
    return [inv_a, inv_draw, inv_b]


def render_percentage_bars(capital: float) -> List[float]:
    """Render three independent percentage sliders and return USD amounts."""
    st.subheader("Barras de porcentaje (se normalizan automáticamente)")
    st.caption(
        "Mueve cualquiera de las tres barras. Si su suma no es 100%, los "
        "montos en USD se reparten de forma proporcional para que sigan "
        "sumando el capital total."
    )

    pct_a = st.slider("% Equipo A", min_value=0, max_value=100, value=16)
    pct_draw = st.slider("% Empate", min_value=0, max_value=100, value=26)
    pct_b = st.slider("% Equipo B", min_value=0, max_value=100, value=58)

    raw_percentages = [float(pct_a), float(pct_draw), float(pct_b)]

    pct_validation = validate_percentages(raw_percentages)
    for error in pct_validation.errors:
        st.error(error)
    if not pct_validation.is_valid:
        st.stop()

    raw_sum = sum(raw_percentages)
    normalized = normalize_percentages(raw_percentages)
    st.info(
        f"Suma cruda de las barras: {raw_sum:.0f}% → normalizado a 100% → "
        f"A {normalized[0] * 100:.1f}% · Empate {normalized[1] * 100:.1f}% · "
        f"B {normalized[2] * 100:.1f}%"
    )

    return percentages_to_investments(raw_percentages, capital)


def render_minimums_inputs() -> List[float]:
    """Render optional per-outcome minimum investment inputs for Maximin mode."""
    with st.expander("Restricciones avanzadas: mínimo por resultado (opcional)"):
        st.caption(
            "Fuerza al optimizador a mantener al menos esta inversión en cada "
            "resultado, incluso si el criterio maximin preferiría invertir 0."
        )
        cols = st.columns(3)
        with cols[0]:
            min_a = st.number_input("Mínimo en Equipo A", min_value=0.0, value=0.0)
        with cols[1]:
            min_draw = st.number_input("Mínimo en Empate", min_value=0.0, value=0.0)
        with cols[2]:
            min_b = st.number_input("Mínimo en Equipo B", min_value=0.0, value=0.0)
    return [min_a, min_draw, min_b]


def render_sacrifice_controls(capital: float) -> tuple[int, float]:
    """Render the sacrifice-mode controls: which outcome, and how much.

    Args:
        capital: Total capital available, used to bound the risk slider.

    Returns:
        A tuple (sacrifice_index, sacrifice_amount) where sacrifice_index
        is 0 (A), 1 (Draw), or 2 (B).
    """
    st.subheader("Sacrificar un resultado")
    st.caption(
        "Elige el resultado que crees menos probable. El optimizador reparte "
        "el resto del capital entre los otros dos para igualar y maximizar "
        "su ganancia conjunta (maximin entre esos dos), dejando la pérdida "
        "del resultado sacrificado acotada a lo que tú decidas arriesgar ahí."
    )

    outcome_choice = st.radio(
        "Resultado a sacrificar",
        options=list(OUTCOME_LABELS),
        horizontal=True,
    )
    sacrifice_index = OUTCOME_LABELS.index(outcome_choice)

    sacrifice_pct = st.slider(
        f"Máximo a arriesgar en '{outcome_choice}' (% del capital)",
        min_value=0,
        max_value=100,
        value=0,
    )
    sacrifice_amount = capital * (sacrifice_pct / 100)
    st.caption(f"Monto fijado en '{outcome_choice}': ${sacrifice_amount:,.2f}")

    return sacrifice_index, sacrifice_amount


def render_results_table(result: ScenarioResult) -> None:
    """Render the per-scenario results table."""
    df = pd.DataFrame(
        {
            "Resultado": result.labels,
            "Inversión": [f"${v:,.2f}" for v in result.investments],
            "Acciones": [f"{v:,.2f}" for v in result.shares],
            "Cobro": [f"${v:,.2f}" for v in result.payout_per_scenario],
            "Ganancia": [f"${v:,.2f}" for v in result.profit_per_scenario],
            "ROI": [f"{v * 100:,.1f}%" for v in result.roi_per_scenario],
        }
    )
    st.dataframe(df, hide_index=True, use_container_width=True)


def render_summary_metrics(result: ScenarioResult) -> None:
    """Render top-line summary metrics: total invested, max/min profit and ROI."""
    cols = st.columns(4)
    cols[0].metric("Inversión total", f"${result.total_invested:,.2f}")
    cols[1].metric("Beneficio máximo", f"${result.max_profit:,.2f}")
    cols[2].metric("Pérdida máxima", f"${result.max_loss:,.2f}")
    cols[3].metric(
        "ROI (mín / máx)",
        f"{result.min_roi * 100:,.1f}% / {result.max_roi * 100:,.1f}%",
    )


def main() -> None:
    """Entry point for the Streamlit app."""
    st.title("📊 Portfolio Optimizer v3")
    st.caption(
        "Calculadora de reparto de capital para mercados de 3 resultados "
        "(estilo Polymarket): Equipo A · Empate · Equipo B."
    )

    prices, capital, mode = render_sidebar()

    price_validation = validate_prices(prices)
    capital_validation = validate_capital(capital)

    for error in price_validation.errors + capital_validation.errors:
        st.error(error)
    if not (price_validation.is_valid and capital_validation.is_valid):
        st.stop()

    st.divider()

    if mode == MODE_MANUAL:
        investments = render_manual_inputs(capital)
        inv_validation = validate_investments(investments, capital)
        for error in inv_validation.errors:
            st.error(error)
        if not inv_validation.is_valid:
            st.stop()

        unallocated = capital - sum(investments)
        if unallocated > 0.01:
            st.info(f"Capital sin asignar: ${unallocated:,.2f}")

        result = compute_scenario_result(prices, investments)
        distribution_title = "Distribución utilizada"

    elif mode == MODE_PERCENT:
        investments = render_percentage_bars(capital)
        result = compute_scenario_result(prices, investments)
        distribution_title = "Distribución resultante de las barras"

    elif mode == MODE_MAXIMIN:
        minimums = render_minimums_inputs()
        min_validation = validate_minimums(minimums, capital)
        for error in min_validation.errors:
            st.error(error)
        if not min_validation.is_valid:
            st.stop()

        opt_result = solve_maximin(prices, capital, minimums)
        if not opt_result.success:
            st.error(
                f"El optimizador no encontró una solución factible: "
                f"{opt_result.message}"
            )
            st.stop()

        st.success(
            "Distribución óptima encontrada (maximin: maximiza el peor "
            "escenario posible entre los tres resultados)."
        )
        result = compute_scenario_result(prices, opt_result.investments)
        distribution_title = "Distribución recomendada"

    else:  # MODE_SACRIFICE
        sacrifice_index, sacrifice_amount = render_sacrifice_controls(capital)

        try:
            opt_result, sacrificed_profit = solve_maximin_sacrifice(
                prices, capital, sacrifice_index, sacrifice_amount
            )
        except ValueError as exc:
            st.error(str(exc))
            st.stop()

        if not opt_result.success:
            st.error(
                f"El optimizador no encontró una solución factible: "
                f"{opt_result.message}"
            )
            st.stop()

        sacrificed_label = OUTCOME_LABELS[sacrifice_index]
        st.success(
            f"Distribución encontrada: maximiza y prácticamente iguala la "
            f"ganancia entre los dos resultados no sacrificados. Si gana "
            f"'{sacrificed_label}', la pérdida queda acotada en "
            f"${abs(sacrificed_profit):,.2f}."
        )
        result = compute_scenario_result(prices, opt_result.investments)
        distribution_title = "Distribución recomendada"

    st.subheader("Resumen")
    render_summary_metrics(result)

    st.subheader(distribution_title)
    dist_cols = st.columns(3)
    for col, label, amount in zip(dist_cols, OUTCOME_LABELS, result.investments):
        col.metric(label, f"${amount:,.2f}")

    st.subheader("Tabla de resultados por escenario")
    render_results_table(result)

    st.subheader("Gráficos")
    chart_cols = st.columns(2)
    with chart_cols[0]:
        st.plotly_chart(build_profit_bar_chart(result), use_container_width=True)
    with chart_cols[1]:
        st.plotly_chart(build_investment_pie_chart(result), use_container_width=True)


if __name__ == "__main__":
    main()
