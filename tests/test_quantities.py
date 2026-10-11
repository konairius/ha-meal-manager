"""Quantity parsing, unit normalization and plausibility."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from custom_components.meal_manager.core.catalog import parse_recipes
from custom_components.meal_manager.core.models import Ingredient
from custom_components.meal_manager.core.quantities import is_plausible, normalize, parse_quantity

RECIPES = Path(__file__).parents[1] / "custom_components" / "meal_manager" / "data" / "recipes.json"


@pytest.mark.parametrize(
    ("text", "expected"),
    [("2", 2), ("0,5", 0.5), ("1/2", 0.5), ("1 1/2", 1.5), ("½", 0.5), ("1½", 1.5), ("1-2", 1), ("x", None)],
)
def test_parse_quantity(text: str, expected: float | None) -> None:
    assert parse_quantity(text) == expected


def test_normalize_units() -> None:
    assert normalize(Ingredient("lemon", 1, "unit")).unit == "pcs"
    assert normalize(Ingredient("flour", 0.2, "kg")) == Ingredient("flour", 200, "g")
    assert normalize(Ingredient("oil", 2, "Tablespoons")).unit == "tbsp"
    assert normalize(Ingredient("thyme", 1, "sprig")).unit == "sprig"


@pytest.mark.parametrize(
    ("ingredient", "plausible"),
    [
        (Ingredient("lemon", 5, "pcs"), False),
        (Ingredient("lemon", 5, ""), False),
        (Ingredient("lemon", 0.5, "pcs"), True),
        (Ingredient("potatoes", 1000, "g"), False),
        (Ingredient("thyme", 20, "sprig"), True),
    ],
)
def test_plausibility(ingredient: Ingredient, plausible: bool) -> None:
    assert is_plausible(ingredient) is plausible


def test_bundled_recipes_are_plausible() -> None:
    recipes, errors = parse_recipes(json.loads(RECIPES.read_text()), "builtin")
    assert errors == []
    assert len(recipes) > 100


def test_user_recipe_with_whole_dish_amounts_is_skipped() -> None:
    raw = {
        "title": "Soup for everyone",
        "meal_types": ["dinner"],
        "effort": 2,
        "minutes": 40,
        "health": 4,
        "kcal": 400,
        "ingredients": [{"name": "potatoes", "quantity": 1500, "unit": "g"}],
    }
    recipes, errors = parse_recipes([raw], "user")
    assert recipes == [] and "potatoes" in errors[0]
