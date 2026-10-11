"""Planner use cases."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from custom_components.meal_manager.core.models import PlannerState, PlanStatus
from custom_components.meal_manager.core.planner import MealPlanner, PlannerError, PlannerOptions
from custom_components.meal_manager.core.settings import (
    PlannerSettings,
    Setting,
    SettingsResolver,
    ValueSource,
)

from .fakes import FixedClock, MemoryStore, RecordingEvents, catalog

NOW = datetime(2026, 10, 12, 9, 0)


def make(
    settings: PlannerSettings | None = None, **options
) -> tuple[MealPlanner, RecordingEvents, MemoryStore]:
    events = RecordingEvents()
    store = MemoryStore()
    settings = settings or PlannerSettings()
    planner = MealPlanner(
        store=store,
        source=catalog(),
        resolver=lambda: SettingsResolver(settings, lambda *_: None),
        events=events,
        clock=FixedClock(NOW),
        options=PlannerOptions(**options),
    )
    return planner, events, store


async def test_generate_and_accept() -> None:
    planner, events, store = make()
    draft = await planner.generate_draft(days=3)
    assert draft.status is PlanStatus.DRAFT
    assert len(draft.meals) == 9
    assert len(draft.titles()) == 9, "no dish twice in a plan"
    assert events.names() == ["draft_ready"]

    await planner.accept_draft()
    assert planner.state.active is draft
    assert planner.state.draft is None
    assert PlannerState.from_dict(store.data).to_dict() == planner.state.to_dict()


async def test_effort_and_calories_respected() -> None:
    settings = PlannerSettings(
        defaults={Setting.EFFORT: ValueSource(value=1), Setting.CALORIES: ValueSource(value=2000)}
    )
    planner, _, _ = make(settings)
    draft = await planner.generate_draft(days=2)
    assert all(m.recipe.effort == 1 for m in draft.meals)
    dinner = next(m for m in draft.meals if m.slot == "dinner")
    assert dinner.kcal_target == 737
    assert 0.75 <= dinner.scale <= 1.5
    portions = dinner.portions * dinner.scale
    assert dinner.scaled_ingredients()[1].quantity == round(100 * portions, 1)


async def test_cook_all_offers_new_plan() -> None:
    planner, events, _ = make(default_days=2)
    await planner.generate_draft(days=1)
    plan = await planner.accept_draft()
    for meal in plan.meals:
        await planner.mark_cooked(meal.id)
    assert plan.status is PlanStatus.COMPLETED
    assert "plan_completed" in events.names()
    assert planner.state.draft is not None
    assert events.names()[-1] == "draft_ready"
    # Recently cooked dishes are avoided in the new plan.
    assert not planner.state.draft.titles() & plan.titles()

    await planner.mark_cooked(plan.meals[0].id, cooked=False)
    assert plan.status is PlanStatus.ACTIVE
    assert len(planner.state.history) == 2


async def test_no_auto_plan_when_disabled() -> None:
    planner, _, _ = make(auto_new_plan=False)
    await planner.generate_draft(days=1)
    plan = await planner.accept_draft()
    for meal in plan.meals:
        await planner.mark_cooked(meal.id)
    assert planner.state.draft is None


async def test_cooking_draft_meal_fails() -> None:
    planner, _, _ = make()
    draft = await planner.generate_draft(days=1)
    with pytest.raises(PlannerError, match="not_active"):
        await planner.mark_cooked(draft.meals[0].id)


async def test_decline_replaces_and_remembers() -> None:
    planner, _, _ = make()
    draft = await planner.generate_draft(days=1)
    old = draft.meals[0]
    new = await planner.decline_meal(old.id)
    assert new.recipe.key != old.recipe.key
    assert draft.meals[0] is new
    assert old.recipe.key in draft.declined
    assert new.slot == old.slot and new.day == old.day


async def test_ban_replaces_everywhere_and_excludes() -> None:
    planner, _, _ = make()
    draft = await planner.generate_draft(days=1)
    title = draft.meals[1].recipe.title
    await planner.ban_meal(meal_id=draft.meals[1].id)
    assert title not in {m.recipe.title for m in draft.meals}
    assert [b.title for b in planner.state.bans] == [title]
    for _ in range(5):
        again = await planner.generate_draft(days=3)
        assert title not in {m.recipe.title for m in again.meals}

    await planner.unban(title.upper())
    assert planner.state.bans == []
    with pytest.raises(PlannerError, match="not_banned"):
        await planner.unban(title)


async def test_ban_by_title() -> None:
    planner, _, _ = make()
    ban = await planner.ban_meal(title="  Main 3 ")
    assert ban.title == "Main 3"
    await planner.ban_meal(title="main 3")
    assert len(planner.state.bans) == 1


async def test_runs_out_of_recipes() -> None:
    planner, events, _ = make(PlannerSettings(defaults={Setting.MEALS_PER_DAY: ValueSource(value=4)}))
    with pytest.raises(PlannerError, match="no_recipe"):
        await planner.generate_draft(days=6)  # only 5 snacks exist
    assert events.names() == ["generation_failed"]
    assert planner.generating is False


async def test_default_start_follows_active_plan() -> None:
    planner, _, _ = make()
    await planner.generate_draft(days=3)
    await planner.accept_draft()
    nxt = await planner.generate_draft()
    assert nxt.start == NOW.date() + timedelta(days=3)
    assert nxt.days == 7


async def test_shopping_list_aggregates_uncooked() -> None:
    planner, _, _ = make()
    await planner.generate_draft(days=1)
    plan = await planner.accept_draft()
    await planner.mark_cooked(plan.meals[0].id)
    items = planner.shopping_list()
    onion = next(i for i in items if i.name == "onion")
    expected = sum(0.5 * m.portions * m.scale for m in plan.meals[1:])
    assert onion.quantity == pytest.approx(expected)
    assert len(items) == 3  # onion + two dish bases


async def test_next_meal_and_find_slot() -> None:
    planner, _, _ = make()
    await planner.generate_draft(days=2)
    plan = await planner.accept_draft()
    first = planner.next_meal(NOW)
    assert first.slot == "breakfast" and first.day == date(2026, 10, 12)
    await planner.mark_cooked(first.id)
    assert planner.next_meal(NOW).slot == "lunch"
    assert planner.find_slot(date(2026, 10, 13), "dinner") in plan.meals
