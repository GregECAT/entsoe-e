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
        update_interval: timedelta,
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
        )

    async def _async_update_data(self) -> PriceData:
        """Fetch data from ENTSO-E."""
        try:
            return await self.api_client.async_get_prices()
        except EntsoeApiError as err:
            raise UpdateFailed(f"Błąd aktualizacji danych ENTSO-E: {err}") from err
