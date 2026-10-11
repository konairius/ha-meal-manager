"""Local recipe catalog: picks dishes from a bundled dataset, no network involved."""

from __future__ import annotations

from collections.abc import Iterable
import math
import random
import re
from typing import Any

from .models import MealRequest, MealType, Recipe

# Randomness added to every score so plans vary; larger = more variety, less precision.
VARIETY = 1.5


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.casefold()).strip("_")


def parse_recipes(items: Iterable[Any], source: str) -> tuple[list[Recipe], list[str]]:
    """Parse raw recipe dicts. Invalid entries are skipped and reported."""
    recipes: list[Recipe] = []
    errors: list[str] = []
    for index, item in enumerate(items):
        try:
            if not isinstance(item, dict):
                raise TypeError("not an object")
            data = dict(item)
            data.setdefault("id", f"{source}:{_slug(str(data['title']))}")
            data["source"] = source
            recipe = Recipe.from_dict(data)
            if not recipe.meal_types:
                raise ValueError("meal_types is empty")
            if not 1 <= recipe.effort <= 3 or not 1 <= recipe.health <= 5 or recipe.kcal <= 0:
                raise ValueError("effort must be 1-3, health 1-5, kcal > 0")
        except (KeyError, TypeError, ValueError) as err:
            errors.append(f"{source} recipe #{index + 1}: {err}")
            continue
        recipes.append(recipe)
    return recipes, errors


class RecipeCatalog:
    """A :class:`~.ports.RecipeSource` over an in-memory list of recipes."""

    def __init__(self, recipes: Iterable[Recipe], rng: random.Random | None = None) -> None:
        by_key: dict[str, Recipe] = {}
        for recipe in recipes:
            by_key[recipe.key] = recipe  # later sources (user recipes) win
        self._recipes = list(by_key.values())
        self._rng = rng or random.Random()

    @property
    def recipes(self) -> list[Recipe]:
        return list(self._recipes)

    def count(self, meal_type: MealType | None = None) -> int:
        return sum(1 for r in self._recipes if meal_type is None or meal_type in r.meal_types)

    async def suggest(self, request: MealRequest) -> Recipe | None:
        candidates = [
            r for r in self._recipes if request.meal_type in r.meal_types and r.key not in request.exclude
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda r: self.score(r, request) + self._rng.random() * VARIETY)

    @staticmethod
    def score(recipe: Recipe, request: MealRequest) -> float:
        """Penalty of a recipe for a request; lower is better."""
        penalty = abs(recipe.health - request.health)
        if recipe.effort > request.effort:
            penalty += 4 * (recipe.effort - request.effort)
        if request.kcal_target:
            ratio = request.kcal_target / recipe.kcal
            penalty += 2 * abs(math.log(ratio))
            if not MIN_SCALE <= ratio <= MAX_SCALE:
                penalty += 2
        if recipe.key in request.avoid:
            penalty += 3
        return penalty


MIN_SCALE = 0.75
MAX_SCALE = 1.5


def portion_scale(recipe: Recipe, kcal_target: int | None) -> float:
    """Portion size factor (in quarter steps) that brings a dish close to the calorie target."""
    if not kcal_target:
        return 1.0
    factor = min(MAX_SCALE, max(MIN_SCALE, kcal_target / recipe.kcal))
    return round(factor * 4) / 4
