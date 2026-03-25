"""Config flow for ENTSO-E Ceny Energii."""
from __future__ import annotations

from typing import Any
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import EntsoeApiClient
from .const import (
    AREA_CHOICES,
    CONF_API_TOKEN,
    CONF_AREA,
    CONF_AUTO_RATE,
    CONF_CURRENCY,
    CONF_CURRENCY_RATE,
    CONF_ENERGY_UNIT,
    CONF_VAT,
    DEFAULT_AREA,
    DEFAULT_CURRENCY,
    DEFAULT_CURRENCY_RATE,
    DEFAULT_ENERGY_UNIT,
    DEFAULT_VAT,
    DOMAIN,
    SUPPORTED_CURRENCIES,
    SUPPORTED_ENERGY_UNITS,
)

_LOGGER = logging.getLogger(__name__)

AREA_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=[
            selector.SelectOptionDict(value=code, label=f"{name} ({code})")
            for name, code in AREA_CHOICES
        ],
        mode=selector.SelectSelectorMode.DROPDOWN,
        custom_value=False,
    )
)


class EntsoeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for ENTSO-E Ceny Energii."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step — API token and basic config."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate token
            token = (user_input.get(CONF_API_TOKEN) or "").strip()
            if not token:
                errors[CONF_API_TOKEN] = "token_required"
            else:
                user_input[CONF_API_TOKEN] = token

            area = user_input.get(CONF_AREA, DEFAULT_AREA)

            # Validate exchange rate for PLN
            currency = user_input.get(CONF_CURRENCY, DEFAULT_CURRENCY)
            auto_rate = user_input.get(CONF_AUTO_RATE, True)
            rate = user_input.get(CONF_CURRENCY_RATE, DEFAULT_CURRENCY_RATE)

            if currency != "EUR" and not auto_rate and (rate is None or rate <= 0):
                errors[CONF_CURRENCY_RATE] = "invalid_rate"

            if not errors:
                # Test API connectivity
                session = async_get_clientsession(self.hass)
                client = EntsoeApiClient(
                    session=session,
                    api_token=token,
                    area=area,
                )
                try:
                    valid = await client.async_test_connection()
                    if not valid:
                        errors["base"] = "connection_failed"
                except Exception:
                    errors["base"] = "connection_failed"

            if not errors:
                # Ensure unique per area
                await self.async_set_unique_id(area)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=self._get_area_name(area),
                    data={
                        CONF_API_TOKEN: token,
                        CONF_AREA: area,
                        CONF_CURRENCY: currency,
                        CONF_ENERGY_UNIT: user_input.get(
                            CONF_ENERGY_UNIT, DEFAULT_ENERGY_UNIT
                        ),
                        CONF_VAT: user_input.get(CONF_VAT, DEFAULT_VAT),
                        CONF_AUTO_RATE: auto_rate,
                        CONF_CURRENCY_RATE: rate,
                    },
                )

        defaults = user_input or {}
        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_API_TOKEN,
                    default=defaults.get(CONF_API_TOKEN, ""),
                ): str,
                vol.Required(
                    CONF_AREA,
                    default=defaults.get(CONF_AREA, DEFAULT_AREA),
                ): AREA_SELECTOR,
                vol.Required(
                    CONF_CURRENCY,
                    default=defaults.get(CONF_CURRENCY, DEFAULT_CURRENCY),
                ): vol.In(SUPPORTED_CURRENCIES),
                vol.Required(
                    CONF_ENERGY_UNIT,
                    default=defaults.get(CONF_ENERGY_UNIT, DEFAULT_ENERGY_UNIT),
                ): vol.In(SUPPORTED_ENERGY_UNITS),
                vol.Optional(
                    CONF_VAT,
                    default=defaults.get(CONF_VAT, DEFAULT_VAT),
                ): vol.Coerce(float),
                vol.Optional(
                    CONF_AUTO_RATE,
                    default=defaults.get(CONF_AUTO_RATE, True),
                ): bool,
                vol.Optional(
                    CONF_CURRENCY_RATE,
                    default=defaults.get(CONF_CURRENCY_RATE, DEFAULT_CURRENCY_RATE),
                ): vol.Coerce(float),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow handler."""
        return EntsoeOptionsFlow()

    @staticmethod
    def _get_area_name(code: str) -> str:
        """Get human-readable area name from code."""
        for name, area_code in AREA_CHOICES:
            if area_code == code:
                return name
        return f"ENTSO-E ({code})"


class EntsoeOptionsFlow(config_entries.OptionsFlow):
    """Options flow for reconfiguring ENTSO-E.

    Since HA 2025.1, OptionsFlow provides self.config_entry automatically.
    Do NOT manually assign self.config_entry in __init__ — it breaks in HA 2025.12+.
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle options."""
        return await self.async_step_options(user_input)

    async def async_step_options(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle options form."""
        errors: dict[str, str] = {}
        current = {**self.config_entry.data}

        if user_input is not None:
            token = (user_input.get(CONF_API_TOKEN) or "").strip()
            if not token:
                errors[CONF_API_TOKEN] = "token_required"

            currency = user_input.get(CONF_CURRENCY, DEFAULT_CURRENCY)
            auto_rate = user_input.get(CONF_AUTO_RATE, True)
            rate = user_input.get(CONF_CURRENCY_RATE, DEFAULT_CURRENCY_RATE)

            if currency != "EUR" and not auto_rate and (rate is None or rate <= 0):
                errors[CONF_CURRENCY_RATE] = "invalid_rate"

            if not errors:
                new_data = {
                    CONF_API_TOKEN: token,
                    CONF_AREA: user_input.get(CONF_AREA, current.get(CONF_AREA, DEFAULT_AREA)),
                    CONF_CURRENCY: currency,
                    CONF_ENERGY_UNIT: user_input.get(
                        CONF_ENERGY_UNIT, DEFAULT_ENERGY_UNIT
                    ),
                    CONF_VAT: user_input.get(CONF_VAT, DEFAULT_VAT),
                    CONF_AUTO_RATE: auto_rate,
                    CONF_CURRENCY_RATE: rate,
                }
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=new_data
                )
                await self.hass.config_entries.async_reload(
                    self.config_entry.entry_id
                )
                return self.async_create_entry(title="", data={})

        defaults = user_input or current
        options_schema = vol.Schema(
            {
                vol.Required(
                    CONF_API_TOKEN,
                    default=defaults.get(CONF_API_TOKEN, ""),
                ): str,
                vol.Required(
                    CONF_AREA,
                    default=defaults.get(CONF_AREA, DEFAULT_AREA),
                ): AREA_SELECTOR,
                vol.Required(
                    CONF_CURRENCY,
                    default=defaults.get(CONF_CURRENCY, DEFAULT_CURRENCY),
                ): vol.In(SUPPORTED_CURRENCIES),
                vol.Required(
                    CONF_ENERGY_UNIT,
                    default=defaults.get(CONF_ENERGY_UNIT, DEFAULT_ENERGY_UNIT),
                ): vol.In(SUPPORTED_ENERGY_UNITS),
                vol.Optional(
                    CONF_VAT,
                    default=defaults.get(CONF_VAT, DEFAULT_VAT),
                ): vol.Coerce(float),
                vol.Optional(
                    CONF_AUTO_RATE,
                    default=defaults.get(CONF_AUTO_RATE, True),
                ): bool,
                vol.Optional(
                    CONF_CURRENCY_RATE,
                    default=defaults.get(CONF_CURRENCY_RATE, DEFAULT_CURRENCY_RATE),
                ): vol.Coerce(float),
            }
        )

        return self.async_show_form(
            step_id="options",
            data_schema=options_schema,
            errors=errors,
        )
