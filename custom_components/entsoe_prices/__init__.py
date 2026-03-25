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
    CONF_ENERGY_UNIT,
    CONF_VAT,
    CONF_AUTO_RATE,
    DEFAULT_AREA,
    DEFAULT_CURRENCY,
    DEFAULT_ENERGY_UNIT,
    DEFAULT_VAT,

    PLATFORMS,
    UPDATE_INTERVAL_MINUTES,
)
from .coordinator import EntsoeCoordinator

_LOGGER = logging.getLogger(__name__)

# ── Typed ConfigEntry (HA 2024.8+ best practice) ────────────────────────────
# PEP 695 `type` statement requires Python 3.12+; HA 2026.3 uses Python 3.14.
# Using typing_extensions / typing.TypeAlias for broader compatibility.
try:
    from typing import TypeAlias
except ImportError:
    # Python 3.9 fallback — TypeAlias unavailable, use simple assignment
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
        update_interval=timedelta(minutes=UPDATE_INTERVAL_MINUTES),
    )

    await coordinator.async_config_entry_first_refresh()

    # Store coordinator in runtime_data (HA 2024.8+ best practice)
    # Automatically cleaned up on unload — no need for hass.data
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EntsoeConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
