"""Integration tests against a real Home Assistant core."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ServiceValidationError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.meal_manager.config_flow import default_options
from custom_components.meal_manager.const import DOMAIN, OPT_DEFAULTS, OPT_GENERAL


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading custom_components."""
    return


async def setup(hass: HomeAssistant, **overrides) -> MockConfigEntry:
    options = default_options()
    options.update(overrides)
    entry = MockConfigEntry(domain=DOMAIN, options=options)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_config_flow_single_instance(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    again = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert again["type"] is FlowResultType.ABORT


async def test_bundled_recipes_load(hass: HomeAssistant) -> None:
    entry = await setup(hass)
    assert entry.runtime_data.catalog.count() > 100


async def test_full_cycle(hass: HomeAssistant) -> None:
    hass.states.async_set("sensor.kcal", "2200")
    entry = await setup(
        hass,
        **{OPT_DEFAULTS: {"calories": {"entity_id": "sensor.kcal", "value": 2000}, "portions": {"value": 3}}},
    )
    response = await hass.services.async_call(
        DOMAIN, "generate_plan", {"days": 2}, blocking=True, return_response=True
    )
    assert response["meals"] == 6
    await hass.services.async_call(DOMAIN, "accept_plan", {}, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.meal_manager_plan_status").state == "active"

    plan = entry.runtime_data.planner.state.active
    assert {m.portions for m in plan.meals} == {3}
    assert sum(m.kcal_target for m in plan.meals if m.day == plan.start) == pytest.approx(2200, abs=2)

    today_dinner = hass.states.get("sensor.meal_manager_today_dinner")
    assert today_dinner.state == next(
        m.recipe.title for m in plan.meals if m.slot == "dinner" and m.day == plan.start
    )

    first = plan.meals[0]
    await hass.services.async_call(DOMAIN, "decline_meal", {"meal_id": first.id}, blocking=True)
    title = plan.meals[1].recipe.title
    await hass.services.async_call(DOMAIN, "ban_meal", {"meal_id": plan.meals[1].id}, blocking=True)
    assert title not in {m.recipe.title for m in plan.meals}

    events = []
    hass.bus.async_listen("meal_manager_draft_ready", events.append)
    for meal in list(plan.meals):
        await hass.services.async_call(DOMAIN, "mark_cooked", {"meal_id": meal.id}, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.meal_manager_plan_status").state == "completed"
    assert events, "a new plan is offered when everything is cooked"
    assert hass.states.get("sensor.meal_manager_plan_status").attributes["draft_pending"] is True


async def test_mark_cooked_by_slot_and_errors(hass: HomeAssistant) -> None:
    await setup(hass)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "accept_plan", {}, blocking=True)
    await hass.services.async_call(DOMAIN, "generate_plan", {"days": 1}, blocking=True)
    await hass.services.async_call(DOMAIN, "accept_plan", {}, blocking=True)
    await hass.services.async_call(DOMAIN, "mark_cooked", {"slot": "lunch"}, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.meal_manager_plan_status").attributes["cooked"] == 1


async def test_shopping_list_to_todo(hass: HomeAssistant) -> None:
    calls = []

    async def add_item(call):
        calls.append(call.data["item"])

    hass.services.async_register("todo", "add_item", add_item)
    await setup(hass, **{OPT_GENERAL: {**default_options()[OPT_GENERAL], "shopping_list": "todo.shopping"}})
    await hass.services.async_call(DOMAIN, "generate_plan", {"days": 1}, blocking=True)
    await hass.services.async_call(DOMAIN, "accept_plan", {}, blocking=True)
    response = await hass.services.async_call(
        DOMAIN, "add_to_shopping_list", {}, blocking=True, return_response=True
    )
    assert response["entity_id"] == "todo.shopping"
    assert calls == response["items"] and calls


async def test_calendar_events(hass: HomeAssistant) -> None:
    await setup(hass)
    await hass.services.async_call(DOMAIN, "generate_plan", {"days": 1}, blocking=True)
    await hass.services.async_call(DOMAIN, "accept_plan", {}, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get("calendar.meal_manager_meal_plan") is not None


async def test_websocket_subscription(hass: HomeAssistant, hass_ws_client) -> None:
    await setup(hass)
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "meal_manager/subscribe"})
    assert (await client.receive_json())["success"]
    view = (await client.receive_json())["event"]
    assert view["loaded"] and view["active"] is None and len(view["preview"]) == 7

    await hass.services.async_call(DOMAIN, "generate_plan", {"days": 1}, blocking=True)
    while True:
        view = (await client.receive_json())["event"]
        if view["draft"]:
            break
    assert view["draft"]["total"] == 3
    assert view["draft"]["meals"][0]["slot"] == "breakfast"


async def test_ai_task_source_with_fallback(hass: HomeAssistant) -> None:
    answers = iter(
        [
            {
                "title": "Model Porridge",
                "minutes": 10,
                "kcal": 400,
                "health": 4,
                "ingredients": "50 | g | oats\n200 | ml | milk",
                "steps": "Cook.",
            },
        ]
    )

    async def fake_generate(hass, **kwargs):
        try:
            data = next(answers)
        except StopIteration:
            from homeassistant.exceptions import HomeAssistantError  # noqa: PLC0415

            raise HomeAssistantError("model offline") from None
        return SimpleNamespace(data=data)

    with patch("custom_components.meal_manager.adapters.generate_data", fake_generate):
        entry = await setup(
            hass, **{OPT_GENERAL: {**default_options()[OPT_GENERAL], "ai_task_entity": "ai_task.local"}}
        )
        await hass.services.async_call(DOMAIN, "generate_plan", {"days": 1}, blocking=True)
    draft = entry.runtime_data.planner.state.draft
    assert draft.meals[0].recipe.title == "Model Porridge"
    assert draft.meals[0].recipe.source == "ai"
    assert all(m.recipe.source == "builtin" for m in draft.meals[1:])


async def test_options_flow_override(hass: HomeAssistant) -> None:
    entry = await setup(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "add_override"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"setting": "calories", "weekday": "sat", "slot": "dinner"}
    )
    assert result["errors"] == {"slot": "day_scoped"}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"setting": "portions", "weekday": "sat", "slot": "dinner"}
    )
    assert result["step_id"] == "override_value"
    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert result["errors"] == {"base": "value_required"}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"value": 4, "entity_id": "zone.home"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options["overrides"] == [
        {"setting": "portions", "weekday": 5, "slot": "dinner", "value": 4, "entity_id": "zone.home"}
    ]


async def test_options_flow_defaults(hass: HomeAssistant) -> None:
    entry = await setup(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "defaults"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "portions": {"value": 2},
            "effort": {"value": "1"},
            "health": {},
            "calories": {"entity_id": "sensor.kcal", "value": 1800},
            "meals_per_day": {"value": 2},
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options["defaults"]["calories"] == {"value": 1800, "entity_id": "sensor.kcal"}
    assert "health" not in entry.options["defaults"]
