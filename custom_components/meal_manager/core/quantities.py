"""Quantities of ingredients: parsing and plausibility. Amounts are in g, ml or pcs only."""

from __future__ import annotations

import re

from .models import Ingredient

METRIC_UNITS = ("g", "ml", "pcs")

# Largest believable amount for ONE portion. Model output above this is almost always an
# amount for the whole dish or a misread number (e.g. 5 lemons per portion).
MAX_PER_PORTION: dict[str, float] = {"g": 600, "ml": 750, "pcs": 4}

_VULGAR = {"½": 0.5, "⅓": 1 / 3, "⅔": 2 / 3, "¼": 0.25, "¾": 0.75, "⅛": 0.125}
_MIXED = re.compile(r"(\d+)\s+(\d+)\s*/\s*(\d+)")
_FRACTION = re.compile(r"(\d+)\s*/\s*(\d+)")
_WITH_VULGAR = re.compile(r"(\d+)?\s*([½⅓⅔¼¾⅛])")
_DECIMAL = re.compile(r"\d+(?:[.,]\d+)?")


def parse_quantity(text: str) -> float | None:
    """Parse '1', '0,5', '1/2', '1 1/2', '½', '1½' or a range '1-2' (first value)."""
    text = str(text)
    if match := _MIXED.search(text):
        whole, num, den = (int(g) for g in match.groups())
        return whole + num / den if den else None
    if match := _FRACTION.search(text):
        num, den = (int(g) for g in match.groups())
        return num / den if den else None
    if match := _WITH_VULGAR.search(text):
        return int(match.group(1) or 0) + _VULGAR[match.group(2)]
    if match := _DECIMAL.search(text):
        return float(match.group().replace(",", "."))
    return None


def is_plausible(ingredient: Ingredient) -> bool:
    """Whether a per-portion amount is believable; units that are not metric are not judged."""
    if ingredient.quantity < 0:
        return False
    limit = MAX_PER_PORTION.get(ingredient.unit or "pcs")
    return limit is None or ingredient.quantity <= limit
