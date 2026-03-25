"""Data update coordinator for ENTSO-E Ceny Energii."""
from __future__ import annotations

from datetime import timedelta
from typing import Any
import logging

from aiohttp import ClientSession
from homeassistant.core import HomeAssistant
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
            data = self.api_client.compute_spread(
                data,
                rce_price_mwh=rce_price,
                rce_max_today_mwh=rce_max,
            )

        return data

    def _read_rce_price(self) -> float | None:
        """Read current RCE price from HA sensor (PLN/MWh)."""
        state = self.hass.states.get(self._rce_entity)
        if state is None or state.state in ("unavailable", "unknown"):
            return None
        try:
            return float(state.state)
        except (ValueError, TypeError):
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
