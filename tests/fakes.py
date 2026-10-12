"""In-memory fakes of the core ports, including a stand-in for the local model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from custom_components.meal_manager.core.models import (
    Ingredient,
    MealRequest,
    MealType,
    Recipe,
    normalize_title,
)

# Dishes the fake model knows per meal type; it runs out after these.
POOLS = {
    MealType.BREAKFAST: [f"Breakfast {i}" for i in range(8)],
    MealType.LUNCH: [f"Main {i}" for i in range(20)],
    MealType.DINNER: [f"Main {i}" for i in range(20)],
    MealType.SNACK: [f"Snack {i}" for i in range(5)],
}


class FakeModel:
    """A RecipeSource standing in for the local model: follows the request like a good model."""

    def __init__(self) -> None:
        self.requests: list[MealRequest] = []

    async def suggest(self, request: MealRequest) -> Recipe | None:
        self.requests.append(request)
        allowed = [t for t in POOLS[request.meal_type] if normalize_title(t) not in request.exclude]
        fresh = [t for t in allowed if normalize_title(t) not in request.avoid]
        title = next(iter(fresh or allowed), None)
        if title is None:
            return None
        return Recipe(
            id=f"ai:{normalize_title(title)}",
            title=title,
            meal_types=(request.meal_type,),
            effort=request.effort,
            minutes={1: 15, 2: 35, 3: 70}[request.effort],
            health=request.health,
            kcal=request.kcal_target or 500,
            ingredients=(Ingredient("onion", 0.5, "pcs"), Ingredient(f"{title.lower()} base", 100, "g")),
            steps=("Cook it.",),
            source="ai",
        )


class MemoryStore:
    def __init__(self) -> None:
        self.data: dict[str, Any] | None = None
        self.saves = 0

    async def load(self) -> dict[str, Any] | None:
        return self.data

    async def save(self, data: dict[str, Any]) -> None:
        self.data = data
        self.saves += 1


class RecordingEvents:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    def publish(self, event: str, data: dict[str, Any]) -> None:
        self.events.append((event, data))

    def names(self) -> list[str]:
        return [e for e, _ in self.events]


class FixedClock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now
