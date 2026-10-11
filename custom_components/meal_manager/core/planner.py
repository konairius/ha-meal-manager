"""MealPlanner application service: plan lifecycle, bans, history and shopping list."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
import logging
import uuid

from .catalog import portion_scale
from .models import (
    Ban,
    CookedEntry,
    Ingredient,
    MealRequest,
    MealType,
    Plan,
    PlannedMeal,
    PlannerState,
    PlanStatus,
    SeasonMode,
    normalize_title,
)
from .ports import EventSink, RecipeSource, StateStore
from .settings import Setting, SettingsResolver

_LOGGER = logging.getLogger(__name__)

EVENT_DRAFT_READY = "draft_ready"
EVENT_PLAN_COMPLETED = "plan_completed"
EVENT_MEAL_COOKED = "meal_cooked"
EVENT_GENERATION_FAILED = "generation_failed"

HISTORY_LIMIT = 100
MAX_DAYS = 31


class PlannerError(Exception):
    """A request the planner cannot fulfil. ``code`` is a stable translation key."""

    def __init__(self, code: str, **placeholders: str) -> None:
        super().__init__(code)
        self.code = code
        self.placeholders = placeholders


@dataclass(frozen=True, slots=True)
class PlannerOptions:
    """Behaviour options of the planner."""

    default_days: int = 7
    avoid_recent: int = 10  # number of recently cooked dishes to avoid
    auto_new_plan: bool = True  # offer a new draft when every meal is cooked
    season: SeasonMode = SeasonMode.STRICT  # seasonal produce (Central Europe)


class MealPlanner:
    """Use cases of the meal planner."""

    def __init__(
        self,
        *,
        store: StateStore,
        source: RecipeSource,
        resolver: Callable[[], SettingsResolver],
        events: EventSink,
        clock: Callable[[], datetime],
        options: PlannerOptions | None = None,
        new_id: Callable[[], str] = lambda: uuid.uuid4().hex[:12],
    ) -> None:
        self._store = store
        self._source = source
        self._resolver = resolver
        self._events = events
        self._clock = clock
        self._new_id = new_id
        self.options = options or PlannerOptions()
        self._state = PlannerState()
        self._lock = asyncio.Lock()
        self._listeners: list[Callable[[], None]] = []
        self.generating = False

    # ----------------------------------------------------------------- state

    @property
    def state(self) -> PlannerState:
        return self._state

    async def async_load(self) -> None:
        self._state = PlannerState.from_dict(await self._store.load())

    def add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    async def _commit(self) -> None:
        await self._store.save(self._state.to_dict())
        self._notify()

    def _notify(self) -> None:
        for listener in list(self._listeners):
            listener()

    def _today(self) -> date:
        return self._clock().date()

    # ------------------------------------------------------------- generation

    async def generate_draft(self, start: date | None = None, days: int | None = None) -> Plan:
        """Create a new draft plan, replacing an existing draft."""
        days = days or self.options.default_days
        if not 1 <= days <= MAX_DAYS:
            raise PlannerError("invalid_days", max=str(MAX_DAYS))
        start = start or self._default_start()
        async with self._lock:
            self.generating = True
            self._notify()
            try:
                plan = await self._build_plan(start, days)
            except PlannerError as err:
                self._events.publish(EVENT_GENERATION_FAILED, {"reason": err.code})
                raise
            finally:
                self.generating = False
            self._state.draft = plan
            await self._commit()
        self._events.publish(
            EVENT_DRAFT_READY, {"plan_id": plan.id, "start": start.isoformat(), "days": days}
        )
        return plan

    def _default_start(self) -> date:
        today = self._today()
        active = self._state.active
        if active and active.status is PlanStatus.ACTIVE and not active.all_cooked:
            return max(today, active.start + timedelta(days=active.days))
        return today

    async def _build_plan(self, start: date, days: int) -> Plan:
        resolver = self._resolver()
        plan = Plan(
            id=self._new_id(),
            status=PlanStatus.DRAFT,
            start=start,
            days=days,
            created=self._clock(),
        )
        for offset in range(days):
            day = start + timedelta(days=offset)
            slots = resolver.slots_for(day)
            targets = resolver.kcal_targets(day, slots)
            for slot in slots:
                request = MealRequest(
                    day=day,
                    slot=slot.name,
                    meal_type=slot.meal_type,
                    portions=resolver.resolve(Setting.PORTIONS, day, slot.name).value,
                    effort=resolver.resolve(Setting.EFFORT, day, slot.name).value,
                    health=resolver.resolve(Setting.HEALTH, day, slot.name).value,
                    kcal_target=targets[slot.name],
                )
                plan.meals.append(await self._new_meal(plan, request))
        return plan

    def _exclusions(self, plan: Plan) -> tuple[frozenset[str], frozenset[str]]:
        exclude = self._state.banned_keys() | plan.titles() | plan.declined
        avoid = {normalize_title(h.title) for h in self._state.history[-self.options.avoid_recent :]}
        if self._state.active and self._state.active is not plan:
            avoid |= self._state.active.titles()
        return frozenset(exclude), frozenset(avoid)

    async def _new_meal(self, plan: Plan, request: MealRequest, meal_id: str | None = None) -> PlannedMeal:
        exclude, avoid = self._exclusions(plan)
        request = replace(request, exclude=exclude, avoid=avoid, season=self.options.season)
        recipe = await self._source.suggest(request)
        if recipe is None:
            raise PlannerError("no_recipe", slot=request.slot, day=request.day.isoformat())
        return PlannedMeal(
            id=meal_id or self._new_id(),
            day=request.day,
            slot=request.slot,
            recipe=recipe,
            portions=request.portions,
            effort=request.effort,
            health=request.health,
            kcal_target=request.kcal_target,
            scale=portion_scale(recipe, request.kcal_target),
        )

    # -------------------------------------------------------------- lifecycle

    async def accept_draft(self) -> Plan:
        async with self._lock:
            draft = self._require_draft()
            draft.status = PlanStatus.ACTIVE
            self._state.active = draft
            self._state.draft = None
            await self._commit()
            return draft

    async def discard_draft(self) -> None:
        async with self._lock:
            self._require_draft()
            self._state.draft = None
            await self._commit()

    def _require_draft(self) -> Plan:
        if self._state.draft is None:
            raise PlannerError("no_draft")
        return self._state.draft

    def _find(self, meal_id: str) -> tuple[Plan, PlannedMeal]:
        for plan in (self._state.active, self._state.draft):
            if plan and (meal := plan.meal(meal_id)):
                return plan, meal
        raise PlannerError("meal_not_found", meal_id=meal_id)

    def find_slot(self, day: date, slot: str) -> PlannedMeal:
        active = self._state.active
        meal = next(
            (m for m in (active.meals if active else ()) if m.day == day and m.slot == slot),
            None,
        )
        if meal is None:
            raise PlannerError("meal_not_found", meal_id=f"{day.isoformat()} {slot}")
        return meal

    async def mark_cooked(self, meal_id: str, cooked: bool = True) -> PlannedMeal:
        completed = False
        async with self._lock:
            plan, meal = self._find(meal_id)
            if plan is not self._state.active:
                raise PlannerError("not_active")
            if meal.cooked == cooked:
                return meal
            meal.cooked = cooked
            meal.cooked_at = self._clock() if cooked else None
            if cooked:
                self._state.history.append(CookedEntry(meal.recipe.title, meal.day, meal.id))
                self._state.history = self._state.history[-HISTORY_LIMIT:]
            else:
                self._state.history = [h for h in self._state.history if h.meal_id != meal.id]
            if plan.all_cooked and plan.status is PlanStatus.ACTIVE:
                plan.status = PlanStatus.COMPLETED
                completed = True
            elif not plan.all_cooked and plan.status is PlanStatus.COMPLETED:
                plan.status = PlanStatus.ACTIVE
            await self._commit()
        self._events.publish(
            EVENT_MEAL_COOKED, {"meal_id": meal.id, "title": meal.recipe.title, "cooked": cooked}
        )
        if completed:
            self._events.publish(EVENT_PLAN_COMPLETED, {"plan_id": plan.id})
            if self.options.auto_new_plan and self._state.draft is None:
                try:
                    await self.generate_draft()
                except PlannerError as err:
                    _LOGGER.warning("Could not create the next plan: %s", err.code)
        return meal

    async def decline_meal(self, meal_id: str) -> PlannedMeal:
        """Replace a meal with another suggestion."""
        async with self._lock:
            plan, meal = self._find(meal_id)
            if meal.cooked:
                raise PlannerError("already_cooked")
            plan.declined.add(meal.recipe.key)
            replacement = await self._replace(plan, meal)
            await self._commit()
            return replacement

    async def ban_meal(self, meal_id: str | None = None, title: str | None = None) -> Ban:
        """Never plan a dish again; a planned meal is replaced right away."""
        async with self._lock:
            if meal_id:
                title = self._find(meal_id)[1].recipe.title
            if not title or not title.strip():
                raise PlannerError("title_required")
            ban = Ban(title.strip(), self._clock())
            if ban.key not in self._state.banned_keys():
                self._state.bans.append(ban)
            # Replace every uncooked occurrence of the dish.
            for current in (self._state.active, self._state.draft):
                if current is None:
                    continue
                for planned in list(current.meals):
                    if planned.recipe.key == ban.key and not planned.cooked:
                        await self._replace(current, planned)
            await self._commit()
            return ban

    async def unban(self, title: str) -> None:
        async with self._lock:
            key = normalize_title(title)
            if key not in self._state.banned_keys():
                raise PlannerError("not_banned", title=title)
            self._state.bans = [b for b in self._state.bans if b.key != key]
            await self._commit()

    async def _replace(self, plan: Plan, meal: PlannedMeal) -> PlannedMeal:
        request = MealRequest(
            day=meal.day,
            slot=meal.slot,
            meal_type=self._meal_type(meal),
            portions=meal.portions,
            effort=meal.effort,
            health=meal.health,
            kcal_target=meal.kcal_target,
        )
        index = plan.meals.index(meal)
        replacement = await self._new_meal(plan, request, meal_id=self._new_id())
        plan.meals[index] = replacement
        return replacement

    def _meal_type(self, meal: PlannedMeal) -> MealType:
        slot = self._resolver().settings.slot(meal.slot)
        if slot is not None:
            return slot.meal_type
        return meal.recipe.meal_types[0]

    # ----------------------------------------------------------------- queries

    def shopping_list(self, draft: bool = False) -> list[Ingredient]:
        """Aggregated ingredients of all uncooked meals."""
        plan = self._state.draft if draft else self._state.active
        if plan is None:
            raise PlannerError("no_draft" if draft else "no_plan")
        totals: dict[tuple[str, str], Ingredient] = {}
        for meal in plan.meals:
            if meal.cooked:
                continue
            for item in meal.scaled_ingredients():
                key = (item.name.casefold(), item.unit.casefold())
                if key in totals:
                    prev = totals[key]
                    totals[key] = Ingredient(prev.name, prev.quantity + item.quantity, prev.unit)
                else:
                    totals[key] = item
        return sorted(totals.values(), key=lambda i: i.name.casefold())

    def meals_on(self, day: date) -> list[PlannedMeal]:
        active = self._state.active
        return [m for m in active.meals if m.day == day] if active else []

    def next_meal(self, now: datetime) -> PlannedMeal | None:
        """The earliest uncooked meal of the active plan."""
        active = self._state.active
        if not active:
            return None
        resolver = self._resolver()
        uncooked = [m for m in active.meals if not m.cooked]

        def when(meal: PlannedMeal) -> tuple[date, str]:
            slot = resolver.settings.slot(meal.slot)
            return meal.day, slot.time if slot else "99:99"

        return min(uncooked, key=when, default=None)
