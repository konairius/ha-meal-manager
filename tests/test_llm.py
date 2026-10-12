"""Parsing of local model output."""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from custom_components.meal_manager.core.llm import (
    RecipeRejected,
    build_instructions,
    check_recipe,
    parse_ingredient,
    parse_recipe,
    retry_instructions,
)
from custom_components.meal_manager.core.models import MealRequest, MealType, SeasonMode

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
            "ingredients": "- 80 | g | rice\n2. 30 | G | curry paste\n1/2 | pcs | onion",
            "steps": "1. Cook rice.\n2) Make curry.",
        },
        REQUEST,
    )
    assert recipe.effort == 2 and recipe.minutes == 25 and recipe.health == 5
    assert [(i.quantity, i.unit, i.name) for i in recipe.ingredients] == [
        (80, "g", "rice"),
        (30, "g", "curry paste"),
        (0.5, "pcs", "onion"),
    ]
    assert recipe.steps == ("Cook rice.", "Make curry.")


def test_parse_recipe_rejects_excluded_or_empty() -> None:
    assert parse_recipe({"title": "  PIZZA "}, REQUEST) is None
    assert parse_recipe({"title": ""}, REQUEST) is None
    assert parse_recipe("not a dict", REQUEST) is None


@pytest.mark.parametrize(
    "line",
    [
        "5 | unit | lemon",
        "2 | tbsp | olive oil",
        "1 | clove | garlic",
        "0,25 l milk",
        "salt",
        "x | g | rice",
        "0 | g | rice",
    ],
)
def test_parse_ingredient_rejects_anything_but_metric(line: str) -> None:
    assert parse_ingredient(line) is None


def test_rejects_wrong_units_and_whole_dish_amounts() -> None:
    """'5 | unit | lemon' is a malformed answer, '5 | pcs | lemon' an implausible one: both retried."""
    data = {
        "title": "Lemon Garlic Butter Salmon",
        "minutes": 30,
        "kcal": 450,
        "health": 3,
        "ingredients": "150 | g | salmon fillet\n5 | unit | lemon\n1 | pcs | garlic clove",
        "steps": "Bake.",
    }
    assert parse_recipe(data, REQUEST) is None
    data["ingredients"] = "150 | g | salmon fillet\n5 | pcs | lemon"
    assert parse_recipe(data, REQUEST) is None
    data["ingredients"] = "150 | g | salmon fillet\n15 | ml | lemon juice\n1 | pcs | garlic clove"
    recipe = parse_recipe(data, REQUEST)
    assert [i.unit for i in recipe.ingredients] == ["g", "ml", "pcs"]


def test_out_of_season_dish_is_rejected_when_strict() -> None:
    data = {
        "title": "Salmon with asparagus",
        "minutes": 30,
        "ingredients": "150 | g | salmon fillet\n150 | g | green asparagus",
    }
    assert parse_recipe(data, replace(REQUEST, season=SeasonMode.STRICT)) is None
    assert parse_recipe(data, replace(REQUEST, season=SeasonMode.PREFER)) is not None
    assert parse_recipe(data, replace(REQUEST, day=date(2026, 5, 4), season=SeasonMode.STRICT)) is not None


def test_instructions_name_metric_units_and_season() -> None:
    text = build_instructions(replace(REQUEST, season=SeasonMode.STRICT), "")
    assert "g, ml, pcs" in text and "October" in text and "asparagus" in text
    assert "October" not in build_instructions(REQUEST, "")


@pytest.fixture(scope="module")
def ingredients():
    from custom_components.meal_manager.adapters import load_ingredients  # noqa: PLC0415

    return load_ingredients()


def test_model_must_use_known_ingredients_in_their_unit(ingredients) -> None:
    data = {"title": "Gnocchi", "minutes": 25, "ingredients": "200 | g | gnocchi\n1 | pcs | yellow onion"}
    recipe = check_recipe(data, REQUEST, ingredients)
    assert [(i.name, i.unit) for i in recipe.ingredients] == [("potato gnocchi", "g"), ("onion", "pcs")]

    data["ingredients"] = "200 | g | gnocchi\n100 | g | onion"
    with pytest.raises(RecipeRejected, match="onion must be in pcs, not g"):
        check_recipe(data, REQUEST, ingredients)
    data["ingredients"] = "200 | g | dragon fruit"
    with pytest.raises(RecipeRejected, match=r"unknown ingredients .*dragon fruit"):
        check_recipe(data, REQUEST, ingredients)


def test_prompt_lists_known_ingredients(ingredients) -> None:
    text = build_instructions(REQUEST, "", ingredients)
    assert "onion (pcs)" in text and "potatoes (g)" in text
    assert "rejected: x" in retry_instructions(text, "x")
