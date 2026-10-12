"""Shopping list: products one can actually buy for the uncooked meals.

Ingredients are merged and pantry staples (salt, oil, spices, water, ...) are left out. Known
ingredients become packages ("2 x Dose 400 ml", "1 x Bund"), loose produce is rounded up to
whole pieces or a weight one can ask for, names are translated, and items are ordered by
supermarket section.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import math

from .ingredients import IngredientCatalog, IngredientInfo, Package
from .models import Ingredient

# Supermarket walk; unknown ingredients go last.
CATEGORIES = (
    "produce",
    "herbs",
    "bakery",
    "meat",
    "fish",
    "dairy",
    "frozen",
    "dry",
    "spices",
    "drinks",
    "other",
)

# Left out unless the household changes it. Entries match an ingredient name (English or
# translated) or a category.
DEFAULT_PANTRY = (
    "water",
    "salt",
    "pepper",
    "black pepper",
    "spices",
    "olive oil",
    "sunflower oil",
    "vegetable oil",
    "rapeseed oil",
    "vinegar",
    "white wine vinegar",
    "balsamic vinegar",
    "flour",
    "sugar",
    "brown sugar",
    "powdered sugar",
    "baking powder",
    "dry yeast",
    "soy sauce",
    "mustard",
    "ketchup",
)

_PIECES = {"en": "pcs", "de": "Stück"}


@dataclass(frozen=True, slots=True)
class ShoppingItem:
    name: str
    amount: str  # e.g. "2 kg", "3 Stk.", "1 Bund"
    category: str

    def display(self) -> str:
        """E.g. "Kokosmilch: 2 x Dose 400 ml"; name first so the list reads by product."""
        return f"{self.name}: {self.amount}" if self.amount else self.name


def parse_pantry(text: str) -> frozenset[str]:
    """'salt, pepper\\nolive oil' -> {'salt', 'pepper', 'olive oil'}."""
    return frozenset(p.strip().casefold() for p in text.replace("\n", ",").split(",") if p.strip())


def _round_up(quantity: float) -> float:
    """Round a weight or volume up to a size that is sold or easily measured."""
    for limit, step in ((50, 5), (250, 10), (1000, 50)):
        if quantity <= limit:
            return math.ceil(quantity / step - 1e-9) * step
    return math.ceil(quantity / 500 - 1e-9) * 500


def _amount(quantity: float, unit: str, package: Package | None, language: str) -> str:
    if package and package.unit == unit:
        count = max(1, math.ceil(quantity / package.size - 1e-9))
        return f"{count} × {package.labels.get(language) or package.labels.get('en', '')}".strip()
    if unit == "pcs":
        return f"{max(1, math.ceil(quantity - 1e-9))} {_PIECES.get(language, 'pcs')}"
    if unit in ("g", "ml"):
        rounded = _round_up(quantity)
        if rounded >= 1000:
            big = "kg" if unit == "g" else "l"
            text = f"{rounded / 1000:.1f}".rstrip("0").rstrip(".")
            return f"{text.replace('.', ',') if language == 'de' else text} {big}"
        return f"{rounded:g} {unit}"
    return f"{quantity:g} {unit}".strip()


def build_shopping_list(
    ingredients: Iterable[Ingredient],
    catalog: IngredientCatalog,
    pantry: frozenset[str] = frozenset(DEFAULT_PANTRY),
    language: str = "en",
) -> list[ShoppingItem]:
    """Merge, filter, round, translate and order the ingredients of the meals to shop for."""
    totals: dict[tuple[str, str], float] = {}
    for item in ingredients:
        name = catalog.resolve(item.name) or " ".join(item.name.casefold().split())
        key = (name, item.unit)
        totals[key] = totals.get(key, 0.0) + item.quantity

    items: list[ShoppingItem] = []
    for (name, unit), quantity in totals.items():
        info = catalog.get(name, IngredientInfo())
        local = info.names.get(language) or name
        if {name, local.casefold(), info.category} & pantry or quantity <= 0:
            continue
        category = info.category if info.category in CATEGORIES else "other"
        items.append(ShoppingItem(local, _amount(quantity, unit, info.package, language), category))
    return sorted(items, key=lambda i: (CATEGORIES.index(i.category), i.name.casefold()))
