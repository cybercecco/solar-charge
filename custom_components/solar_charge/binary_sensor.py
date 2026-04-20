"""Solar Charge Balancer — binary sensor platform."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import FlowSnapshot, SolarChargeCoordinator
from .entity import SolarChargeEntity


@dataclass(frozen=True, kw_only=True)
class SolarChargeBinaryDescription(BinarySensorEntityDescription):
    value_fn: Callable[[FlowSnapshot], bool]


SENSORS: tuple[SolarChargeBinaryDescription, ...] = (
    SolarChargeBinaryDescription(
        key="overconsumption",
        translation_key="overconsumption",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda s: s.overconsumption,
    ),
    SolarChargeBinaryDescription(
        key="ev_charging",
        translation_key="ev_charging",
        device_class=BinarySensorDeviceClass.POWER,
        value_fn=lambda s: s.ev_power > 200,
    ),
    SolarChargeBinaryDescription(
        key="exporting",
        translation_key="exporting",
        device_class=BinarySensorDeviceClass.POWER,
        value_fn=lambda s: s.grid_power < 0,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coord: SolarChargeCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities(SolarChargeBinarySensor(coord, entry, d) for d in SENSORS)


class SolarChargeBinarySensor(SolarChargeEntity, BinarySensorEntity):
    entity_description: SolarChargeBinaryDescription

    def __init__(
        self,
        coordinator: SolarChargeCoordinator,
        entry: ConfigEntry,
        description: SolarChargeBinaryDescription,
    ) -> None:
        super().__init__(coordinator, entry, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        snap = self.coordinator.data
        if snap is None:
            return None
        return self.entity_description.value_fn(snap)
