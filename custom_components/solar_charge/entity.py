"""Common base entities for Solar Charge Balancer.

Two device "flavours":
- The main hub device (one per config entry)
- A sub-device per charger, linked via ``via_device`` to the main hub.
"""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SolarChargeCoordinator


def main_device_info(entry: ConfigEntry) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer="Solar Charge",
        name=entry.title or "Solar Charge Balancer",
        model="Energy Flow Balancer",
        sw_version="0.2.0",
    )


def charger_device_info(entry: ConfigEntry, charger_id: str, charger_name: str) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_charger_{charger_id}")},
        manufacturer="Solar Charge",
        name=f"{entry.title or 'Solar Charge'} — {charger_name}",
        model="EV Wallbox",
        via_device=(DOMAIN, entry.entry_id),
    )


class SolarChargeEntity(CoordinatorEntity[SolarChargeCoordinator]):
    """Base for entities attached to the main hub device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SolarChargeCoordinator, entry: ConfigEntry, key: str) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._key = key
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = main_device_info(entry)


class ChargerEntity(CoordinatorEntity[SolarChargeCoordinator]):
    """Base for entities attached to a per-charger sub-device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SolarChargeCoordinator,
        entry: ConfigEntry,
        charger_id: str,
        charger_name: str,
        key: str,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._charger_id = charger_id
        self._charger_name = charger_name
        self._key = key
        self._attr_unique_id = f"{entry.entry_id}_charger_{charger_id}_{key}"
        self._attr_device_info = charger_device_info(entry, charger_id, charger_name)
