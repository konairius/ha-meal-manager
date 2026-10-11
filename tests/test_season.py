"""Seasonal produce (Central Europe)."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
import random

from custom_components.meal_manager.core.catalog import RecipeCatalog
from custom_components.meal_manager.core.models import Ingredient, MealRequest, MealType, Recipe, SeasonMode
from custom_components.meal_manager.core.season import out_of_season, produce_out_of_season


def recipe(title: str, *names: str) -> Recipe:
    return Recipe(
        id=title,
        title=title,
        meal_types=(MealType.DINNER,),
        effort=2,
        minutes=30,
        health=3,
        kcal=500,
        ingredients=tuple(Ingredient(n, 100, "g") for n in names),
        steps=(),
        source="builtin",
    )


OCTOBER = MealRequest(
    day=date(2026, 10, 12),
    slot="dinner",
    meal_type=MealType.DINNER,
    portions=2,
    effort=2,
    health=3,
    kcal_target=None,
    season=SeasonMode.STRICT,
)


def test_asparagus_only_in_spring() -> None:
    assert out_of_season(["green asparagus", "salmon"], 10) == ["green asparagus"]
    assert out_of_season(["green asparagus"], 5) == []
    assert "asparagus" in produce_out_of_season(10)


def test_winter_vegetables_wrap_around_the_year() -> None:
    assert out_of_season(["kale"], 1) == [] and out_of_season(["kale"], 7) == ["kale"]


def test_preserved_produce_is_always_fine() -> None:
    assert out_of_season(["canned tomatoes", "tomato paste", "frozen berries"], 1) == []


async def test_strict_catalog_never_suggests_out_of_season() -> None:
    catalog = RecipeCatalog(
        [recipe("Asparagus", "asparagus"), recipe("Pumpkin soup", "pumpkin")], random.Random(1)
    )
    for _ in range(20):
        assert (await catalog.suggest(OCTOBER)).title == "Pumpkin soup"


async def test_strict_falls_back_when_nothing_is_in_season() -> None:
    catalog = RecipeCatalog([recipe("Asparagus", "asparagus")], random.Random(1))
    assert (await catalog.suggest(OCTOBER)).title == "Asparagus"


def test_off_ignores_seasons() -> None:
    request = replace(OCTOBER, season=SeasonMode.OFF)
    assert RecipeCatalog.score(recipe("Asparagus", "asparagus"), request) == RecipeCatalog.score(
        recipe("Pumpkin soup", "pumpkin"), request
    )
