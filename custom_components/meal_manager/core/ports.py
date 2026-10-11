"""Interfaces the core depends on. Implemented by the Home Assistant adapters."""

from __future__ import annotations

from typing import Any, Protocol

from .models import MealRequest, Recipe


class RecipeSource(Protocol):
    """Suggests a dish for a meal."""

    async def suggest(self, request: MealRequest) -> Recipe | None:
        """Return a recipe satisfying the request, or None if there is none."""


class StateStore(Protocol):
    """Persists the planner state."""

    async def load(self) -> dict[str, Any] | None:
        """Load the stored state."""

    async def save(self, data: dict[str, Any]) -> None:
        """Store the state."""


class EventSink(Protocol):
    """Publishes domain events."""

    def publish(self, event: str, data: dict[str, Any]) -> None:
        """Publish an event."""
