"""In-memory fakes of the core ports and a small recipe set."""

from __future__ import annotations

from datetime import datetime
import random
from typing import Any

from custom_components.meal_manager.core.catalog import RecipeCatalog, parse_recipes


def recipe(title: str, types: list[str], effort: int = 1, health: int = 3, kcal: int = 500) -> dict:
    return {
        "title": title,
        "meal_types": types,
        "effort": effort,
        "minutes": {1: 15, 2: 35, 3: 70}[effort],
        "health": health,
        "kcal": kcal,
        "ingredients": [
            {"name": "onion", "quantity": 0.5, "unit": "pcs"},
            {"name": f"{title.lower()} base", "quantity": 100, "unit": "g"},
        ],
        "steps": ["Cook it."],
    }


RAW = [
    *(
        recipe(f"Breakfast {i}", ["breakfast"], effort=1 + i % 3, health=1 + i % 5, kcal=300 + 20 * i)
        for i in range(8)
    ),
    *(
        recipe(f"Main {i}", ["lunch", "dinner"], effort=1 + i % 3, health=1 + i % 5, kcal=450 + 30 * i)
        for i in range(20)
    ),
    *(recipe(f"Snack {i}", ["snack"], effort=1, health=2 + i % 3, kcal=150 + 20 * i) for i in range(5)),
]


def catalog(seed: int = 1) -> RecipeCatalog:
    recipes, errors = parse_recipes(RAW, "test")
    assert not errors
    return RecipeCatalog(recipes, random.Random(seed))


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
