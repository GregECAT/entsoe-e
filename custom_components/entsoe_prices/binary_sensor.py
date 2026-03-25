"""Binary sensor platform for ENTSO-E Ceny Energii."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import PriceData
from .const import DOMAIN
from .coordinator import EntsoeCoordinator


@dataclass(frozen=True)
class EntsoeBinarySensorDescription:
    """Description for an ENTSO-E binary sensor."""
    key: str
    name_pl: str
    name_en: str
    icon_on: str
    icon_off: str
    device_class: BinarySensorDeviceClass | None = None


BINARY_SENSOR_DESCRIPTIONS: list[EntsoeBinarySensorDescription] = [
    EntsoeBinarySensorDescription(
        key="trend_up_3h",
        name_pl="Trend rosnący 3h",
        name_en="3h Upward Trend",
        icon_on="mdi:trending-up",
        icon_off="mdi:trending-neutral",
    ),
    EntsoeBinarySensorDescription(
        key="trend_down_3h",
        name_pl="Trend malejący 3h",
        name_en="3h Downward Trend",
        icon_on="mdi:trending-down",
        icon_off="mdi:trending-neutral",
    ),
    EntsoeBinarySensorDescription(
        key="in_cheapest_window",
        name_pl="Okno ładowania aktywne",
        name_en="Charging Window Active",
        icon_on="mdi:battery-charging",
        icon_off="mdi:battery-outline",
    ),
    EntsoeBinarySensorDescription(
        key="in_most_expensive_window",
        name_pl="Okno sprzedaży aktywne",
        name_en="Selling Window Active",
        icon_on="mdi:cash-check",
        icon_off="mdi:cash-remove",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ENTSO-E binary sensors from a config entry."""
    coordinator: EntsoeCoordinator = entry.runtime_data

    entities = [
        EntsoeBinarySensor(
            coordinator=coordinator,
            description=desc,
            entry=entry,
        )
        for desc in BINARY_SENSOR_DESCRIPTIONS
    ]

    async_add_entities(entities)


class EntsoeBinarySensor(CoordinatorEntity[EntsoeCoordinator], BinarySensorEntity):
    """Binary sensor for ENTSO-E price data."""

    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator: EntsoeCoordinator,
        description: EntsoeBinarySensorDescription,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._description = description
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_name = f"ENTSO-E {description.name_pl}"
        self._attr_suggested_object_id = f"entsoe_{description.key}"

        if description.device_class is not None:
            self._attr_device_class = description.device_class

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        data = self._get_data()
        if data is None:
            return None
        return getattr(data, self._description.key, None)

    @property
    def icon(self) -> str:
        """Return icon based on state."""
        if self.is_on:
            return self._description.icon_on
        return self._description.icon_off

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
