"""Maximin portfolio optimization for a 3-outcome market.

This module offers two optimization strategies, both solved as linear
programs via scipy.optimize.linprog:

1. `solve_maximin`: the classic maximin over all three outcomes. Finds
   the allocation that maximizes the worst-case profit across A, Draw,
   and B simultaneously.

2. `solve_maximin_sacrifice`: a variant where the user deliberately
   "sacrifices" one outcome (caps how much can be risked on it, often
   zero) and asks the optimizer to maximize the worst-case profit only
   across the *other two* outcomes. This models a common real-world
   strategy: "go with the favorite, hedge the draw, accept the loss if
   the clear underdog wins."

Mathematical formulation — full maximin (3 outcomes)
-----------------------------------------------------
Let x_i be the amount invested in outcome i, p_i its price, and C the
total capital.

    maximize   t
    subject to t <= x_i / p_i - C   for i = 1, 2, 3
               sum(x_i) = C
               x_i >= m_i  (per-outcome minimum, default 0)

Mathematical formulation — sacrifice variant (2 outcomes)
-----------------------------------------------------------
Let `s` be the sacrificed outcome with a fixed investment `x_s` (chosen
by the user, e.g. 0), and let `j`, `k` be the other two outcomes. The
remaining capital `C - x_s` is split between j and k to maximize the
worst case between *only those two*:

    maximize   t
    subject to t <= x_j / p_j - C
               t <= x_k / p_k - C
               x_j + x_k = C - x_s
               x_j, x_k >= 0

Note the profit constraints still subtract the *total* invested capital
C (including what was sunk into the sacrificed outcome), since that
money is genuinely at risk and lost if the sacrificed outcome does not
win. The sacrificed outcome's own profit is not part of the maximin
objective — it is allowed to be very negative (down to -x_s, i.e. losing
exactly what was risked there).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
from scipy.optimize import linprog

from utils import MarketPrices


@dataclass(frozen=True)
class OptimizationResult:
    """Result of a maximin optimization.

    Attributes:
        investments: Optimal amount invested in [A, Draw, B].
        worst_case_profit: The guaranteed (maximin) profit. For the full
            3-outcome maximin this is the worst profit across all three
            scenarios. For the sacrifice variant this is the worst profit
            across only the two non-sacrificed scenarios (the sacrificed
            scenario's profit is reported separately and may be lower).
        success: Whether the linear program converged to a solution.
        message: Solver status message (useful for debugging infeasibility).
    """

    investments: List[float]
    worst_case_profit: float
    success: bool
    message: str


def solve_maximin(
    prices: MarketPrices,
    capital: float,
    minimums: Optional[List[float]] = None,
) -> OptimizationResult:
    """Solve the full 3-outcome maximin capital allocation problem.

    Args:
        prices: Market prices for [A, Draw, B], each strictly in (0, 1).
        capital: Total capital available to invest. Must be > 0.
        minimums: Optional minimum investment per outcome [A, Draw, B].
            Defaults to [0, 0, 0] if not provided.

    Returns:
        An OptimizationResult with the optimal investments and the
        resulting guaranteed worst-case profit across all three outcomes.

    Raises:
        ValueError: If capital <= 0, if any price is outside (0, 1), or if
            the minimums sum to more than the available capital.
    """
    price_list = prices.as_list()
    _validate_common(price_list, capital)

    if minimums is None:
        minimums = [0.0, 0.0, 0.0]
    if len(minimums) != 3:
        raise ValueError("Se requieren exactamente 3 valores mínimos (A, Empate, B).")
    if any(m < 0 for m in minimums):
        raise ValueError("Los mínimos no pueden ser negativos.")
    if sum(minimums) > capital:
        raise ValueError(
            "La suma de los mínimos por resultado supera el capital disponible."
        )

    # Decision variables: [x_A, x_Draw, x_B, t]
    c = np.array([0.0, 0.0, 0.0, -1.0])

    a_ub = []
    b_ub = []
    for i, price in enumerate(price_list):
        row = [0.0, 0.0, 0.0, 0.0]
        row[i] = -1.0 / price
        row[3] = 1.0
        a_ub.append(row)
        b_ub.append(-capital)

    a_eq = [[1.0, 1.0, 1.0, 0.0]]
    b_eq = [capital]

    bounds = [
        (minimums[0], capital),
        (minimums[1], capital),
        (minimums[2], capital),
        (None, None),
    ]

    result = linprog(
        c,
        A_ub=np.array(a_ub),
        b_ub=np.array(b_ub),
        A_eq=np.array(a_eq),
        b_eq=np.array(b_eq),
        bounds=bounds,
        method="highs",
    )

    if not result.success:
        return OptimizationResult(
            investments=[0.0, 0.0, 0.0],
            worst_case_profit=0.0,
            success=False,
            message=result.message,
        )

    investments = [float(result.x[0]), float(result.x[1]), float(result.x[2])]
    worst_case_profit = float(result.x[3])
    investments = _rescale_to_capital(investments, capital)

    return OptimizationResult(
        investments=investments,
        worst_case_profit=worst_case_profit,
        success=True,
        message=result.message,
    )


def solve_maximin_sacrifice(
    prices: MarketPrices,
    capital: float,
    sacrifice_index: int,
    sacrifice_amount: float,
) -> Tuple[OptimizationResult, float]:
    """Solve a maximin problem that deliberately sacrifices one outcome.

    A fixed amount (`sacrifice_amount`, often 0) is committed to the
    sacrificed outcome. The remaining capital is split between the other
    two outcomes to maximize their worst-case profit (equalizing it where
    possible), exactly like the classic maximin but restricted to two
    outcomes. This models strategies like "go with the favorite, hedge
    the draw, accept the loss if the clear underdog wins."

    Args:
        prices: Market prices for [A, Draw, B], each strictly in (0, 1).
        capital: Total capital available to invest. Must be > 0.
        sacrifice_index: Index (0=A, 1=Draw, 2=B) of the outcome to
            sacrifice — i.e. exclude from the maximin objective.
        sacrifice_amount: Fixed amount to invest in the sacrificed
            outcome. Must be between 0 and capital.

    Returns:
        A tuple of (OptimizationResult, sacrificed_outcome_profit) where
        the OptimizationResult's `investments` list covers all three
        outcomes (sacrificed one included, at the fixed amount) and
        `worst_case_profit` is the guaranteed profit across the two
        non-sacrificed outcomes only. `sacrificed_outcome_profit` is the
        profit if the sacrificed outcome wins (it is allowed to be very
        negative and is reported separately since it is outside the
        maximin objective).

    Raises:
        ValueError: If capital <= 0, any price is outside (0, 1),
            sacrifice_index is not in {0, 1, 2}, or sacrifice_amount is
            outside [0, capital].
    """
    price_list = prices.as_list()
    _validate_common(price_list, capital)

    if sacrifice_index not in (0, 1, 2):
        raise ValueError("sacrifice_index debe ser 0 (A), 1 (Empate) o 2 (B).")
    if sacrifice_amount < 0 or sacrifice_amount > capital:
        raise ValueError(
            "El monto sacrificado debe estar entre 0 y el capital disponible."
        )

    other_indices = [i for i in range(3) if i != sacrifice_index]
    j, k = other_indices
    p_j, p_k = price_list[j], price_list[k]
    remaining = capital - sacrifice_amount

    # Decision variables: [x_j, x_k, t]
    c = np.array([0.0, 0.0, -1.0])

    # t <= x_j/p_j - C  =>  -x_j/p_j + t <= -C
    # t <= x_k/p_k - C  =>  -x_k/p_k + t <= -C
    a_ub = np.array(
        [
            [-1.0 / p_j, 0.0, 1.0],
            [0.0, -1.0 / p_k, 1.0],
        ]
    )
    b_ub = np.array([-capital, -capital])

    a_eq = np.array([[1.0, 1.0, 0.0]])
    b_eq = np.array([remaining])

    bounds = [(0.0, remaining), (0.0, remaining), (None, None)]

    result = linprog(
        c,
        A_ub=a_ub,
        b_ub=b_ub,
        A_eq=a_eq,
        b_eq=b_eq,
        bounds=bounds,
        method="highs",
    )

    if not result.success:
        return (
            OptimizationResult(
                investments=[0.0, 0.0, 0.0],
                worst_case_profit=0.0,
                success=False,
                message=result.message,
            ),
            0.0,
        )

    x_j, x_k, t = float(result.x[0]), float(result.x[1]), float(result.x[2])

    investments = [0.0, 0.0, 0.0]
    investments[sacrifice_index] = sacrifice_amount
    investments[j] = x_j
    investments[k] = x_k
    investments = _rescale_to_capital(investments, capital)

    sacrificed_shares = (
        investments[sacrifice_index] / price_list[sacrifice_index]
        if price_list[sacrifice_index] > 0
        else 0.0
    )
    sacrificed_profit = sacrificed_shares - capital

    return (
        OptimizationResult(
            investments=investments,
            worst_case_profit=t,
            success=True,
            message=result.message,
        ),
        sacrificed_profit,
    )


def _validate_common(price_list: List[float], capital: float) -> None:
    """Shared validation for both optimization entry points.

    Args:
        price_list: The three market prices, [A, Draw, B].
        capital: Total capital available.

    Raises:
        ValueError: If capital <= 0 or any price is outside (0, 1).
    """
    if capital <= 0:
        raise ValueError("El capital debe ser mayor que 0.")
    if any(p <= 0 or p >= 1 for p in price_list):
        raise ValueError("Todos los precios deben estar estrictamente entre 0 y 1.")


def _rescale_to_capital(investments: List[float], capital: float) -> List[float]:
    """Clip tiny negative solver noise and rescale so amounts sum to capital.

    Args:
        investments: Raw investment amounts from the solver.
        capital: Total capital that the investments should sum to.

    Returns:
        A cleaned-up list of investments summing exactly to `capital`
        (assuming the original sum was already close to it).
    """
    cleaned = [max(0.0, v) for v in investments]
    total = sum(cleaned)
    if total > 0:
        scale = capital / total
        cleaned = [v * scale for v in cleaned]
    return cleaned
