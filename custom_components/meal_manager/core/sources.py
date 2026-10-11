"""Composition of recipe sources."""

from __future__ import annotations

import logging

from .models import MealRequest, Recipe
from .ports import RecipeSource

_LOGGER = logging.getLogger(__name__)


class FallbackSource:
    """Asks the primary source first and falls back to the secondary one."""

    def __init__(self, primary: RecipeSource, fallback: RecipeSource) -> None:
        self._primary = primary
        self._fallback = fallback

    async def suggest(self, request: MealRequest) -> Recipe | None:
        recipe = await self._primary.suggest(request)
        if recipe is None:
            _LOGGER.debug("Primary source had no %s for %s, using fallback", request.slot, request.day)
            recipe = await self._fallback.suggest(request)
        return recipe
