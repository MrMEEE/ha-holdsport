"""Data coordinator for Holdsport."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_UPDATE_INTERVAL, DOMAIN
from .holdsport_api import HoldsportApiClient, HoldsportApiError

_LOGGER = logging.getLogger(__name__)


class HoldsportDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate Holdsport API data updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: HoldsportApiClient,
        *,
        update_interval_minutes: int = DEFAULT_UPDATE_INTERVAL,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=update_interval_minutes),
        )
        self.client = client

    async def _async_team_payload(self, team_id: int) -> dict[str, list[dict[str, Any]]]:
        """Fetch team scoped payload."""

        async def _safe(call_name: str, coro: Any) -> list[dict[str, Any]]:
            try:
                result = await coro
                if isinstance(result, list):
                    return result
                return []
            except HoldsportApiError as err:
                _LOGGER.warning("Unable to fetch %s for team %s: %s", call_name, team_id, err)
                return []

        activities = await _safe("activities", self.client.async_get_activities(team_id))
        members = await _safe("members", self.client.async_get_members(team_id))
        notes = await _safe("notes", self.client.async_get_notes(team_id))

        tasks_map: dict[str, list[dict[str, Any]]] = {}
        for activity in activities:
            activity_id = activity.get("id")
            if activity_id is None:
                continue
            tasks = await _safe("activity_tasks", self.client.async_get_activity_tasks(int(activity_id)))
            tasks_map[str(activity_id)] = tasks

        return {
            "activities": activities,
            "members": members,
            "notes": notes,
            "activity_tasks": tasks_map,
        }

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch all account data from Holdsport."""
        try:
            user = await self.client.async_get_user()
            teams = await self.client.async_get_teams()

            activities: dict[str, list[dict[str, Any]]] = {}
            members: dict[str, list[dict[str, Any]]] = {}
            notes: dict[str, list[dict[str, Any]]] = {}
            activity_tasks: dict[str, dict[str, list[dict[str, Any]]]] = {}

            for team in teams:
                team_id = int(team["id"])
                payload = await self._async_team_payload(team_id)
                team_key = str(team_id)
                activities[team_key] = payload["activities"]
                members[team_key] = payload["members"]
                notes[team_key] = payload["notes"]
                activity_tasks[team_key] = payload["activity_tasks"]

            return {
                "user": user,
                "teams": teams,
                "activities": activities,
                "members": members,
                "notes": notes,
                "activity_tasks": activity_tasks,
            }
        except HoldsportApiError as err:
            raise UpdateFailed(f"Error communicating with Holdsport API: {err}") from err
