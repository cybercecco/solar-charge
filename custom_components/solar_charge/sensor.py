"""Solar Charge Balancer — sensor platform (global + per-charger)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    BATTERY_ID,
    BATTERY_NAME,
    CHARGER_ID,
    CHARGER_NAME,
    CONF_BATTERIES,
    CONF_CHARGERS,
    DOMAIN,
)
from .coordinator import (
    BatterySnapshot,
    ChargerSnapshot,
    FlowSnapshot,
    SolarChargeCoordinator,
)
from .entity import BatteryEntity, ChargerEntity, SolarChargeEntity


# ---------------------------------------------------------------------------
# Global sensors
# ---------------------------------------------------------------------------
@dataclass(frozen=True, kw_only=True)
class GlobalSensor(SensorEntityDescription):
    value_fn: Callable[[FlowSnapshot], Any]


GLOBAL_SENSORS: tuple[GlobalSensor, ...] = (
    GlobalSensor(
        key="pv_power",
        translation_key="pv_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda s: s.pv_power,
    ),
    GlobalSensor(
        key="house_power",
        translation_key="house_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda s: s.house_power,
    ),
    GlobalSensor(
        key="grid_power",
        translation_key="grid_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda s: s.grid_power,
    ),
    GlobalSensor(
        key="battery_power",
        translation_key="battery_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda s: s.battery_power,
    ),
    GlobalSensor(
        key="battery_soc",
        translation_key="battery_soc",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda s: s.battery_soc,
    ),
    GlobalSensor(
        key="ev_power_total",
        translation_key="ev_power_total",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda s: s.ev_power_total,
    ),
    GlobalSensor(
        key="surplus",
        translation_key="surplus",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda s: s.surplus,
    ),
    GlobalSensor(
        key="recommended_ev_power_total",
        translation_key="recommended_ev_power_total",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda s: s.recommended_ev_power_total,
    ),
    GlobalSensor(
        key="battery_allocation",
        translation_key="battery_allocation",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda s: s.battery_allocation,
    ),
)


# ---------------------------------------------------------------------------
# Per-charger sensors
# ---------------------------------------------------------------------------
@dataclass(frozen=True, kw_only=True)
class ChargerSensor(SensorEntityDescription):
    value_fn: Callable[[ChargerSnapshot], Any]


CHARGER_SENSORS: tuple[ChargerSensor, ...] = (
    ChargerSensor(
        key="power",
        translation_key="charger_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda c: c.power,
    ),
    ChargerSensor(
        key="recommended_power",
        translation_key="charger_recommended_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda c: c.recommended_power,
    ),
    ChargerSensor(
        key="recommended_current",
        translation_key="charger_recommended_current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value_fn=lambda c: c.recommended_current,
    ),
)


# ---------------------------------------------------------------------------
# Per-battery sensors
# ---------------------------------------------------------------------------
@dataclass(frozen=True, kw_only=True)
class BatterySensor(SensorEntityDescription):
    value_fn: Callable[[BatterySnapshot], Any]


BATTERY_SENSORS: tuple[BatterySensor, ...] = (
    BatterySensor(
        key="power",
        translation_key="battery_unit_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda b: b.power,
    ),
    BatterySensor(
        key="soc",
        translation_key="battery_unit_soc",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda b: b.soc,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coord: SolarChargeCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    entities: list[Any] = [GlobalSensorEntity(coord, entry, d) for d in GLOBAL_SENSORS]
    merged: dict[str, Any] = {**entry.data, **(entry.options or {})}
    for cfg in merged.get(CONF_CHARGERS, []) or []:
        if CHARGER_ID not in cfg:
            continue
        cid = cfg[CHARGER_ID]
        cname = cfg.get(CHARGER_NAME, cid)
        for desc in CHARGER_SENSORS:
            entities.append(ChargerSensorEntity(coord, entry, cid, cname, desc))
    for cfg in merged.get(CONF_BATTERIES, []) or []:
        if BATTERY_ID not in cfg:
            continue
        bid = cfg[BATTERY_ID]
        bname = cfg.get(BATTERY_NAME, bid)
        for desc in BATTERY_SENSORS:
            entities.append(BatterySensorEntity(coord, entry, bid, bname, desc))
    async_add_entities(entities)


class GlobalSensorEntity(SolarChargeEntity, SensorEntity):
    entity_description: GlobalSensor

    def __init__(
        self,
        coordinator: SolarChargeCoordinator,
        entry: ConfigEntry,
        description: GlobalSensor,
    ) -> None:
        super().__init__(coordinator, entry, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        snap = self.coordinator.data
        if snap is None:
            return None
        return self.entity_description.value_fn(snap)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        snap = self.coordinator.data
        if snap is None:
            return None
        return {"mode": snap.mode}


class ChargerSensorEntity(ChargerEntity, SensorEntity):
    entity_description: ChargerSensor

    def __init__(
        self,
        coordinator: SolarChargeCoordinator,
        entry: ConfigEntry,
        charger_id: str,
        charger_name: str,
        description: ChargerSensor,
    ) -> None:
        super().__init__(coordinator, entry, charger_id, charger_name, description.key)
        self.entity_description = description

    def _find(self) -> ChargerSnapshot | None:
        snap = self.coordinator.data
        if snap is None:
            return None
        for c in snap.chargers:
            if c.id == self._charger_id:
                return c
        return None

    @property
    def native_value(self) -> Any:
        ch = self._find()
        if ch is None:
            return None
        return self.entity_description.value_fn(ch)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        ch = self._find()
        if ch is None:
            return None
        return {"priority": ch.priority, "boost": ch.boost}


class BatterySensorEntity(BatteryEntity, SensorEntity):
    entity_description: BatterySensor

    def __init__(
        self,
        coordinator: SolarChargeCoordinator,
        entry: ConfigEntry,
        battery_id: str,
        battery_name: str,
        description: BatterySensor,
    ) -> None:
        super().__init__(coordinator, entry, battery_id, battery_name, description.key)
        self.entity_description = description

    def _find(self) -> BatterySnapshot | None:
        snap = self.coordinator.data
        if snap is None:
            return None
        for b in snap.batteries:
            if b.id == self._battery_id:
                return b
        return None

    @property
    def native_value(self) -> Any:
        b = self._find()
        if b is None:
            return None
        return self.entity_description.value_fn(b)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        b = self._find()
        if b is None:
            return None
        return {"capacity_kwh": b.capacity_kwh}
