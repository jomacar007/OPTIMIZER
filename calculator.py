"""Core payout and profitability calculations for a 3-outcome market.

This module is pure calculation logic (no Streamlit, no optimization).
Given prices and an investment per outcome, it derives shares purchased,
payouts under each possible outcome, profits, and ROI.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from utils import OUTCOME_LABELS, MarketPrices


@dataclass(frozen=True)
class ScenarioResult:
    """Outcome-by-outcome breakdown of a portfolio's payoff structure.

    Each list is indexed in [A, Draw, B] order and has length 3.

    Attributes:
        labels: Human-readable outcome names.
        investments: Amount invested in each outcome.
        shares: Contracts purchased in each outcome (investment / price).
        payouts_if_a: Total payout received under each scenario if A wins
            (only the A contracts pay out 1 USD each; this is the same
            value repeated for clarity in tabular form — see `payout_per_scenario`).
        total_invested: Sum of all investments.
        payout_per_scenario: Payout received *in that scenario* (i.e. the
            payout of the matching outcome's shares, since only the winning
            outcome pays 1 USD per share).
        profit_per_scenario: payout_per_scenario - total_invested.
        roi_per_scenario: profit_per_scenario / total_invested, as a fraction.
    """

    labels: List[str]
    investments: List[float]
    shares: List[float]
    total_invested: float
    payout_per_scenario: List[float]
    profit_per_scenario: List[float]
    roi_per_scenario: List[float]

    @property
    def max_profit(self) -> float:
        """Best-case profit across all scenarios."""
        return max(self.profit_per_scenario)

    @property
    def max_loss(self) -> float:
        """Worst-case profit across all scenarios (most negative, or smallest)."""
        return min(self.profit_per_scenario)

    @property
    def max_roi(self) -> float:
        """Best-case ROI across all scenarios."""
        return max(self.roi_per_scenario)

    @property
    def min_roi(self) -> float:
        """Worst-case ROI across all scenarios."""
        return min(self.roi_per_scenario)


def compute_shares(investments: List[float], prices: List[float]) -> List[float]:
    """Compute the number of contracts (shares) bought for each outcome.

    Each contract costs `price` and pays 1 USD if that outcome occurs, so
    shares = investment / price.

    Args:
        investments: Amount invested in each outcome, [A, Draw, B].
        prices: Price per contract for each outcome, [A, Draw, B].

    Returns:
        List of shares purchased for each outcome.

    Raises:
        ValueError: If any price is not strictly positive.
    """
    shares: List[float] = []
    for inv, price in zip(investments, prices):
        if price <= 0:
            raise ValueError("El precio debe ser mayor que 0 para calcular acciones.")
        shares.append(inv / price)
    return shares


def compute_scenario_result(
    prices: MarketPrices, investments: List[float]
) -> ScenarioResult:
    """Compute the full payoff breakdown for a given investment allocation.

    For each possible winning outcome, only the shares bought on *that*
    outcome pay out (1 USD per share); shares on the other two outcomes
    pay nothing. This function computes the payout, profit, and ROI for
    each of the three possible scenarios.

    Args:
        prices: The market prices for [A, Draw, B].
        investments: The amount invested in [A, Draw, B]. Must be the same
            length and order as prices.

    Returns:
        A ScenarioResult with the per-scenario breakdown.
    """
    price_list = prices.as_list()
    shares = compute_shares(investments, price_list)
    total_invested = sum(investments)

    # In scenario i, only shares[i] pay out (1 USD each).
    payout_per_scenario = [shares[i] * 1.0 for i in range(3)]
    profit_per_scenario = [payout_per_scenario[i] - total_invested for i in range(3)]

    roi_per_scenario = [
        (profit_per_scenario[i] / total_invested) if total_invested > 0 else 0.0
        for i in range(3)
    ]

    return ScenarioResult(
        labels=list(OUTCOME_LABELS),
        investments=list(investments),
        shares=shares,
        total_invested=total_invested,
        payout_per_scenario=payout_per_scenario,
        profit_per_scenario=profit_per_scenario,
        roi_per_scenario=roi_per_scenario,
    )
