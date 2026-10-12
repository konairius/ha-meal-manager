"""Domain model of the meal planner.

Framework-free: nothing in ``core`` may import Home Assistant.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime
from enum import StrEnum
from typing import Any


class MealType(StrEnum):
    """Kind of meal a recipe is suitable for."""

    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"


class PlanStatus(StrEnum):
    """Lifecycle of a plan."""

    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"


class SeasonMode(StrEnum):
    """How strictly seasonal produce is respected."""

    STRICT = "strict"  # only produce that is in season now
    PREFER = "prefer"  # rather plan seasonal dishes
    OFF = "off"


EFFORT_LABELS = {1: "low", 2: "medium", 3: "high"}


def normalize_title(title: str) -> str:
    """Key used to compare dish titles (bans, duplicates, history)."""
    return " ".join(title.casefold().split())


def nice_quantity(quantity: float) -> float:
    """Round a scaled quantity to something one can measure in a kitchen."""
    if quantity >= 100:
        return float(round(quantity / 10) * 10)
    if quantity >= 20:
        return float(round(quantity / 5) * 5)
    if quantity >= 5:
        return float(round(quantity))
    return max(0.25, round(quantity * 4) / 4) if quantity > 0 else 0.0


@dataclass(frozen=True, slots=True)
class Ingredient:
    """One ingredient, quantity is per portion."""

    name: str
    quantity: float
    unit: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "quantity": self.quantity, "unit": self.unit}

    def display(self) -> str:
        """E.g. 'rice 180 g' (name first, so shopping lists sort by name)."""
        amount = nice_quantity(self.quantity)
        quantity = f"{amount:g}" if self.quantity else ""
        return " ".join(p for p in (self.name, quantity, self.unit) if p)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Ingredient:
        return cls(
            name=str(data["name"]),
            quantity=float(data.get("quantity", 0) or 0),
            unit=str(data.get("unit", "") or ""),
        )


@dataclass(frozen=True, slots=True)
class Recipe:
    """A dish. Nutrition and ingredients are per portion."""

    id: str
    title: str
    meal_types: tuple[MealType, ...]
    effort: int  # 1 low, 2 medium, 3 high
    minutes: int
    health: int  # 1 indulgent .. 5 very healthy
    kcal: int  # per portion
    ingredients: tuple[Ingredient, ...] = ()
    steps: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    source: str = "builtin"

    @property
    def key(self) -> str:
        return normalize_title(self.title)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "meal_types": [str(m) for m in self.meal_types],
            "effort": self.effort,
            "minutes": self.minutes,
            "health": self.health,
            "kcal": self.kcal,
            "ingredients": [i.to_dict() for i in self.ingredients],
            "steps": list(self.steps),
            "tags": list(self.tags),
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Recipe:
        return cls(
            id=str(data["id"]),
            title=str(data["title"]),
            meal_types=tuple(MealType(m) for m in data["meal_types"]),
            effort=int(data["effort"]),
            minutes=int(data["minutes"]),
            health=int(data["health"]),
            kcal=int(data["kcal"]),
            ingredients=tuple(Ingredient.from_dict(i) for i in data.get("ingredients", ())),
            steps=tuple(str(s) for s in data.get("steps", ())),
            tags=tuple(str(t) for t in data.get("tags", ())),
            source=str(data.get("source", "builtin")),
        )


@dataclass(frozen=True, slots=True)
class MealRequest:
    """What a single meal of the plan must satisfy (resolved settings)."""

    day: date
    slot: str
    meal_type: MealType
    portions: int
    effort: int  # maximum effort
    health: int  # target health level
    kcal_target: int | None  # per person, None = no target
    exclude: frozenset[str] = frozenset()  # normalized titles that must not be used
    avoid: frozenset[str] = frozenset()  # normalized titles that should rather not be used
    season: SeasonMode = SeasonMode.OFF


@dataclass(slots=True)
class PlannedMeal:
    """A recipe placed on a day and slot."""

    id: str
    day: date
    slot: str
    recipe: Recipe
    portions: int
    effort: int
    health: int
    kcal_target: int | None
    scale: float = 1.0  # portion size factor to meet the calorie target
    cooked: bool = False
    cooked_at: datetime | None = None

    @property
    def kcal_per_person(self) -> int:
        return round(self.recipe.kcal * self.scale)

    def scaled_ingredients(self) -> list[Ingredient]:
        factor = self.portions * self.scale
        return [replace(i, quantity=i.quantity * factor) for i in self.recipe.ingredients]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "day": self.day.isoformat(),
            "slot": self.slot,
            "recipe": self.recipe.to_dict(),
            "portions": self.portions,
            "effort": self.effort,
            "health": self.health,
            "kcal_target": self.kcal_target,
            "scale": self.scale,
            "cooked": self.cooked,
            "cooked_at": self.cooked_at.isoformat() if self.cooked_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PlannedMeal:
        cooked_at = data.get("cooked_at")
        return cls(
            id=str(data["id"]),
            day=date.fromisoformat(data["day"]),
            slot=str(data["slot"]),
            recipe=Recipe.from_dict(data["recipe"]),
            portions=int(data["portions"]),
            effort=int(data["effort"]),
            health=int(data["health"]),
            kcal_target=data.get("kcal_target"),
            scale=float(data.get("scale", 1.0)),
            cooked=bool(data.get("cooked", False)),
            cooked_at=datetime.fromisoformat(cooked_at) if cooked_at else None,
        )


@dataclass(slots=True)
class Plan:
    """A set of meals over consecutive days."""

    id: str
    status: PlanStatus
    start: date
    days: int
    created: datetime
    meals: list[PlannedMeal] = field(default_factory=list)
    declined: set[str] = field(default_factory=set)  # normalized titles declined in this plan

    @property
    def cooked_count(self) -> int:
        return sum(1 for m in self.meals if m.cooked)

    @property
    def all_cooked(self) -> bool:
        return bool(self.meals) and all(m.cooked for m in self.meals)

    def meal(self, meal_id: str) -> PlannedMeal | None:
        return next((m for m in self.meals if m.id == meal_id), None)

    def titles(self) -> set[str]:
        return {m.recipe.key for m in self.meals}

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "status": str(self.status),
            "start": self.start.isoformat(),
            "days": self.days,
            "created": self.created.isoformat(),
            "meals": [m.to_dict() for m in self.meals],
            "declined": sorted(self.declined),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Plan:
        return cls(
            id=str(data["id"]),
            status=PlanStatus(data["status"]),
            start=date.fromisoformat(data["start"]),
            days=int(data["days"]),
            created=datetime.fromisoformat(data["created"]),
            meals=[PlannedMeal.from_dict(m) for m in data.get("meals", ())],
            declined=set(data.get("declined", ())),
        )


@dataclass(frozen=True, slots=True)
class Ban:
    """A dish that must never be planned again."""

    title: str
    banned_at: datetime

    @property
    def key(self) -> str:
        return normalize_title(self.title)

    def to_dict(self) -> dict[str, Any]:
        return {"title": self.title, "banned_at": self.banned_at.isoformat()}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Ban:
        return cls(title=str(data["title"]), banned_at=datetime.fromisoformat(data["banned_at"]))


@dataclass(frozen=True, slots=True)
class CookedEntry:
    """History of cooked dishes, used to avoid repetition."""

    title: str
    day: date
    meal_id: str

    def to_dict(self) -> dict[str, Any]:
        return {"title": self.title, "day": self.day.isoformat(), "meal_id": self.meal_id}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CookedEntry:
        return cls(
            title=str(data["title"]),
            day=date.fromisoformat(data["day"]),
            meal_id=str(data.get("meal_id", "")),
        )


@dataclass(slots=True)
class PlannerState:
    """Everything the planner persists."""

    active: Plan | None = None
    draft: Plan | None = None
    bans: list[Ban] = field(default_factory=list)
    history: list[CookedEntry] = field(default_factory=list)

    def banned_keys(self) -> set[str]:
        return {b.key for b in self.bans}

    def to_dict(self) -> dict[str, Any]:
        return {
            "active": self.active.to_dict() if self.active else None,
            "draft": self.draft.to_dict() if self.draft else None,
            "bans": [b.to_dict() for b in self.bans],
            "history": [h.to_dict() for h in self.history],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> PlannerState:
        if not data:
            return cls()
        return cls(
            active=Plan.from_dict(data["active"]) if data.get("active") else None,
            draft=Plan.from_dict(data["draft"]) if data.get("draft") else None,
            bans=[Ban.from_dict(b) for b in data.get("bans", ())],
            history=[CookedEntry.from_dict(h) for h in data.get("history", ())],
        )


MIN_SCALE = 0.75
MAX_SCALE = 1.5


def portion_scale(recipe: Recipe, kcal_target: int | None) -> float:
    """Portion size factor (in quarter steps) that brings a dish close to the calorie target."""
    if not kcal_target:
        return 1.0
    factor = min(MAX_SCALE, max(MIN_SCALE, kcal_target / recipe.kcal))
    return round(factor * 4) / 4
