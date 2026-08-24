"""Sensor platform for Holdsport."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN, MAX_TASK_ATTRIBUTES
from .coordinator import HoldsportDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Holdsport sensors based on a config entry."""
    coordinator: HoldsportDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = [HoldsportUserSensor(coordinator, entry)]
    for team in coordinator.data.get("teams", []):
        entities.extend(
            [
                HoldsportTeamNextActivitySensor(coordinator, entry, team),
                HoldsportTeamMetricSensor(coordinator, entry, team, "activities"),
                HoldsportTeamMetricSensor(coordinator, entry, team, "members"),
                HoldsportTeamMetricSensor(coordinator, entry, team, "notes"),
            ]
        )

    async_add_entities(entities)


class HoldsportBaseEntity(CoordinatorEntity[HoldsportDataUpdateCoordinator], SensorEntity):
    """Base entity for Holdsport sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HoldsportDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry

    @property
    def device_info(self) -> DeviceInfo:
        """Return shared account device info."""
        user = self.coordinator.data.get("user", {})
        display_name = f"{user.get('firstname', '')} {user.get('lastname', '')}".strip()
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=display_name or self._entry.data[CONF_USERNAME],
            manufacturer="Holdsport",
            model="Account",
        )


class HoldsportUserSensor(HoldsportBaseEntity):
    """Sensor describing current authenticated profile."""

    def __init__(self, coordinator: HoldsportDataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_translation_key = "user_name"
        self._attr_unique_id = f"{entry.entry_id}_user"

    @property
    def native_value(self) -> str | None:
        """Return current user name."""
        user = self.coordinator.data.get("user", {})
        display_name = f"{user.get('firstname', '')} {user.get('lastname', '')}".strip()
        return display_name or None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return user attributes."""
        user = self.coordinator.data.get("user", {})
        return {
            "id": user.get("id"),
            "birthday": user.get("birthday"),
            "age": user.get("age"),
            "gender": user.get("gender"),
            "team_count": len(self.coordinator.data.get("teams", [])),
            "addresses": user.get("addresses", []),
        }


class HoldsportTeamBaseEntity(HoldsportBaseEntity):
    """Base entity for team-specific sensors."""

    def __init__(
        self,
        coordinator: HoldsportDataUpdateCoordinator,
        entry: ConfigEntry,
        team: dict[str, Any],
    ) -> None:
        super().__init__(coordinator, entry)
        self._team = team
        self._team_id = str(team["id"])

    @property
    def device_info(self) -> DeviceInfo:
        """Return team device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.entry_id}_{self._team_id}")},
            name=self._team.get("name", f"Team {self._team_id}"),
            manufacturer="Holdsport",
            model="Team",
            via_device=(DOMAIN, self._entry.entry_id),
        )


class HoldsportTeamMetricSensor(HoldsportTeamBaseEntity):
    """Sensor exposing counts for team collections."""

    def __init__(
        self,
        coordinator: HoldsportDataUpdateCoordinator,
        entry: ConfigEntry,
        team: dict[str, Any],
        metric: str,
    ) -> None:
        super().__init__(coordinator, entry, team)
        self._metric = metric
        self._attr_translation_key = f"team_{metric}_count"
        self._attr_unique_id = f"{entry.entry_id}_{self._team_id}_{metric}_count"

    @property
    def native_value(self) -> int:
        """Return collection size."""
        return len(self.coordinator.data.get(self._metric, {}).get(self._team_id, []))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose team details."""
        return {
            "team_id": int(self._team_id),
            "team_name": self._team.get("name"),
            "role": self._team.get("role"),
        }


class HoldsportTeamNextActivitySensor(HoldsportTeamBaseEntity):
    """Sensor exposing next upcoming activity details for a team."""

    def __init__(
        self,
        coordinator: HoldsportDataUpdateCoordinator,
        entry: ConfigEntry,
        team: dict[str, Any],
    ) -> None:
        super().__init__(coordinator, entry, team)
        self._attr_translation_key = "team_next_activity"
        self._attr_unique_id = f"{entry.entry_id}_{self._team_id}_next_activity"

    def _next_activity(self) -> dict[str, Any] | None:
        activities = self.coordinator.data.get("activities", {}).get(self._team_id, [])
        best: tuple[datetime, dict[str, Any]] | None = None
        now = dt_util.utcnow()

        for activity in activities:
            start = activity.get("starttime")
            if not start:
                continue
            start_time = dt_util.parse_datetime(start)
            if start_time is None:
                continue
            start_time = dt_util.as_utc(start_time)
            if start_time < now:
                continue
            if best is None or start_time < best[0]:
                best = (start_time, activity)

        return best[1] if best else None

    @property
    def native_value(self) -> str | None:
        """Return next activity name."""
        activity = self._next_activity()
        if not activity:
            return None
        return activity.get("name")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return details of the next activity plus snapshots."""
        activity = self._next_activity()
        tasks = self.coordinator.data.get("activity_tasks", {}).get(self._team_id, {})
        if not activity:
            return {
                "team_id": int(self._team_id),
                "team_name": self._team.get("name"),
                "team_role": self._team.get("role"),
                "activities_count": len(
                    self.coordinator.data.get("activities", {}).get(self._team_id, [])
                ),
                "members_count": len(self.coordinator.data.get("members", {}).get(self._team_id, [])),
                "notes_count": len(self.coordinator.data.get("notes", {}).get(self._team_id, [])),
            }

        activity_id = str(activity.get("id"))
        return {
            "team_id": int(self._team_id),
            "team_name": self._team.get("name"),
            "team_role": self._team.get("role"),
            "activity_id": activity.get("id"),
            "starttime": activity.get("starttime"),
            "endtime": activity.get("endtime"),
            "status": activity.get("status"),
            "place": activity.get("place"),
            "comment": activity.get("comment"),
            "no_rsvp_count": activity.get("no_rsvp_count"),
            "no_rsvp": activity.get("no_rsvp", []),
            "available_actions": activity.get("actions", []),
            "action_method": activity.get("action_method"),
            "action_path": activity.get("action_path"),
            "rides": activity.get("rides", []),
            "ride_comment": activity.get("ride_comment"),
            "tasks": tasks.get(activity_id, [])[:MAX_TASK_ATTRIBUTES],
            "tasks_count": len(tasks.get(activity_id, [])),
            "activities_count": len(
                self.coordinator.data.get("activities", {}).get(self._team_id, [])
            ),
            "members_count": len(self.coordinator.data.get("members", {}).get(self._team_id, [])),
            "notes_count": len(self.coordinator.data.get("notes", {}).get(self._team_id, [])),
        }
