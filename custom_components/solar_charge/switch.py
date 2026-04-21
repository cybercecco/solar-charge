"""Solar Charge Balancer — switches.

- Global ``boost_battery`` (sets coordinator mode to BOOST_BATTERY)
- Per-charger ``boost`` (elevates that charger's priority to 0 in the
  distribution algorithm and sets mode to BOOST_CAR to prefer EVs over
  battery when available)
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CHARGER_ID,
    CHARGER_NAME,
    CONF_CHARGERS,
    DOMAIN,
    MODE_BALANCED,
    MODE_BOOST_BATTERY,
    MODE_BOOST_CAR,
)
from .coordinator import SolarChargeCoordinator
from .entity import ChargerEntity, SolarChargeEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coord: SolarChargeCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    entities: list[Any] = [BoostBatterySwitch(coord, entry)]
    merged: dict[str, Any] = {**entry.data, **(entry.options or {})}
    for cfg in merged.get(CONF_CHARGERS, []) or []:
        if CHARGER_ID not in cfg:
            continue
        cid = cfg[CHARGER_ID]
        cname = cfg.get(CHARGER_NAME, cid)
        entities.append(ChargerBoostSwitch(coord, entry, cid, cname))
    async_add_entities(entities)


class BoostBatterySwitch(SolarChargeEntity, SwitchEntity):
    def __init__(self, coordinator: SolarChargeCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "boost_battery")
        self.entity_description = SwitchEntityDescription(
            key="boost_battery", translation_key="boost_battery"
        )

    @property
    def is_on(self) -> bool:
        return self.coordinator.mode == MODE_BOOST_BATTERY

    async def async_turn_on(self, **kwargs: Any) -> None:
        self.coordinator.set_mode(MODE_BOOST_BATTERY)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        if self.coordinator.mode == MODE_BOOST_BATTERY:
            self.coordinator.set_mode(MODE_BALANCED)
        self.async_write_ha_state()


class ChargerBoostSwitch(ChargerEntity, SwitchEntity):
    def __init__(
        self,
        coordinator: SolarChargeCoordinator,
        entry: ConfigEntry,
        charger_id: str,
        charger_name: str,
    ) -> None:
        super().__init__(coordinator, entry, charger_id, charger_name, "boost")
        self.entity_description = SwitchEntityDescription(
            key="boost", translation_key="charger_boost"
        )

    @property
    def is_on(self) -> bool:
        return self.coordinator.get_boost(self._charger_id)

    async def async_turn_on(self, **kwargs: Any) -> None:
        self.coordinator.set_boost(self._charger_id, True)
        if self.coordinator.mode not in (MODE_BOOST_CAR,):
            self.coordinator.set_mode(MODE_BOOST_CAR)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self.coordinator.set_boost(self._charger_id, False)
        # If no boost remains, return to balanced
        if not any(
            self.coordinator.get_boost(c.id) for c in (self.coordinator.data.chargers if self.coordinator.data else [])
        ):
            if self.coordinator.mode == MODE_BOOST_CAR:
                self.coordinator.set_mode(MODE_BALANCED)
        self.async_write_ha_state()
