"""Quantity parsing, unit normalization and plausibility."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from custom_components.meal_manager.core.catalog import parse_recipes
from custom_components.meal_manager.core.models import Ingredient
from custom_components.meal_manager.core.quantities import is_plausible, parse_quantity, to_metric

RECIPES = Path(__file__).parents[1] / "custom_components" / "meal_manager" / "data" / "recipes.json"


@pytest.mark.parametrize(
    ("text", "expected"),
    [("2", 2), ("0,5", 0.5), ("1/2", 0.5), ("1 1/2", 1.5), ("½", 0.5), ("1½", 1.5), ("1-2", 1), ("x", None)],
)
def test_parse_quantity(text: str, expected: float | None) -> None:
    assert parse_quantity(text) == expected


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        (Ingredient("lemon", 1, "unit"), Ingredient("lemon", 1, "pcs")),
        (Ingredient("eggs", 2, ""), Ingredient("eggs", 2, "pcs")),
        (Ingredient("flour", 0.2, "kg"), Ingredient("flour", 200, "g")),
        (Ingredient("milk", 0.25, "l"), Ingredient("milk", 250, "ml")),
        (Ingredient("olive oil", 2, "Tablespoons"), Ingredient("olive oil", 30, "ml")),
        (Ingredient("sugar", 1, "tbsp"), Ingredient("sugar", 12, "g")),
        (Ingredient("salt", 1, "tsp"), Ingredient("salt", 4, "g")),
        (Ingredient("chopped parsley", 1, "tbsp"), Ingredient("chopped parsley", 3, "g")),
        (Ingredient("salt", 1, "pinch"), Ingredient("salt", 0.5, "g")),
        (Ingredient("garlic", 2, "cloves"), Ingredient("garlic clove", 2, "pcs")),
        (Ingredient("bacon", 2, "slice"), Ingredient("bacon slice", 2, "pcs")),
    ],
)
def test_to_metric(given: Ingredient, expected: Ingredient) -> None:
    assert to_metric(given) == expected


@pytest.mark.parametrize(
    ("ingredient", "plausible"),
    [
        (Ingredient("lemon", 5, "pcs"), False),
        (Ingredient("lemon", 5, ""), False),
        (Ingredient("lemon", 0.5, "pcs"), True),
        (Ingredient("potatoes", 1000, "g"), False),
        (Ingredient("garlic clove", 6, "pcs"), False),
        (Ingredient("olive oil", 15, "ml"), True),
    ],
)
def test_plausibility(ingredient: Ingredient, plausible: bool) -> None:
    assert is_plausible(ingredient) is plausible


def test_bundled_recipes_are_plausible_and_metric() -> None:
    raw = json.loads(RECIPES.read_text())
    assert {i["unit"] for r in raw for i in r["ingredients"]} <= {"g", "ml", "pcs"}
    recipes, errors = parse_recipes(raw, "builtin")
    assert errors == []
    assert len(recipes) > 100


def test_user_recipe_units_become_metric() -> None:
    raw = {
        "title": "Toast",
        "meal_types": ["breakfast"],
        "effort": 1,
        "minutes": 5,
        "health": 3,
        "kcal": 300,
        "ingredients": [{"name": "butter", "quantity": 1, "unit": "tbsp"}],
    }
    recipes, _ = parse_recipes([raw], "user")
    assert recipes[0].ingredients[0] == Ingredient("butter", 12, "g")


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
