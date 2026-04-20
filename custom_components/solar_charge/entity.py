"""Common base entity for Solar Charge Balancer."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SolarChargeCoordinator


class SolarChargeEntity(CoordinatorEntity[SolarChargeCoordinator]):
    """Base entity bound to the coordinator + a device per config entry."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SolarChargeCoordinator, entry: ConfigEntry, key: str) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._key = key
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Solar Charge",
            name=entry.title or "Solar Charge Balancer",
            model="Energy Flow Balancer",
            sw_version="0.1.0",
        )
