"""Solar Charge Balancer — number platform (runtime-tunable global thresholds)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import SolarChargeCoordinator
from .entity import SolarChargeEntity


@dataclass(frozen=True, kw_only=True)
class NumDesc(NumberEntityDescription):
    getter: Callable[[SolarChargeCoordinator], float]
    setter: Callable[[SolarChargeCoordinator, float], None]


NUMBERS: tuple[NumDesc, ...] = (
    NumDesc(
        key="battery_min_soc",
        translation_key="battery_min_soc",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.SLIDER,
        getter=lambda c: c.battery_min_soc,
        setter=lambda c, v: setattr(c, "battery_min_soc", int(v)),
    ),
    NumDesc(
        key="battery_target_soc",
        translation_key="battery_target_soc",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.SLIDER,
        getter=lambda c: c.battery_target_soc,
        setter=lambda c, v: setattr(c, "battery_target_soc", int(v)),
    ),
    NumDesc(
        key="battery_max_charge_w",
        translation_key="battery_max_charge_w",
        native_min_value=500,
        native_max_value=20000,
        native_step=100,
        native_unit_of_measurement=UnitOfPower.WATT,
        mode=NumberMode.BOX,
        getter=lambda c: c.battery_max_charge_w,
        setter=lambda c, v: setattr(c, "battery_max_charge_w", int(v)),
    ),
    NumDesc(
        key="min_pv_surplus",
        translation_key="min_pv_surplus",
        native_min_value=0,
        native_max_value=5000,
        native_step=50,
        native_unit_of_measurement=UnitOfPower.WATT,
        mode=NumberMode.BOX,
        getter=lambda c: c.min_pv_surplus,
        setter=lambda c, v: setattr(c, "min_pv_surplus", int(v)),
    ),
    NumDesc(
        key="hysteresis",
        translation_key="hysteresis",
        native_min_value=0,
        native_max_value=2000,
        native_step=25,
        native_unit_of_measurement=UnitOfPower.WATT,
        mode=NumberMode.BOX,
        getter=lambda c: c.hysteresis,
        setter=lambda c, v: setattr(c, "hysteresis", int(v)),
    ),
    NumDesc(
        key="overconsumption_w",
        translation_key="overconsumption_w",
        native_min_value=1000,
        native_max_value=30000,
        native_step=100,
        native_unit_of_measurement=UnitOfPower.WATT,
        mode=NumberMode.BOX,
        getter=lambda c: c.overconsumption_w,
        setter=lambda c, v: setattr(c, "overconsumption_w", int(v)),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coord: SolarChargeCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities(SolarChargeNumber(coord, entry, d) for d in NUMBERS)


class SolarChargeNumber(SolarChargeEntity, NumberEntity):
    entity_description: NumDesc

    def __init__(
        self,
        coordinator: SolarChargeCoordinator,
        entry: ConfigEntry,
        description: NumDesc,
    ) -> None:
        super().__init__(coordinator, entry, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float:
        return float(self.entity_description.getter(self.coordinator))

    async def async_set_native_value(self, value: float) -> None:
        self.entity_description.setter(self.coordinator, value)
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()
