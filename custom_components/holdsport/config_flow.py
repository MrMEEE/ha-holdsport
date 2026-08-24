"""Config flow for Holdsport integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL, DOMAIN
from .holdsport_api import HoldsportApiClient, HoldsportAuthError, HoldsportApiError


async def _validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate user input allows us to connect."""
    client = HoldsportApiClient(
        async_get_clientsession(hass),
        data[CONF_USERNAME],
        data[CONF_PASSWORD],
    )

    user = await client.async_get_user()
    teams = await client.async_get_teams()

    first_name = user.get("firstname", "")
    last_name = user.get("lastname", "")
    title = f"{first_name} {last_name}".strip() or str(user.get("id", data[CONF_USERNAME]))

    return {
        "title": title,
        "team_count": len(teams),
    }


class HoldsportConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Holdsport."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await _validate_input(self.hass, user_input)
            except HoldsportAuthError:
                errors["base"] = "invalid_auth"
            except HoldsportApiError:
                errors["base"] = "cannot_connect"
            except Exception:  # pragma: no cover
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user_input[CONF_USERNAME])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"{info['title']} ({info['team_count']} teams)",
                    data={
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                    options={
                        CONF_UPDATE_INTERVAL: user_input[CONF_UPDATE_INTERVAL],
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Optional(CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=360)
                ),
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Get the options flow for this handler."""
        return HoldsportOptionsFlow(config_entry)


class HoldsportOptionsFlow(config_entries.OptionsFlow):
    """Options flow for Holdsport."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_UPDATE_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=360)),
                }
            ),
        )
