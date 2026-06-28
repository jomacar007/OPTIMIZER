"""Utility types and validation helpers for the Portfolio Optimizer.

This module defines the shared data structures used across the app
(prices, investments, results) and the validation logic for user input.
Keeping these separate from the UI and the optimization logic makes the
core domain model easy to test and reuse.

Version 2 adds support for a "percentage bars" mode: the user moves three
independent sliders (one per outcome) that do not need to sum to 100% on
their own — they get normalized automatically.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

OUTCOME_LABELS: Tuple[str, str, str] = ("Gana Equipo A", "Empate", "Gana Equipo B")


@dataclass(frozen=True)
class MarketPrices:
    """Prices (YES probability, in (0, 1)) for the three market outcomes."""

    price_a: float
    price_draw: float
    price_b: float

    def as_list(self) -> List[float]:
        """Return the three prices as a list, in [A, Draw, B] order."""
        return [self.price_a, self.price_draw, self.price_b]


@dataclass(frozen=True)
class ValidationResult:
    """Result of validating user input.

    Attributes:
        is_valid: True if all checks passed.
        errors: List of human-readable error messages. Empty if valid.
    """

    is_valid: bool
    errors: List[str]


def validate_prices(prices: MarketPrices) -> ValidationResult:
    """Validate that all three prices are strictly between 0 and 1.

    Args:
        prices: The market prices to validate.

    Returns:
        A ValidationResult describing whether the prices are valid and,
        if not, why.
    """
    errors: List[str] = []
    for label, value in zip(OUTCOME_LABELS, prices.as_list()):
        if value <= 0:
            errors.append(f"El precio de '{label}' debe ser mayor que 0.")
        if value >= 1:
            errors.append(f"El precio de '{label}' debe ser menor que 1.")
    return ValidationResult(is_valid=len(errors) == 0, errors=errors)


def validate_capital(capital: float) -> ValidationResult:
    """Validate that capital is a strictly positive number.

    Args:
        capital: The total capital available to invest.

    Returns:
        A ValidationResult describing whether the capital is valid.
    """
    errors: List[str] = []
    if capital <= 0:
        errors.append("El capital disponible debe ser mayor que 0.")
    return ValidationResult(is_valid=len(errors) == 0, errors=errors)


def validate_investments(
    investments: List[float], capital: float, tolerance: float = 1e-6
) -> ValidationResult:
    """Validate manual investments: non-negative and not exceeding capital.

    Args:
        investments: Proposed investment amounts for [A, Draw, B].
        capital: Total capital available.
        tolerance: Numerical tolerance when comparing the sum to capital.

    Returns:
        A ValidationResult. Note that under-allocating capital is allowed
        (treated as leaving money uninvested) and only flagged informationally
        by the UI layer, not as a hard error here.
    """
    errors: List[str] = []
    for label, value in zip(OUTCOME_LABELS, investments):
        if value < 0:
            errors.append(f"La inversión en '{label}' no puede ser negativa.")

    total = sum(investments)
    if total > capital + tolerance:
        errors.append(
            f"La inversión total ({total:.2f}) supera el capital disponible "
            f"({capital:.2f})."
        )
    return ValidationResult(is_valid=len(errors) == 0, errors=errors)


def validate_minimums(minimums: List[float], capital: float) -> ValidationResult:
    """Validate per-outcome minimum investments used to constrain Mode 3.

    Args:
        minimums: Minimum investment required for [A, Draw, B].
        capital: Total capital available.

    Returns:
        A ValidationResult flagging negative minimums or minimums whose
        sum exceeds the available capital (which would make the problem
        infeasible).
    """
    errors: List[str] = []
    for label, value in zip(OUTCOME_LABELS, minimums):
        if value < 0:
            errors.append(f"El mínimo para '{label}' no puede ser negativo.")

    if sum(minimums) > capital:
        errors.append(
            "La suma de los mínimos por resultado supera el capital disponible; "
            "el problema no tiene solución factible."
        )
    return ValidationResult(is_valid=len(errors) == 0, errors=errors)


def validate_percentages(percentages: List[float]) -> ValidationResult:
    """Validate the three raw percentage-bar values before normalization.

    Each bar is independent and does not need to sum to 100 — that is
    handled by `normalize_percentages`. The only hard requirements are
    that values are non-negative and that at least one bar is above zero
    (otherwise there is nothing to normalize against).

    Args:
        percentages: Raw slider values for [A, Draw, B], each typically
            in [0, 100] but only non-negativity is enforced here.

    Returns:
        A ValidationResult describing whether the percentages are usable.
    """
    errors: List[str] = []
    for label, value in zip(OUTCOME_LABELS, percentages):
        if value < 0:
            errors.append(f"El porcentaje de '{label}' no puede ser negativo.")

    if sum(percentages) <= 0:
        errors.append(
            "Sube al menos una de las tres barras por encima de 0% para "
            "poder calcular un reparto."
        )
    return ValidationResult(is_valid=len(errors) == 0, errors=errors)


def normalize_percentages(percentages: List[float]) -> List[float]:
    """Normalize three independent percentage-bar values so they sum to 1.0.

    This is the core logic behind "Mode 2: percentage bars". The user can
    move each of the three sliders independently (e.g. 16, 26, 80, which
    sum to 122), and this function rescales them proportionally so they
    represent a valid capital split that sums to exactly 100%.

    Args:
        percentages: Raw slider values for [A, Draw, B]. Must sum to a
            strictly positive number (validated beforehand).

    Returns:
        A list of three fractions in [0, 1] that sum to 1.0, in the same
        [A, Draw, B] order.

    Raises:
        ValueError: If the percentages sum to zero or less.
    """
    total = sum(percentages)
    if total <= 0:
        raise ValueError(
            "No se puede normalizar: la suma de los porcentajes debe ser mayor que 0."
        )
    return [p / total for p in percentages]


def percentages_to_investments(
    percentages: List[float], capital: float
) -> List[float]:
    """Convert raw (possibly non-normalized) percentage bars into USD amounts.

    Args:
        percentages: Raw slider values for [A, Draw, B].
        capital: Total capital available to invest.

    Returns:
        A list of investment amounts in USD for [A, Draw, B] that sum
        exactly to `capital`.
    """
    fractions = normalize_percentages(percentages)
    return [f * capital for f in fractions]
