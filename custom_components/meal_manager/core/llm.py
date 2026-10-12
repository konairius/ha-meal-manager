"""Prompt and tolerant output parsing for an optional local language model."""

from __future__ import annotations

import logging
import re
from typing import Any

from .ingredients import IngredientCatalog
from .models import EFFORT_LABELS, Ingredient, MealRequest, Recipe, normalize_title
from .quantities import METRIC_UNITS, is_plausible, parse_quantity
from .season import SeasonMode, out_of_season, produce_out_of_season

_LOGGER = logging.getLogger(__name__)

EFFORT_HINT = {1: "at most 20 minutes", 2: "at most 45 minutes", 3: "any preparation time"}
HEALTH_HINT = {
    1: "indulgent comfort food is fine",
    2: "rather hearty",
    3: "balanced",
    4: "healthy, plenty of vegetables",
    5: "very healthy, whole foods, lots of vegetables, little sugar and fat",
}

FIELDS = ("title", "minutes", "kcal", "health", "ingredients", "steps")


def build_instructions(
    request: MealRequest, preferences: str = "", ingredients: IngredientCatalog | None = None
) -> str:
    """Instructions for one dish."""
    lines = [
        f"Suggest one {request.meal_type} dish for {request.day:%A}.",
        f"Effort: {EFFORT_LABELS[request.effort]} ({EFFORT_HINT[request.effort]}).",
        f"Healthiness: {request.health} of 5 ({HEALTH_HINT[request.health]}).",
    ]
    if request.kcal_target:
        lines.append(f"Calories: about {request.kcal_target} kcal per portion.")
    if preferences.strip():
        lines.append(f"Household preferences: {preferences.strip()}")
    if request.exclude:
        lines.append("Do not suggest any of: " + "; ".join(sorted(request.exclude)) + ".")
    if request.season is not SeasonMode.OFF:
        avoid = ", ".join(produce_out_of_season(request.day.month))
        lines.append(
            f"Season: it is {request.day:%B} in Central Europe. Use produce that is in season now;"
            f" not in season: {avoid}."
        )
    if request.avoid:
        lines.append("Avoid if possible (cooked recently): " + "; ".join(sorted(request.avoid)) + ".")
    lines += [
        "Answer with:",
        "- title: dish name",
        "- minutes: total preparation time",
        "- kcal: calories per portion",
        "- health: 1 (indulgent) to 5 (very healthy)",
        "- ingredients: one per line, amounts for ONE person (not the whole dish), formatted"
        " 'quantity | unit | name', e.g. '120 | g | spaghetti', '15 | ml | olive oil' or"
        f" '0.5 | pcs | lemon'. Only metric units: {', '.join(METRIC_UNITS)}; no spoons, cups or"
        " other units. Answers in any other format are rejected.",
        "- steps: one cooking step per line",
    ]
    if ingredients:
        lines.append(
            "Use only these ingredients, spelled exactly like this and in the unit given in brackets"
            f" (any other ingredient or unit is rejected): {ingredients.prompt_list()}."
        )
    return "\n".join(lines)


def retry_instructions(instructions: str, reason: str) -> str:
    """The instructions again, with why the previous answer was rejected."""
    return (
        f"{instructions}\nYour previous answer was rejected: {reason}. Suggest a dish that follows all rules."
    )


_NUMBER = re.compile(r"-?\d+(?:[.,]\d+)?")


def _number(raw: Any, default: float) -> float:
    if isinstance(raw, int | float) and not isinstance(raw, bool):
        return float(raw)
    match = _NUMBER.search(str(raw or ""))
    return float(match.group().replace(",", ".")) if match else default


