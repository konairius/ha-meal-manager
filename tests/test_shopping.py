"""Shopping list written by the model: prompt and strict checking of the answer."""

from __future__ import annotations

import pytest

from custom_components.meal_manager.core.llm import Rejected
from custom_components.meal_manager.core.models import Ingredient
from custom_components.meal_manager.core.shopping import (
    ShoppingItem,
    build_shopping_instructions,
    parse_shopping_list,
)

NEEDED = [Ingredient("Kokosmilch", 480, "ml"), Ingredient("Zwiebel", 2.5, "pcs"), Ingredient("Salz", 3, "g")]


def test_prompt_has_amounts_language_and_pantry() -> None:
    text = build_shopping_instructions(NEEDED, "Salz, Pfeffer", "de")
    assert "- 480 ml Kokosmilch" in text and "- 2.5 pcs Zwiebel" in text
    assert "Write it in German." in text
    assert "always has at home: Salz, Pfeffer." in text
    assert "'Kokosmilch | 2 Dosen à 400 ml'" in text


def test_parses_products() -> None:
    items = parse_shopping_list({"items": "- Kokosmilch | 2 Dosen à 400 ml\n2. Zwiebeln | 3 Stück"}, NEEDED)
    assert items == [ShoppingItem("Kokosmilch", "2 Dosen à 400 ml"), ShoppingItem("Zwiebeln", "3 Stück")]
    assert items[0].display() == "Kokosmilch: 2 Dosen à 400 ml"


@pytest.mark.parametrize(
    ("answer", "reason"),
    [
        ({"items": "Gemüse:\nKokosmilch | 2 Dosen"}, "not written as 'product | amount'.*Gemüse:"),
        ({"items": "Zwiebeln | etwas"}, "with a number: Zwiebeln | etwas"),
        ({"items": ""}, "the list is empty"),
        ({"items": "Zwiebeln | 2 Stück\nzwiebeln | 1 Stück"}, "more than once.*zwiebeln"),
        ({"items": "A | 1\nB | 1\nC | 1\nD | 1"}, "more products than there are ingredients"),
        ("Kokosmilch", "not a shopping list"),
    ],
)
def test_rejects_broken_answers_with_a_reason(answer, reason: str) -> None:
    with pytest.raises(Rejected, match=reason):
        parse_shopping_list(answer, NEEDED)
