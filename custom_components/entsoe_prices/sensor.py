"""Sensor platform for ENTSO-E Ceny Energii."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import PriceData
from .const import (
    ATTR_DATA_AVAILABLE,
    ATTR_EXCHANGE_RATE,
    ATTR_PRICES_TODAY,
    ATTR_PRICES_TOMORROW,
    ATTR_UPDATED_AT,
    DOMAIN,
)
from .coordinator import EntsoeCoordinator


@dataclass(frozen=True)
class EntsoeSensorDescription:
    """Description for an ENTSO-E sensor."""
    key: str
    name_pl: str
    name_en: str
    icon: str
    state_class: SensorStateClass | None = SensorStateClass.MEASUREMENT
    device_class: SensorDeviceClass | None = None
    extra_attrs: bool = False
    unit_override: str | None = None


SENSOR_DESCRIPTIONS: list[EntsoeSensorDescription] = [
    EntsoeSensorDescription(
        key="current_price",
        name_pl="Aktualna cena energii",
        name_en="Current Energy Price",
        icon="mdi:flash",
        extra_attrs=True,
    ),
    EntsoeSensorDescription(
        key="next_hour_price",
        name_pl="Cena za następną godzinę",
        name_en="Next Hour Price",
        icon="mdi:flash-outline",
    ),
    EntsoeSensorDescription(
        key="today_min",
        name_pl="Minimum dzisiaj",
        name_en="Today Minimum",
        icon="mdi:arrow-down-bold",
    ),
    EntsoeSensorDescription(
        key="today_max",
        name_pl="Maksimum dzisiaj",
        name_en="Today Maximum",
        icon="mdi:arrow-up-bold",
    ),
    EntsoeSensorDescription(
        key="today_avg",
        name_pl="Średnia dzisiaj",
        name_en="Today Average",
        icon="mdi:chart-line",
    ),
    EntsoeSensorDescription(
        key="cheapest_hours_avg",
        name_pl="Najtańsze 3h — średnia",
        name_en="Cheapest 3h Average",
        icon="mdi:sale",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ENTSO-E sensors from a config entry."""
    # Use runtime_data (HA 2024.8+) instead of hass.data[DOMAIN]
    coordinator: EntsoeCoordinator = entry.runtime_data

    entities = [
        EntsoePriceSensor(
            coordinator=coordinator,
            description=desc,
            entry=entry,
        )
        for desc in SENSOR_DESCRIPTIONS
    ]

    async_add_entities(entities)


class EntsoePriceSensor(CoordinatorEntity[EntsoeCoordinator], SensorEntity):
    """Sensor for ENTSO-E electricity price data."""

    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator: EntsoeCoordinator,
        description: EntsoeSensorDescription,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._description = description
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_name = f"ENTSO-E {description.name_pl}"
        self._attr_icon = description.icon
        self._attr_suggested_object_id = f"entsoe_{description.key}"

        if description.state_class is not None:
            self._attr_state_class = description.state_class
        if description.device_class is not None:
            self._attr_device_class = description.device_class

    @property
    def native_value(self) -> float | None:
        """Return the current sensor value."""
        data = self._get_data()
        if data is None:
            return None
        return getattr(data, self._description.key, None)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement."""
        data = self._get_data()
        if data is None:
            return None
        if self._description.unit_override:
            return self._description.unit_override
        return data.unit

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        data = self._get_data()
        if data is None:
            return {}

        attrs: dict[str, Any] = {
            ATTR_UPDATED_AT: data.updated_at,
            ATTR_EXCHANGE_RATE: data.exchange_rate,
        }

        if self._description.extra_attrs:
            attrs[ATTR_PRICES_TODAY] = data.prices_today
            attrs[ATTR_PRICES_TOMORROW] = data.prices_tomorrow
            attrs[ATTR_DATA_AVAILABLE] = data.tomorrow_available

            # Additional info
            attrs["today_min"] = data.today_min
            attrs["today_max"] = data.today_max
            attrs["today_avg"] = data.today_avg
            attrs["today_min_hour"] = data.today_min_hour
            attrs["today_max_hour"] = data.today_max_hour
            attrs["cheapest_hours_start"] = data.cheapest_hours_start
            attrs["cheapest_hours_end"] = data.cheapest_hours_end
            attrs["cheapest_hours_avg"] = data.cheapest_hours_avg

        return attrs

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name="ENTSO-E Ceny Energii",
            manufacturer="Smarting HOME",
            model="ENTSO-E Transparency Platform",
            configuration_url="https://smartinghome.pl",
            entry_type=None,
        )

    @property
    def should_poll(self) -> bool:
        """No direct polling — coordinator handles updates."""
        return False

    def _get_data(self) -> PriceData | None:
        """Get coordinator data safely."""
        return self.coordinator.data if self.coordinator.data else None
