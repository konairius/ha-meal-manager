"""Units and quantities of ingredients: parsing, conversion to metric and plausibility.

Every amount ends up in g, ml or pcs. Spoons, cups and pinches are converted; cloves and
slices become pieces named after them ("garlic clove", "bacon slice").
"""

from __future__ import annotations

import re

from .models import Ingredient

METRIC_UNITS = ("g", "ml", "pcs")

# alias -> (metric unit, factor)
_DIRECT: dict[str, tuple[str, float]] = {
    "g": ("g", 1),
    "gr": ("g", 1),
    "gram": ("g", 1),
    "grams": ("g", 1),
    "gramm": ("g", 1),
    "kg": ("g", 1000),
    "ml": ("ml", 1),
    "milliliter": ("ml", 1),
    "milliliters": ("ml", 1),
    "cl": ("ml", 10),
    "dl": ("ml", 100),
    "l": ("ml", 1000),
    "liter": ("ml", 1000),
    "litre": ("ml", 1000),
    "cup": ("ml", 240),
    "cups": ("ml", 240),
    "pcs": ("pcs", 1),
    "pc": ("pcs", 1),
    "piece": ("pcs", 1),
    "pieces": ("pcs", 1),
    "stück": ("pcs", 1),
    "stk": ("pcs", 1),
    "unit": ("pcs", 1),
    "units": ("pcs", 1),
    "whole": ("pcs", 1),
    "x": ("pcs", 1),
    "pinch": ("g", 0.5),
    "pinches": ("g", 0.5),
    "prise": ("g", 0.5),
}

# Spoons: (ml if liquid, g otherwise, g for leafy herbs).
_SPOONS: dict[str, tuple[float, float, float]] = {
    "tbsp": (15, 12, 3),
    "tablespoon": (15, 12, 3),
    "tablespoons": (15, 12, 3),
    "el": (15, 12, 3),
    "tsp": (5, 4, 1),
    "teaspoon": (5, 4, 1),
    "teaspoons": (5, 4, 1),
    "tl": (5, 4, 1),
}

# Countable parts that become pieces with the part in the name.
_PARTS = {
    "clove": "clove",
    "cloves": "clove",
    "slice": "slice",
    "slices": "slice",
    "sprig": "sprig",
    "sprigs": "sprig",
}

_LIQUID_WORDS = (
    "oil",
    "vinegar",
    "juice",
    "sauce",
    "milk",
    "cream",
    "water",
    "broth",
    "stock",
    "wine",
    "syrup",
    "honey",
    "ketchup",
    "mayonnaise",
)
_HERB_WORDS = ("parsley", "dill", "chives", "basil", "coriander", "cilantro", "mint", "herbs")


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


def to_metric(ingredient: Ingredient) -> Ingredient:
    """Convert to g, ml or pcs. No unit means pieces; unknown units are kept as they are."""
    name = " ".join(ingredient.name.split())
    alias = ingredient.unit.strip().casefold().rstrip(".")
    quantity = ingredient.quantity
    if not alias:
        return Ingredient(name, quantity, "pcs")
    if alias in _DIRECT:
        unit, factor = _DIRECT[alias]
        return Ingredient(name, quantity * factor, unit)
    if alias in _SPOONS:
        liquid_ml, solid_g, herb_g = _SPOONS[alias]
        lowered = name.casefold()
        if any(word in lowered for word in _LIQUID_WORDS):
            return Ingredient(name, quantity * liquid_ml, "ml")
        grams = herb_g if any(word in lowered for word in _HERB_WORDS) else solid_g
        return Ingredient(name, quantity * grams, "g")
    if alias in _PARTS:
        part = _PARTS[alias]
        named = name if part in name.casefold() else f"{name} {part}"
        return Ingredient(named, quantity, "pcs")
    return Ingredient(name, quantity, ingredient.unit.strip())


def is_plausible(ingredient: Ingredient) -> bool:
    """Whether a per-portion amount is believable; units that are not metric are not judged."""
    if ingredient.quantity < 0:
        return False
    limit = MAX_PER_PORTION.get(ingredient.unit or "pcs")
    return limit is None or ingredient.quantity <= limit
