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
    CONF_DISTRIBUTION_RATE,
    CONF_ENERGY_UNIT,
    CONF_EXCISE_TAX,
    CONF_RCE_ENTITY,
    CONF_SELLER_MARGIN,
    CONF_VAT,
    DEFAULT_AREA,
    DEFAULT_CURRENCY,
    DEFAULT_CURRENCY_RATE,
    DEFAULT_DISTRIBUTION_RATE,
    DEFAULT_ENERGY_UNIT,
    DEFAULT_EXCISE_TAX,
    DEFAULT_RCE_ENTITY,
    DEFAULT_SELLER_MARGIN,
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


def _build_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Build the shared config/options schema."""
    return vol.Schema(
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
            vol.Optional(
                CONF_SELLER_MARGIN,
                default=defaults.get(CONF_SELLER_MARGIN, DEFAULT_SELLER_MARGIN),
            ): vol.Coerce(float),
            vol.Optional(
                CONF_EXCISE_TAX,
                default=defaults.get(CONF_EXCISE_TAX, DEFAULT_EXCISE_TAX),
            ): vol.Coerce(float),
            vol.Optional(
                CONF_DISTRIBUTION_RATE,
                default=defaults.get(CONF_DISTRIBUTION_RATE, DEFAULT_DISTRIBUTION_RATE),
            ): vol.Coerce(float),
            vol.Optional(
                CONF_RCE_ENTITY,
                default=defaults.get(CONF_RCE_ENTITY, DEFAULT_RCE_ENTITY),
            ): str,
        }
    )


def _extract_data(user_input: dict[str, Any]) -> dict[str, Any]:
    """Extract and normalize config data from user input."""
    return {
        CONF_API_TOKEN: (user_input.get(CONF_API_TOKEN) or "").strip(),
        CONF_AREA: user_input.get(CONF_AREA, DEFAULT_AREA),
        CONF_CURRENCY: user_input.get(CONF_CURRENCY, DEFAULT_CURRENCY),
        CONF_ENERGY_UNIT: user_input.get(CONF_ENERGY_UNIT, DEFAULT_ENERGY_UNIT),
        CONF_VAT: user_input.get(CONF_VAT, DEFAULT_VAT),
        CONF_AUTO_RATE: user_input.get(CONF_AUTO_RATE, True),
        CONF_CURRENCY_RATE: user_input.get(CONF_CURRENCY_RATE, DEFAULT_CURRENCY_RATE),
        CONF_SELLER_MARGIN: user_input.get(CONF_SELLER_MARGIN, DEFAULT_SELLER_MARGIN),
        CONF_EXCISE_TAX: user_input.get(CONF_EXCISE_TAX, DEFAULT_EXCISE_TAX),
        CONF_DISTRIBUTION_RATE: user_input.get(CONF_DISTRIBUTION_RATE, DEFAULT_DISTRIBUTION_RATE),
        CONF_RCE_ENTITY: (user_input.get(CONF_RCE_ENTITY) or "").strip(),
    }


class EntsoeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for ENTSO-E Ceny Energii."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step — API token and basic config."""
        errors: dict[str, str] = {}

        if user_input is not None:
            data = _extract_data(user_input)

            if not data[CONF_API_TOKEN]:
                errors[CONF_API_TOKEN] = "token_required"

            currency = data[CONF_CURRENCY]
            auto_rate = data[CONF_AUTO_RATE]
            rate = data[CONF_CURRENCY_RATE]

            if currency != "EUR" and not auto_rate and (rate is None or rate <= 0):
                errors[CONF_CURRENCY_RATE] = "invalid_rate"

            if not errors:
                # Test API connectivity
                session = async_get_clientsession(self.hass)
                client = EntsoeApiClient(
                    session=session,
                    api_token=data[CONF_API_TOKEN],
                    area=data[CONF_AREA],
                )
                try:
                    valid = await client.async_test_connection()
                    if not valid:
                        errors["base"] = "connection_failed"
                except Exception:
                    errors["base"] = "connection_failed"

            if not errors:
                area = data[CONF_AREA]
                await self.async_set_unique_id(area)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=self._get_area_name(area),
                    data=data,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_build_schema(user_input or {}),
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
    """Options flow for reconfiguring ENTSO-E."""

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
            data = _extract_data(user_input)

            if not data[CONF_API_TOKEN]:
                errors[CONF_API_TOKEN] = "token_required"

            currency = data[CONF_CURRENCY]
            auto_rate = data[CONF_AUTO_RATE]
            rate = data[CONF_CURRENCY_RATE]

            if currency != "EUR" and not auto_rate and (rate is None or rate <= 0):
                errors[CONF_CURRENCY_RATE] = "invalid_rate"

            if not errors:
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=data
                )
                await self.hass.config_entries.async_reload(
                    self.config_entry.entry_id
                )
                return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="options",
            data_schema=_build_schema(user_input or current),
            errors=errors,
        )
