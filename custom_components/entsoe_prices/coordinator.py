"""Data update coordinator for ENTSO-E Ceny Energii."""
from __future__ import annotations

from datetime import timedelta
from typing import Any
import logging

from aiohttp import ClientSession
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import EntsoeApiClient, EntsoeApiError, PriceData

_LOGGER = logging.getLogger(__name__)


class EntsoeCoordinator(DataUpdateCoordinator[PriceData]):
    """Coordinator for ENTSO-E price data.

    Fetches day-ahead prices every 30 minutes and provides
    organized data for sensor entities.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        session: ClientSession,
        api_token: str,
        area: str,
        currency: str,
        energy_unit: str,
        vat: float,
        currency_rate: float,
        auto_rate: bool,
        seller_margin: float,
        excise_tax: float,
        distribution_rate: float,
        update_interval: timedelta,
        rce_entity: str = "",
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="ENTSO-E Ceny Energii",
            update_interval=update_interval,
        )
        self.api_client = EntsoeApiClient(
            session=session,
            api_token=api_token,
            area=area,
            currency=currency,
            energy_unit=energy_unit,
            vat=vat,
            currency_rate=currency_rate,
            auto_rate=auto_rate,
            seller_margin=seller_margin,
            excise_tax=excise_tax,
            distribution_rate=distribution_rate,
        )
        self._rce_entity = rce_entity

        # Track RCE sensor changes to recalculate spread in real-time
        if rce_entity:
            _LOGGER.debug("RCE spread enabled, tracking entity: %s", rce_entity)
            async_track_state_change_event(
                hass, [rce_entity], self._on_rce_state_change
            )

    @callback
    def _on_rce_state_change(self, event) -> None:
        """Handle RCE sensor state change — recalculate spread."""
        if self.data is None:
            return
        rce_price = self._read_rce_price()
        rce_max = self._read_rce_max()
        _LOGGER.debug(
            "RCE state changed → recalculating spread (rce=%.4f, max=%s)",
            rce_price if rce_price is not None else 0,
            rce_max,
        )
        self.data = self.api_client.compute_spread(
            self.data,
            rce_price_mwh=rce_price,
            rce_max_today_mwh=rce_max,
        )
        self.async_set_updated_data(self.data)

    async def _async_update_data(self) -> PriceData:
        """Fetch data from ENTSO-E and enrich with RCE spread."""
        try:
            data = await self.api_client.async_get_prices()
        except EntsoeApiError as err:
            raise UpdateFailed(f"Błąd aktualizacji danych ENTSO-E: {err}") from err

        # ── Read RCE data from HA state ──────────────────────────────
        if self._rce_entity:
            rce_price = self._read_rce_price()
            rce_max = self._read_rce_max()
            _LOGGER.debug(
                "RCE spread computation: entity=%s, rce_price=%s, rce_max=%s",
                self._rce_entity, rce_price, rce_max,
            )
            data = self.api_client.compute_spread(
                data,
                rce_price_mwh=rce_price,
                rce_max_today_mwh=rce_max,
            )

        return data

    def _read_rce_price(self) -> float | None:
        """Read current RCE price from HA sensor (PLN/MWh)."""
        state = self.hass.states.get(self._rce_entity)
        if state is None:
            _LOGGER.warning("RCE entity %s not found in HA states", self._rce_entity)
            return None
        if state.state in ("unavailable", "unknown"):
            _LOGGER.debug(
                "RCE entity %s has state '%s', skipping", self._rce_entity, state.state
            )
            return None
        try:
            val = float(state.state)
            _LOGGER.debug("RCE price read: %s = %.4f PLN/MWh", self._rce_entity, val)
            return val
        except (ValueError, TypeError) as exc:
            _LOGGER.warning(
                "Cannot parse RCE price from %s (state='%s'): %s",
                self._rce_entity, state.state, exc,
            )
            return None

    def _read_rce_max(self) -> float | None:
        """Read RCE max today from HA (sensor.rce_max_today)."""
        state = self.hass.states.get("sensor.rce_max_today")
        if state is None or state.state in ("unavailable", "unknown"):
            return None
        try:
            # RCE Max Today stores value in zł/kWh, convert to PLN/MWh
            val = float(state.state)
            return val * 1000.0
        except (ValueError, TypeError):
            return None
