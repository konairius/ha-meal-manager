"""Seasonal produce (Central Europe): which fresh ingredients are local in which month."""

from __future__ import annotations

from collections.abc import Iterable

from .models import Recipe, SeasonMode

__all__ = ["SEASONS", "SeasonMode", "out_of_season", "produce_out_of_season", "recipe_out_of_season"]


def _months(*ranges: tuple[int, int]) -> frozenset[int]:
    months: set[int] = set()
    for start, end in ranges:
        month = start
        while True:
            months.add(month)
            if month == end:
                break
            month = month % 12 + 1
    return frozenset(months)


# Fresh produce with a clear local season in Central Europe (outdoor harvest and storage).
# Keys are matched as substrings of the ingredient name. Imported staples (banana, lemon,
# avocado) and storage vegetables available all year (onion, carrot, cabbage) are not listed.
SEASONS: dict[str, frozenset[int]] = {
    "asparagus": _months((4, 6)),
    "spargel": _months((4, 6)),
    "rhubarb": _months((4, 6)),
    "strawberr": _months((5, 7)),
    "cherries": _months((6, 7)),
    "raspberr": _months((6, 9)),
    "blueberr": _months((6, 9)),
    "berries": _months((6, 9)),
    "plum": _months((7, 10)),
    "grapes": _months((8, 10)),
    "tomato": _months((7, 10)),
    "zucchini": _months((6, 10)),
    "courgette": _months((6, 10)),
    "eggplant": _months((7, 10)),
    "aubergine": _months((7, 10)),
    "bell pepper": _months((7, 10)),
    "cucumber": _months((6, 9)),
    "green beans": _months((7, 10)),
    "broad beans": _months((6, 8)),
    "fresh peas": _months((6, 8)),
    "corn on the cob": _months((8, 10)),
    "broccoli": _months((6, 11)),
    "cauliflower": _months((6, 11)),
    "spinach": _months((3, 6), (9, 11)),
    "rocket": _months((4, 10)),
    "arugula": _months((4, 10)),
    "lettuce": _months((5, 10)),
    "radish": _months((4, 10)),
    "kohlrabi": _months((5, 10)),
    "pumpkin": _months((8, 12)),
    "squash": _months((8, 12)),
    "brussels sprouts": _months((10, 3)),
    "kale": _months((10, 3)),
    "chanterelle": _months((7, 10)),
    "wild garlic": _months((3, 5)),
    "elderflower": _months((5, 6)),
}

# Preserved forms are available all year.
_PRESERVED = (
    "canned",
    "frozen",
    "dried",
    "paste",
    "passata",
    "sauce",
    "ketchup",
    "jam",
    "juice",
    "pickled",
    "puree",
    "powder",
    "flakes",
    "seeds",
)


def _seasonal_key(name: str) -> str | None:
    lowered = name.casefold()
    if any(word in lowered for word in _PRESERVED):
        return None
    return next((key for key in SEASONS if key in lowered), None)


def out_of_season(names: Iterable[str], month: int) -> list[str]:
    """The ingredient names that are fresh produce out of season in the given month."""
    return [n for n in names if (key := _seasonal_key(n)) and month not in SEASONS[key]]


def recipe_out_of_season(recipe: Recipe, month: int) -> list[str]:
    return out_of_season((i.name for i in recipe.ingredients), month)


def produce_out_of_season(month: int) -> list[str]:
    """Example produce to avoid in a month (for prompts)."""
    return [key for key, months in SEASONS.items() if month not in months]
