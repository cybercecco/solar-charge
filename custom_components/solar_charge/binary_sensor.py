"""Solar Charge Balancer — binary sensor platform (global + per-charger)."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CHARGER_ID, CHARGER_NAME, CONF_CHARGERS, DOMAIN
from .coordinator import ChargerSnapshot, FlowSnapshot, SolarChargeCoordinator
from .entity import ChargerEntity, SolarChargeEntity


GLOBAL_BINARY: tuple[tuple[str, str, BinarySensorDeviceClass | None], ...] = (
    ("overconsumption", "overconsumption", BinarySensorDeviceClass.PROBLEM),
    ("exporting", "exporting", BinarySensorDeviceClass.POWER),
    ("any_charging", "any_charging", BinarySensorDeviceClass.POWER),
)


def _global_value(snap: FlowSnapshot, key: str) -> bool:
    if key == "overconsumption":
        return snap.overconsumption
    if key == "exporting":
        return snap.grid_power < 0
    if key == "any_charging":
        return any(c.charging for c in snap.chargers)
    return False


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coord: SolarChargeCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    entities: list[Any] = []
    for key, tkey, dc in GLOBAL_BINARY:
        entities.append(GlobalBinary(coord, entry, key, tkey, dc))

    merged: dict[str, Any] = {**entry.data, **(entry.options or {})}
    for cfg in merged.get(CONF_CHARGERS, []) or []:
        if CHARGER_ID not in cfg:
            continue
        cid = cfg[CHARGER_ID]
        cname = cfg.get(CHARGER_NAME, cid)
        entities.append(ChargerBinary(coord, entry, cid, cname))
    async_add_entities(entities)


class GlobalBinary(SolarChargeEntity, BinarySensorEntity):
    def __init__(
        self,
        coordinator: SolarChargeCoordinator,
        entry: ConfigEntry,
        key: str,
        translation_key: str,
        device_class: BinarySensorDeviceClass | None,
    ) -> None:
        super().__init__(coordinator, entry, key)
        self._sensor_key = key
        self.entity_description = BinarySensorEntityDescription(
            key=key, translation_key=translation_key, device_class=device_class
        )

    @property
    def is_on(self) -> bool | None:
        snap = self.coordinator.data
        if snap is None:
            return None
        return _global_value(snap, self._sensor_key)


class ChargerBinary(ChargerEntity, BinarySensorEntity):
    def __init__(
        self,
        coordinator: SolarChargeCoordinator,
        entry: ConfigEntry,
        charger_id: str,
        charger_name: str,
    ) -> None:
        super().__init__(coordinator, entry, charger_id, charger_name, "charging")
        self.entity_description = BinarySensorEntityDescription(
            key="charging",
            translation_key="charger_charging",
            device_class=BinarySensorDeviceClass.POWER,
        )

    @property
    def is_on(self) -> bool | None:
        snap = self.coordinator.data
        if snap is None:
            return None
        for c in snap.chargers:
            if c.id == self._charger_id:
                return c.charging
        return None
