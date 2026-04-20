"""Solar Charge Balancer — switches for boost toggles."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    MODE_BALANCED,
    MODE_BOOST_BATTERY,
    MODE_BOOST_CAR,
)
from .coordinator import SolarChargeCoordinator
from .entity import SolarChargeEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coord: SolarChargeCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities(
        [
            BoostSwitch(coord, entry, "boost_car", MODE_BOOST_CAR),
            BoostSwitch(coord, entry, "boost_battery", MODE_BOOST_BATTERY),
        ]
    )


class BoostSwitch(SolarChargeEntity, SwitchEntity):
    def __init__(
        self,
        coordinator: SolarChargeCoordinator,
        entry: ConfigEntry,
        key: str,
        mode: str,
    ) -> None:
        super().__init__(coordinator, entry, key)
        self._mode = mode
        self.entity_description = SwitchEntityDescription(key=key, translation_key=key)

    @property
    def is_on(self) -> bool:
        return self.coordinator.mode == self._mode

    async def async_turn_on(self, **kwargs) -> None:
        self.coordinator.set_mode(self._mode)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        if self.coordinator.mode == self._mode:
            self.coordinator.set_mode(MODE_BALANCED)
        self.async_write_ha_state()
