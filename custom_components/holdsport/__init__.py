"""Holdsport integration."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    ATTR_ACTION_INDEX,
    ATTR_ACTIVITY_ID,
    ATTR_COMMENT,
    ATTR_ENTRY_ID,
    ATTR_RIDE_ID,
    ATTR_SEATS,
    ATTR_TASK_TYPE_ID,
    ATTR_TEAM_ID,
    ATTR_USER_ID,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    PLATFORMS,
    SERVICE_ADD_ACTIVITY_COMMENT,
    SERVICE_ADD_ACTIVITY_RIDE,
    SERVICE_ASSIGN_ACTIVITY_TASK,
    SERVICE_EXECUTE_ACTIVITY_ACTION,
    SERVICE_REMOVE_ACTIVITY_RIDE,
)
from .coordinator import HoldsportDataUpdateCoordinator
from .holdsport_api import HoldsportApiClient, HoldsportApiError

_LOGGER = logging.getLogger(__name__)

SERVICE_EXECUTE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTRY_ID): cv.string,
        vol.Required(ATTR_TEAM_ID): vol.Coerce(int),
        vol.Required(ATTR_ACTIVITY_ID): vol.Coerce(int),
        vol.Optional(ATTR_ACTION_INDEX, default=0): vol.Coerce(int),
    }
)
SERVICE_ADD_COMMENT_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTRY_ID): cv.string,
        vol.Required(ATTR_ACTIVITY_ID): vol.Coerce(int),
        vol.Required(ATTR_COMMENT): cv.string,
    }
)
SERVICE_ADD_RIDE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTRY_ID): cv.string,
        vol.Required(ATTR_ACTIVITY_ID): vol.Coerce(int),
        vol.Required(ATTR_SEATS): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Optional(ATTR_COMMENT, default=""): cv.string,
    }
)
SERVICE_REMOVE_RIDE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTRY_ID): cv.string,
        vol.Required(ATTR_ACTIVITY_ID): vol.Coerce(int),
        vol.Required(ATTR_RIDE_ID): vol.Coerce(int),
    }
)
SERVICE_ASSIGN_TASK_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTRY_ID): cv.string,
        vol.Required(ATTR_ACTIVITY_ID): vol.Coerce(int),
        vol.Required(ATTR_TASK_TYPE_ID): vol.Coerce(int),
        vol.Optional(ATTR_USER_ID): vol.Coerce(int),
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Holdsport from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    session = async_get_clientsession(hass)
    client = HoldsportApiClient(session, entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
    coordinator = HoldsportDataUpdateCoordinator(
        hass,
        client,
        update_interval_minutes=entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
    )

    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator

    if not hass.services.has_service(DOMAIN, SERVICE_EXECUTE_ACTIVITY_ACTION):
        _register_services(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_options))
    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Holdsport config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def _get_coordinator(hass: HomeAssistant, entry_id: str | None) -> HoldsportDataUpdateCoordinator:
    entries: dict[str, HoldsportDataUpdateCoordinator] = hass.data.get(DOMAIN, {})
    if not entries:
        raise HomeAssistantError("No Holdsport config entries are loaded")

    if entry_id:
        coordinator = entries.get(entry_id)
        if coordinator is None:
            raise HomeAssistantError(f"Holdsport entry '{entry_id}' not found")
        return coordinator

    return next(iter(entries.values()))


def _find_activity(
    coordinator: HoldsportDataUpdateCoordinator,
    team_id: int,
    activity_id: int,
) -> dict:
    team_activities = coordinator.data.get("activities", {}).get(str(team_id), [])
    for activity in team_activities:
        try:
            found_id = int(activity.get("id"))
        except (TypeError, ValueError):
            continue
        if found_id == activity_id:
            return activity
    raise HomeAssistantError(f"Activity {activity_id} not found in team {team_id}")


def _register_services(hass: HomeAssistant) -> None:
    """Register Holdsport services."""

    async def handle_execute_action(call: ServiceCall) -> None:
        coordinator = await _get_coordinator(hass, call.data.get(ATTR_ENTRY_ID))
        team_id = call.data[ATTR_TEAM_ID]
        activity_id = call.data[ATTR_ACTIVITY_ID]
        action_index = call.data[ATTR_ACTION_INDEX]

        activity = _find_activity(coordinator, team_id, activity_id)
        try:
            await coordinator.client.async_execute_activity_action(activity, action_index)
            await coordinator.async_request_refresh()
        except HoldsportApiError as err:
            raise HomeAssistantError(f"Failed to execute activity action: {err}") from err

    async def handle_add_comment(call: ServiceCall) -> None:
        coordinator = await _get_coordinator(hass, call.data.get(ATTR_ENTRY_ID))
        try:
            await coordinator.client.async_add_activity_comment(
                call.data[ATTR_ACTIVITY_ID], call.data[ATTR_COMMENT]
            )
            await coordinator.async_request_refresh()
        except HoldsportApiError as err:
            raise HomeAssistantError(f"Failed to add activity comment: {err}") from err

    async def handle_add_ride(call: ServiceCall) -> None:
        coordinator = await _get_coordinator(hass, call.data.get(ATTR_ENTRY_ID))
        try:
            await coordinator.client.async_add_ride(
                call.data[ATTR_ACTIVITY_ID],
                call.data[ATTR_SEATS],
                call.data[ATTR_COMMENT],
            )
            await coordinator.async_request_refresh()
        except HoldsportApiError as err:
            raise HomeAssistantError(f"Failed to add activity ride: {err}") from err

    async def handle_remove_ride(call: ServiceCall) -> None:
        coordinator = await _get_coordinator(hass, call.data.get(ATTR_ENTRY_ID))
        try:
            await coordinator.client.async_remove_ride(
                call.data[ATTR_ACTIVITY_ID], call.data[ATTR_RIDE_ID]
            )
            await coordinator.async_request_refresh()
        except HoldsportApiError as err:
            raise HomeAssistantError(f"Failed to remove activity ride: {err}") from err

    async def handle_assign_task(call: ServiceCall) -> None:
        coordinator = await _get_coordinator(hass, call.data.get(ATTR_ENTRY_ID))
        try:
            await coordinator.client.async_assign_activity_task(
                call.data[ATTR_ACTIVITY_ID],
                call.data[ATTR_TASK_TYPE_ID],
                call.data.get(ATTR_USER_ID),
            )
            await coordinator.async_request_refresh()
        except HoldsportApiError as err:
            raise HomeAssistantError(f"Failed to assign activity task: {err}") from err

    hass.services.async_register(
        DOMAIN,
        SERVICE_EXECUTE_ACTIVITY_ACTION,
        handle_execute_action,
        schema=SERVICE_EXECUTE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_ACTIVITY_COMMENT,
        handle_add_comment,
        schema=SERVICE_ADD_COMMENT_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_ACTIVITY_RIDE,
        handle_add_ride,
        schema=SERVICE_ADD_RIDE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_ACTIVITY_RIDE,
        handle_remove_ride,
        schema=SERVICE_REMOVE_RIDE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_ASSIGN_ACTIVITY_TASK,
        handle_assign_task,
        schema=SERVICE_ASSIGN_TASK_SCHEMA,
    )
