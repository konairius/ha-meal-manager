"""Prompt and tolerant output parsing for an optional local language model."""

from __future__ import annotations

import re
from typing import Any

from .models import EFFORT_LABELS, Ingredient, MealRequest, Recipe, normalize_title

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
        "- ingredients: one per line for ONE portion, formatted 'quantity | unit | name',"
        " e.g. '120 | g | spaghetti'",
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


def parse_ingredient(line: str) -> Ingredient | None:
    """Parse 'quantity | unit | name' or a loose 'quantity unit name'."""
    parts = [p.strip() for p in line.split("|")]
    if len(parts) >= 3:
        return Ingredient(parts[2], _number(parts[0], 1), parts[1])
    match = re.match(r"^(-?\d+(?:[.,]\d+)?)\s*([A-Za-zµ]+\.?)?\s+(.+)$", line)
    if match:
        return Ingredient(match.group(3), float(match.group(1).replace(",", ".")), match.group(2) or "")
    return Ingredient(line, 1, "") if line else None


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
