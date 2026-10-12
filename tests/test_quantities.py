"""Quantity parsing and plausibility."""

from __future__ import annotations

import pytest

from custom_components.meal_manager.core.models import Ingredient
from custom_components.meal_manager.core.quantities import is_plausible, parse_quantity


@pytest.mark.parametrize(
    ("text", "expected"),
    [("2", 2), ("0,5", 0.5), ("1/2", 0.5), ("1 1/2", 1.5), ("½", 0.5), ("1½", 1.5), ("1-2", 1), ("x", None)],
)
def test_parse_quantity(text: str, expected: float | None) -> None:
    assert parse_quantity(text) == expected


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
