"""Units and quantities of ingredients: parsing, normalization and plausibility."""

from __future__ import annotations

import re

from .models import Ingredient

# Canonical units and the factor to convert an alias into them.
UNIT_ALIASES: dict[str, tuple[str, float]] = {
    "g": ("g", 1),
    "gram": ("g", 1),
    "grams": ("g", 1),
    "kg": ("g", 1000),
    "ml": ("ml", 1),
    "milliliter": ("ml", 1),
    "milliliters": ("ml", 1),
    "cl": ("ml", 10),
    "dl": ("ml", 100),
    "l": ("ml", 1000),
    "liter": ("ml", 1000),
    "litre": ("ml", 1000),
    "pcs": ("pcs", 1),
    "pc": ("pcs", 1),
    "piece": ("pcs", 1),
    "pieces": ("pcs", 1),
    "unit": ("pcs", 1),
    "units": ("pcs", 1),
    "whole": ("pcs", 1),
    "x": ("pcs", 1),
    "tbsp": ("tbsp", 1),
    "tablespoon": ("tbsp", 1),
    "tablespoons": ("tbsp", 1),
    "el": ("tbsp", 1),
    "tsp": ("tsp", 1),
    "teaspoon": ("tsp", 1),
    "teaspoons": ("tsp", 1),
    "tl": ("tsp", 1),
    "clove": ("clove", 1),
    "cloves": ("clove", 1),
    "pinch": ("pinch", 1),
    "pinches": ("pinch", 1),
    "slice": ("slice", 1),
    "slices": ("slice", 1),
}

# Largest believable amount for ONE portion. Model output above this is almost always an
# amount for the whole dish or a misread number (e.g. 5 lemons per portion).
MAX_PER_PORTION: dict[str, float] = {
    "g": 600,
    "ml": 750,
    "pcs": 4,
    "tbsp": 5,
    "tsp": 5,
    "clove": 4,
    "pinch": 3,
    "slice": 5,
}

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


def normalize(ingredient: Ingredient) -> Ingredient:
    """Canonical unit (g, ml, pcs, tbsp, ...), converting kg/l; unknown units stay as they are."""
    alias = ingredient.unit.strip().casefold().rstrip(".")
    if alias not in UNIT_ALIASES:
        return Ingredient(ingredient.name.strip(), ingredient.quantity, ingredient.unit.strip())
    unit, factor = UNIT_ALIASES[alias]
    return Ingredient(ingredient.name.strip(), ingredient.quantity * factor, unit)


def is_plausible(ingredient: Ingredient) -> bool:
    """Whether a per-portion amount is believable. No unit counts pieces; unknown units pass."""
    if ingredient.quantity < 0:
        return False
    limit = MAX_PER_PORTION.get(ingredient.unit or "pcs")
    return limit is None or ingredient.quantity <= limit
