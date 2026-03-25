"""ENTSO-E Ceny Energii — integration for Home Assistant."""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_API_TOKEN,
    CONF_AREA,
    CONF_CURRENCY,
    CONF_CURRENCY_RATE,
    CONF_DISTRIBUTION_RATE,
    CONF_ENERGY_UNIT,
    CONF_EXCISE_TAX,
    CONF_RCE_ENTITY,
    CONF_SELLER_MARGIN,
    CONF_VAT,
    CONF_AUTO_RATE,
    DEFAULT_AREA,
    DEFAULT_CURRENCY,
    DEFAULT_DISTRIBUTION_RATE,
    DEFAULT_ENERGY_UNIT,
    DEFAULT_EXCISE_TAX,
    DEFAULT_RCE_ENTITY,
    DEFAULT_SELLER_MARGIN,
    DEFAULT_VAT,
    PLATFORMS,
    UPDATE_INTERVAL_MINUTES,
)
from .coordinator import EntsoeCoordinator

_LOGGER = logging.getLogger(__name__)

# ── Typed ConfigEntry (HA 2024.8+ best practice) ────────────────────────────
try:
    from typing import TypeAlias
except ImportError:
    EntsoeConfigEntry = ConfigEntry  # type: ignore[assignment]
else:
    EntsoeConfigEntry: TypeAlias = ConfigEntry[EntsoeCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: EntsoeConfigEntry) -> bool:
    """Set up ENTSO-E Ceny Energii from a config entry."""
    session = async_get_clientsession(hass)
    data = dict(entry.data)

    coordinator = EntsoeCoordinator(
        hass=hass,
        session=session,
        api_token=data[CONF_API_TOKEN],
        area=data.get(CONF_AREA, DEFAULT_AREA),
        currency=data.get(CONF_CURRENCY, DEFAULT_CURRENCY),
        energy_unit=data.get(CONF_ENERGY_UNIT, DEFAULT_ENERGY_UNIT),
        vat=data.get(CONF_VAT, DEFAULT_VAT),
        currency_rate=data.get(CONF_CURRENCY_RATE, 1.0),
        auto_rate=data.get(CONF_AUTO_RATE, True),
        seller_margin=data.get(CONF_SELLER_MARGIN, DEFAULT_SELLER_MARGIN),
        excise_tax=data.get(CONF_EXCISE_TAX, DEFAULT_EXCISE_TAX),
        distribution_rate=data.get(CONF_DISTRIBUTION_RATE, DEFAULT_DISTRIBUTION_RATE),
        update_interval=timedelta(minutes=UPDATE_INTERVAL_MINUTES),
        rce_entity=data.get(CONF_RCE_ENTITY, DEFAULT_RCE_ENTITY),
    )

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EntsoeConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
