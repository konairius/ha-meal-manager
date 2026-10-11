"""Prompt and tolerant output parsing for an optional local language model."""

from __future__ import annotations

import logging
import re
from typing import Any

from .models import EFFORT_LABELS, Ingredient, MealRequest, Recipe, normalize_title
from .quantities import MAX_PER_PORTION, UNIT_ALIASES, is_plausible, normalize, parse_quantity

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


def build_instructions(request: MealRequest, preferences: str = "") -> str:
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
    if request.avoid:
        lines.append("Avoid if possible (cooked recently): " + "; ".join(sorted(request.avoid)) + ".")
    lines += [
        "Answer with:",
        "- title: dish name",
        "- minutes: total preparation time",
        "- kcal: calories per portion",
        "- health: 1 (indulgent) to 5 (very healthy)",
        "- ingredients: one per line, amounts for ONE person (not the whole dish), formatted"
        " 'quantity | unit | name', e.g. '120 | g | spaghetti' or '0.5 | pcs | lemon'."
        f" Units: {', '.join(MAX_PER_PORTION)}.",
        "- steps: one cooking step per line",
    ]
    return "\n".join(lines)


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


_LEADING_QUANTITY = re.compile(r"^\s*([\d½⅓⅔¼¾⅛][\d.,/\s½⅓⅔¼¾⅛-]*)\s*(.*)$")


def parse_ingredient(line: str) -> Ingredient | None:
    """Parse 'quantity | unit | name' or a loose 'quantity [unit] name'; units are normalized."""
    parts = [p.strip() for p in line.split("|")]
    if len(parts) >= 3:
        quantity = parse_quantity(parts[0])
        return normalize(Ingredient(parts[2], 1 if quantity is None else quantity, parts[1]))
    match = _LEADING_QUANTITY.match(line)
    if not match:
        return Ingredient(line.strip(), 1, "") if line.strip() else None
    quantity = parse_quantity(match.group(1))
    words = match.group(2).split(maxsplit=1)
    unit = ""
    if len(words) == 2 and words[0].casefold().rstrip(".") in UNIT_ALIASES:
        unit, name = words
    else:
        name = match.group(2)
    return normalize(Ingredient(name, 1 if quantity is None else quantity, unit))


def parse_recipe(data: Any, request: MealRequest) -> Recipe | None:
    """Turn model output into a recipe. Returns None when unusable or excluded."""
    if not isinstance(data, dict):
        return None
    title = str(data.get("title") or "").strip()
    if not title or normalize_title(title) in request.exclude:
        return None
    minutes = int(_number(data.get("minutes"), 30))
    effort = 1 if minutes <= 20 else 2 if minutes <= 45 else 3
    ingredients = [i for i in (parse_ingredient(line) for line in _lines(data.get("ingredients"))) if i]
    implausible = [i for i in ingredients if not is_plausible(i)]
    if implausible:
        _LOGGER.info(
            "Rejecting %s: implausible amounts per portion: %s",
            title,
            ", ".join(f"{i.quantity:g} {i.unit} {i.name}" for i in implausible),
        )
        return None
    return Recipe(
        id=f"ai:{normalize_title(title).replace(' ', '_')}",
        title=title,
        meal_types=(request.meal_type,),
        effort=effort,
        minutes=minutes,
        health=min(5, max(1, int(_number(data.get("health"), request.health)))),
        kcal=max(1, int(_number(data.get("kcal"), request.kcal_target or 600))),
        ingredients=tuple(ingredients),
        steps=tuple(_lines(data.get("steps"))),
        source="ai",
    )
