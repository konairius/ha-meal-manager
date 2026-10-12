"""Parsing of local model output."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
import re

import pytest

from custom_components.meal_manager.core.llm import (
    Rejected,
    build_instructions,
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
            "ingredients": "- 80 | g | rice\n2. 30 | G | curry paste\n0.5 | pcs | onion",
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


@pytest.mark.parametrize(
    ("data", "reason"),
    [
        ({"title": "  PIZZA ", "ingredients": "1 | pcs | dough"}, "PIZZA must not be suggested"),
        ({"title": ""}, "the title is missing"),
        ("not a dict", "not a recipe"),
        ({"title": "Soup"}, "the ingredients are missing"),
    ],
)
def test_parse_recipe_rejects_with_a_reason(data, reason: str) -> None:
    with pytest.raises(Rejected, match=reason):
        parse_recipe(data, REQUEST)


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
    with pytest.raises(
        Rejected, match=re.escape("not written as 'quantity | g/ml/pcs | name': 5 | unit | lemon")
    ):
        parse_recipe(data, REQUEST)
    data["ingredients"] = "150 | g | salmon fillet\n5 | pcs | lemon"
    with pytest.raises(Rejected, match="implausible amounts for ONE portion: 5 pcs lemon"):
        parse_recipe(data, REQUEST)
    data["ingredients"] = "150 | g | salmon fillet\n15 | ml | lemon juice\n1 | pcs | garlic clove"
    recipe = parse_recipe(data, REQUEST)
    assert [i.unit for i in recipe.ingredients] == ["g", "ml", "pcs"]


def test_instructions_name_units_season_and_language() -> None:
    text = build_instructions(replace(REQUEST, season=SeasonMode.STRICT), "", "de")
    assert "g, ml, pcs" in text and "October" in text and "in season" in text
    assert "Write the title, ingredient names and steps in German." in text
    assert "October" not in build_instructions(replace(REQUEST, season=SeasonMode.OFF), "")


def test_retry_instructions_carry_the_reason() -> None:
    assert retry_instructions("Suggest a dish.", "no title").endswith(
        "Your previous answer was rejected: no title. Answer again and follow all rules."
    )
