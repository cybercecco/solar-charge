"""Solar Charge Balancer — mode and distribution selectors."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DISTRIBUTIONS, DOMAIN, MODES
from .coordinator import SolarChargeCoordinator
from .entity import SolarChargeEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coord: SolarChargeCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([ModeSelect(coord, entry), DistributionSelect(coord, entry)])


class ModeSelect(SolarChargeEntity, SelectEntity):
    _attr_options = list(MODES)

    def __init__(self, coordinator: SolarChargeCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "mode")
        self.entity_description = SelectEntityDescription(key="mode", translation_key="mode")

    @property
    def current_option(self) -> str:
        return self.coordinator.mode

    async def async_select_option(self, option: str) -> None:
        self.coordinator.set_mode(option)
        self.async_write_ha_state()


class DistributionSelect(SolarChargeEntity, SelectEntity):
    _attr_options = list(DISTRIBUTIONS)

    def __init__(self, coordinator: SolarChargeCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "distribution")
        self.entity_description = SelectEntityDescription(
            key="distribution", translation_key="distribution"
        )

    @property
    def current_option(self) -> str:
        return self.coordinator.distribution

    async def async_select_option(self, option: str) -> None:
        self.coordinator.distribution = option
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()
