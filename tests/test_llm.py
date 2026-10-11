"""Parsing of local model output."""

from __future__ import annotations

from datetime import date

from custom_components.meal_manager.core.llm import build_instructions, parse_ingredient, parse_recipe
from custom_components.meal_manager.core.models import MealRequest, MealType

REQUEST = MealRequest(
    day=date(2026, 10, 12),
    slot="dinner",
    meal_type=MealType.DINNER,
    portions=2,
    effort=1,
    health=4,
    kcal_target=700,
    exclude=frozenset({"pizza"}),
)


def test_instructions_mention_constraints() -> None:
    text = build_instructions(REQUEST, "vegetarian")
    assert "700 kcal" in text and "vegetarian" in text and "pizza" in text


def test_parse_recipe_tolerant() -> None:
    recipe = parse_recipe(
        {
            "title": "Veggie Curry",
            "minutes": "about 25 min",
            "kcal": 650.0,
            "health": 7,
            "ingredients": "- 80 | g | rice\n2 tbsp curry paste\nsalt",
            "steps": "1. Cook rice.\n2) Make curry.",
        },
        REQUEST,
    )
    assert recipe.effort == 2 and recipe.minutes == 25 and recipe.health == 5
    assert [i.name for i in recipe.ingredients] == ["rice", "curry paste", "salt"]
    assert recipe.ingredients[1].unit == "tbsp"
    assert recipe.steps == ("Cook rice.", "Make curry.")


def test_parse_recipe_rejects_excluded_or_empty() -> None:
    assert parse_recipe({"title": "  PIZZA "}, REQUEST) is None
    assert parse_recipe({"title": ""}, REQUEST) is None
    assert parse_recipe("not a dict", REQUEST) is None


def test_parse_ingredient_plain() -> None:
    milk = parse_ingredient("0,25 l milk")
    assert (milk.quantity, milk.unit, milk.name) == (250, "ml", "milk")


def test_rejects_whole_dish_amounts() -> None:
    """A model answer like '5 | unit | lemon' per portion (10 lemons for two) is not used."""
    data = {
        "title": "Lemon Garlic Butter Salmon",
        "minutes": 30,
        "kcal": 450,
        "health": 3,
        "ingredients": "150 | g | salmon fillet\n5 | unit | lemon\n1 | clove | garlic",
        "steps": "Bake.",
    }
    assert parse_recipe(data, REQUEST) is None
    data["ingredients"] = "150 | g | salmon fillet\n1/2 | unit | lemon\n1 | cloves | garlic"
    recipe = parse_recipe(data, REQUEST)
    lemon = recipe.ingredients[1]
    assert (lemon.quantity, lemon.unit) == (0.5, "pcs")
    assert recipe.ingredients[2].unit == "clove"
