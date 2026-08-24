"""Calendar platform for Holdsport activities."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import HoldsportDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Holdsport team calendars."""
    coordinator: HoldsportDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        HoldsportTeamCalendar(coordinator, entry, team)
        for team in coordinator.data.get("teams", [])
    )


class HoldsportTeamCalendar(
    CoordinatorEntity[HoldsportDataUpdateCoordinator], CalendarEntity
):
    """Expose a team's Holdsport activities as a calendar."""

    _attr_has_entity_name = True
    _attr_translation_key = "team_calendar"

    def __init__(
        self,
        coordinator: HoldsportDataUpdateCoordinator,
        entry: ConfigEntry,
        team: dict[str, Any],
    ) -> None:
        """Initialize the team calendar."""
        super().__init__(coordinator)
        self._entry = entry
        self._team = team
        self._team_id = str(team["id"])
        self._attr_unique_id = f"{entry.entry_id}_{self._team_id}_calendar"

    @property
    def device_info(self) -> DeviceInfo:
        """Return team device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.entry_id}_{self._team_id}")},
            name=self._team.get("name", f"Team {self._team_id}"),
            manufacturer="Holdsport",
            model="Team",
            via_device=(DOMAIN, self._entry.entry_id),
        )

    @property
    def event(self) -> CalendarEvent | None:
        """Return a current or next upcoming calendar event."""
        now = dt_util.now()
        current_events: list[CalendarEvent] = []
        upcoming_events: list[CalendarEvent] = []

        for event in self._calendar_events():
            if event.end <= now:
                continue
            if event.start <= now:
                current_events.append(event)
            else:
                upcoming_events.append(event)

        if current_events:
            return min(current_events, key=lambda event: event.start)
        if upcoming_events:
            return min(upcoming_events, key=lambda event: event.start)
        return None

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return events that overlap a requested date range."""
        return sorted(
            (
                event
                for event in self._calendar_events()
                if event.end > start_date and event.start < end_date
            ),
            key=lambda event: event.start,
        )

    def _calendar_events(self) -> list[CalendarEvent]:
        """Build calendar events from the coordinator's activity snapshot."""
        events: list[CalendarEvent] = []
        activities = self.coordinator.data.get("activities", {}).get(self._team_id, [])
        for activity in activities:
            event = self._activity_to_event(activity)
            if event is not None:
                events.append(event)
        return events

    def _activity_to_event(self, activity: dict[str, Any]) -> CalendarEvent | None:
        """Translate a Holdsport activity to a Home Assistant calendar event."""
        start = dt_util.parse_datetime(activity.get("starttime", ""))
        end = dt_util.parse_datetime(activity.get("endtime", ""))
        activity_id = activity.get("id")
        if start is None or end is None or start >= end or activity_id is None:
            return None

        return CalendarEvent(
            summary=str(activity.get("name") or "Holdsport activity"),
            start=start,
            end=end,
            description=self._description(activity),
            location=activity.get("place") or None,
            uid=f"holdsport-{self._team_id}-{activity_id}",
        )

    def _description(self, activity: dict[str, Any]) -> str | None:
        """Return a compact activity description for calendar cards."""
        details: list[str] = []
        comment = activity.get("comment")
        if comment:
            details.append(str(comment).strip())

        event_type = activity.get("event_type")
        if event_type:
            details.append(f"Type: {event_type}")

        response = self._user_response(activity)
        if response:
            details.append(f"Your response: {response}")

        registered = sum(
            attendee.get("status_code") == 1
            for attendee in activity.get("activities_users", [])
        )
        declined = sum(
            attendee.get("status_code") == 2
            for attendee in activity.get("activities_users", [])
        )
        if registered or declined or activity.get("no_rsvp_count"):
            details.append(
                "Responses: "
                f"{registered} attending, {declined} declined, "
                f"{activity.get('no_rsvp_count', 0)} awaiting reply"
            )

        return "\n\n".join(details) or None

    def _user_response(self, activity: dict[str, Any]) -> str | None:
        """Find the authenticated user's response for an activity."""
        user_id = self.coordinator.data.get("user", {}).get("id")
        if user_id is None:
            return None

        for attendee in activity.get("activities_users", []):
            if attendee.get("user_id") == user_id:
                return attendee.get("status")

        if any(person.get("id") == user_id for person in activity.get("no_rsvp", [])):
            return "Awaiting response"
        return None