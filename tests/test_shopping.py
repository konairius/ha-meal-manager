"""Shopping list: merged, buyable, translated and without pantry staples."""

from __future__ import annotations

import pytest

from custom_components.meal_manager.adapters import load_ingredients
from custom_components.meal_manager.core.models import Ingredient
from custom_components.meal_manager.core.shopping import build_shopping_list, parse_pantry


@pytest.fixture(scope="module")
def catalog():
    return load_ingredients()


def shop(catalog, *ingredients: Ingredient, language: str = "de", **kwargs) -> list[str]:
    return [i.display() for i in build_shopping_list(ingredients, catalog, language=language, **kwargs)]


def test_packages_instead_of_grams(catalog) -> None:
    assert shop(catalog, Ingredient("coconut milk", 150, "ml"), Ingredient("coconut milk", 300, "ml")) == [
        "Kokosmilch: 2 × Dose 400 ml"
    ]
    assert shop(catalog, Ingredient("eggs", 3, "pcs")) == ["Eier: 1 × 10er-Packung"]
    assert shop(catalog, Ingredient("parsley", 3, "g")) == ["Petersilie: 1 × Bund"]
    assert shop(catalog, Ingredient("bacon slice", 3, "pcs")) == ["Bacon: 1 × Packung (ca. 100 g)"]


def test_loose_produce_is_rounded_up(catalog) -> None:
    assert shop(catalog, Ingredient("apple", 1.25, "pcs")) == ["Äpfel: 2 Stück"]
    assert shop(catalog, Ingredient("potatoes", 2020, "g")) == ["Kartoffeln: 2,5 kg"]
    assert shop(catalog, Ingredient("chicken breast", 910, "g")) == ["Hähnchenbrust: 950 g"]


def test_pantry_staples_are_left_out(catalog) -> None:
    items = (Ingredient("water", 500, "ml"), Ingredient("salt", 2, "g"), Ingredient("cumin", 2, "g"))
    assert shop(catalog, *items, Ingredient("olive oil", 30, "ml")) == []
    assert shop(catalog, Ingredient("olive oil", 30, "ml"), pantry=parse_pantry("salt")) == [
        "Olivenöl: 1 × Flasche 500 ml"
    ]
    assert shop(catalog, Ingredient("feta", 75, "g"), pantry=parse_pantry("Feta")) == []


def test_ordered_by_supermarket_section(catalog) -> None:
    items = (Ingredient("spaghetti", 250, "g"), Ingredient("butter", 20, "g"), Ingredient("onion", 1, "pcs"))
    assert [i.split(":")[0] for i in shop(catalog, *items)] == ["Zwiebeln", "Butter", "Spaghetti"]


def test_variants_are_merged_and_translated(catalog) -> None:
    items = (
        Ingredient("yellow onion", 1, "pcs"),
        Ingredient("onions", 1, "pcs"),
        Ingredient("chestnut mushrooms", 150, "g"),
        Ingredient("brown mushrooms", 150, "g"),
        Ingredient("heavy cream", 150, "ml"),
        Ingredient("fresh parsley", 10, "g"),
        Ingredient("smoked bacon lardons", 80, "g"),
    )
    assert shop(catalog, *items) == [
        "Champignons: 2 × Schale 250 g",
        "Zwiebeln: 2 Stück",
        "Petersilie: 1 × Bund",
        "Speckwürfel: 1 × Packung 125 g",
        "Sahne: 1 × Becher 200 ml",
    ]


def test_english_and_unknown_ingredients(catalog) -> None:
    assert shop(catalog, Ingredient("coconut milk", 150, "ml"), language="en") == [
        "coconut milk: 1 × can 400 ml"
    ]
    assert shop(catalog, Ingredient("dragon fruit", 0.5, "pcs")) == ["dragon fruit: 1 Stück"]


def test_every_bundled_ingredient_is_known(catalog) -> None:
    import json  # noqa: PLC0415
    from pathlib import Path  # noqa: PLC0415

    recipes = json.loads(
        (Path(__file__).parents[1] / "custom_components/meal_manager/data/recipes.json").read_text()
    )
    names = {i["name"] for r in recipes for i in r["ingredients"]}
    assert names <= set(catalog)
    for name in names:
        package = catalog[name].package
        units = {i["unit"] for r in recipes for i in r["ingredients"] if i["name"] == name}
        assert package is None or package.unit in units, name
