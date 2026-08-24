"""Holdsport API client."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import aiohttp

from .const import API_PREFIX, BASE_URL


class HoldsportApiError(Exception):
    """General Holdsport API error."""


class HoldsportAuthError(HoldsportApiError):
    """Authentication error."""


class HoldsportApiClient:
    """Async client for the Holdsport API."""

    def __init__(self, session: aiohttp.ClientSession, username: str, password: str) -> None:
        self._session = session
        self._auth = aiohttp.BasicAuth(username, password)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{BASE_URL}{path}"
        try:
            async with asyncio.timeout(30):
                async with self._session.request(
                    method,
                    url,
                    auth=self._auth,
                    params=params,
                    json=json_data,
                    headers={"Accept": "application/json"},
                ) as response:
                    if response.status in (401, 403):
                        raise HoldsportAuthError("Invalid Holdsport credentials")
                    if response.status >= 400:
                        body = await response.text()
                        raise HoldsportApiError(
                            f"Holdsport API error {response.status} for {path}: {body}"
                        )
                    if response.status == 204 or response.content_length == 0:
                        return None
                    body = await response.text()
                    if not body.strip():
                        return None
                    return json.loads(body)
        except aiohttp.ClientError as err:
            raise HoldsportApiError(f"Connection error: {err}") from err
        except TimeoutError as err:
            raise HoldsportApiError("Request to Holdsport timed out") from err
        except json.JSONDecodeError as err:
            raise HoldsportApiError(f"Invalid JSON response from Holdsport: {err}") from err

    async def async_get_user(self) -> dict[str, Any]:
        """Fetch current user profile."""
        return await self._request("GET", f"{API_PREFIX}/user")

    async def async_get_teams(self) -> list[dict[str, Any]]:
        """Fetch teams available to the user."""
        return await self._request("GET", f"{API_PREFIX}/teams")

    async def async_get_activities(self, team_id: int, *, page: int = 1, per_page: int = 50) -> list[dict[str, Any]]:
        """Fetch team activities."""
        return await self._request(
            "GET",
            f"{API_PREFIX}/teams/{team_id}/activities",
            params={"page": page, "per_page": per_page},
        )

    async def async_get_all_activities(
        self, team_id: int, *, per_page: int = 50
    ) -> list[dict[str, Any]]:
        """Fetch all pages of team activities."""
        activities: list[dict[str, Any]] = []
        page = 1

        while True:
            activity_page = await self.async_get_activities(
                team_id, page=page, per_page=per_page
            )
            activities.extend(activity_page)
            if len(activity_page) < per_page:
                return activities
            page += 1

    async def async_get_members(self, team_id: int) -> list[dict[str, Any]]:
        """Fetch team members."""
        return await self._request("GET", f"{API_PREFIX}/teams/{team_id}/members")

    async def async_get_notes(self, team_id: int) -> list[dict[str, Any]]:
        """Fetch team notes."""
        return await self._request("GET", f"{API_PREFIX}/teams/{team_id}/notes")

    async def async_get_activity_tasks(self, activity_id: int) -> list[dict[str, Any]]:
        """Fetch tasks for an activity."""
        return await self._request("GET", f"{API_PREFIX}/activities/{activity_id}/activity_tasks")

    async def async_execute_activity_action(self, activity: dict[str, Any], action_index: int = 0) -> Any:
        """Execute an action for an activity based on activity metadata."""
        method = activity.get("action_method")
        action_path = activity.get("action_path")
        actions = activity.get("actions") or []

        if not method or not action_path:
            raise HoldsportApiError("Activity does not expose actionable method/path")
        if actions and action_index >= len(actions):
            raise HoldsportApiError("Selected action index does not exist for activity")

        payload: dict[str, Any] | None = None
        if method.upper() != "DELETE" and actions:
            payload = actions[action_index]

        return await self._request(method.upper(), action_path, json_data=payload)

    async def async_add_activity_comment(self, activity_id: int, comment: str) -> Any:
        """Add comment to activity."""
        return await self._request(
            "POST",
            f"{API_PREFIX}/activities/{activity_id}/comments",
            json_data={"comment": {"body": comment}},
        )

    async def async_add_ride(self, activity_id: int, seats: int, comment: str = "") -> Any:
        """Add ride offer to activity."""
        return await self._request(
            "POST",
            f"{API_PREFIX}/activities/{activity_id}/rides",
            json_data={"ride": {"seats": seats, "comment": comment}},
        )

    async def async_remove_ride(self, activity_id: int, ride_id: int) -> Any:
        """Remove ride from activity."""
        return await self._request("DELETE", f"{API_PREFIX}/activities/{activity_id}/rides/{ride_id}")

    async def async_assign_activity_task(self, activity_id: int, task_type_id: int, user_id: int | None = None) -> Any:
        """Assign activity task to current user or a specific user."""
        payload: dict[str, Any] = {"task_type_id": task_type_id}
        if user_id is not None:
            payload["user_id"] = user_id
        return await self._request(
            "POST",
            f"{API_PREFIX}/activities/{activity_id}/activity_tasks",
            json_data={"activity_task": payload},
        )