def _lines(raw: Any) -> list[str]:
    items = [str(i) for i in raw] if isinstance(raw, list) else str(raw or "").splitlines()
    cleaned = [re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", i).strip() for i in items]
    return [c for c in cleaned if c]


def parse_ingredient(line: str) -> Ingredient | None:
    """Parse 'quantity | unit | name' with a metric unit; None when the line is malformed.

    Nothing is guessed: "5 | unit | lemon" or "2 | tbsp | oil" is a wrong answer, so the whole
    dish is rejected and asked for again.
    """
    parts = [p.strip() for p in line.split("|")]
    if len(parts) != 3 or not parts[2]:
        return None
    quantity = parse_quantity(parts[0])
    unit = parts[1].casefold()
    if quantity is None or quantity <= 0 or unit not in METRIC_UNITS:
        return None
    return Ingredient(" ".join(parts[2].split()), quantity, unit)


class RecipeRejected(ValueError):
    """A model answer that cannot be used; the message says why (and is sent with the retry)."""


def parse_recipe(
    data: Any, request: MealRequest, ingredients: IngredientCatalog | None = None
) -> Recipe | None:
    """Turn model output into a recipe. Returns None when unusable or excluded."""
    try:
        return check_recipe(data, request, ingredients)
    except RecipeRejected as err:
        _LOGGER.info("Rejecting model answer: %s", err)
        return None


def check_recipe(data: Any, request: MealRequest, ingredients: IngredientCatalog | None = None) -> Recipe:
    """Turn model output into a recipe, or raise RecipeRejected with the reason.

    With an ingredient catalog every ingredient must be a known one in its unit; names are
    stored in their canonical spelling so plans and shopping lists merge them.
    """
    if not isinstance(data, dict):
        raise RecipeRejected("not a recipe")
    title = str(data.get("title") or "").strip()
    if not title:
        raise RecipeRejected("no title")
    if normalize_title(title) in request.exclude:
        raise RecipeRejected(f"{title} is excluded")
    minutes = int(_number(data.get("minutes"), 30))
    effort = 1 if minutes <= 20 else 2 if minutes <= 45 else 3
    parsed = [(line, parse_ingredient(line)) for line in _lines(data.get("ingredients"))]
    if malformed := [line for line, ingredient in parsed if ingredient is None]:
        raise RecipeRejected(
            f"ingredients not written as 'quantity | g/ml/pcs | name': {'; '.join(malformed)}"
        )
    items = [ingredient for _, ingredient in parsed if ingredient]
    if not items:
        raise RecipeRejected("no ingredients")
    if ingredients is not None:
        items = _canonical(items, ingredients)
    if request.season is SeasonMode.STRICT and (
        unseasonal := out_of_season((i.name for i in items), request.day.month)
    ):
        raise RecipeRejected(f"out of season in {request.day:%B}: {', '.join(unseasonal)}")
    if implausible := [i for i in items if not is_plausible(i)]:
        amounts = ", ".join(f"{i.quantity:g} {i.unit} {i.name}" for i in implausible)
        raise RecipeRejected(f"implausible amounts for one portion: {amounts}")
    return Recipe(
        id=f"ai:{normalize_title(title).replace(' ', '_')}",
        title=title,
        meal_types=(request.meal_type,),
        effort=effort,
        minutes=minutes,
        health=min(5, max(1, int(_number(data.get("health"), request.health)))),
        kcal=max(1, int(_number(data.get("kcal"), request.kcal_target or 600))),
        ingredients=tuple(items),
        steps=tuple(_lines(data.get("steps"))),
        source="ai",
    )


def _canonical(items: list[Ingredient], catalog: IngredientCatalog) -> list[Ingredient]:
    result: list[Ingredient] = []
    unknown: list[str] = []
    wrong_unit: list[str] = []
    for item in items:
        name = catalog.resolve(item.name)
        if name is None:
            unknown.append(item.name)
        elif item.unit != catalog[name].unit:
            wrong_unit.append(f"{name} must be in {catalog[name].unit}, not {item.unit}")
        else:
            result.append(Ingredient(name, item.quantity, item.unit))
    if unknown:
        raise RecipeRejected(f"unknown ingredients (use only the listed ones): {', '.join(unknown)}")
    if wrong_unit:
        raise RecipeRejected("; ".join(wrong_unit))
    return result
