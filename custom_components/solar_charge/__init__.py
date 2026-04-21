"""Solar Charge Balancer — Home Assistant custom integration."""
from __future__ import annotations

import logging
import uuid

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
import voluptuous as vol

from .const import (
    BATTERY_CAPACITY_KWH,
    BATTERY_CHARGE_POSITIVE,
    BATTERY_ID,
    BATTERY_NAME,
    BATTERY_POWER_ENTITY,
    BATTERY_SOC_ENTITY,
    CHARGER_ID,
    CHARGER_MAX_CURRENT,
    CHARGER_MIN_CURRENT,
    CHARGER_NAME,
    CHARGER_PHASES,
    CHARGER_POWER_ENTITY,
    CHARGER_PRIORITY,
    CHARGER_SET_CURRENT_ENTITY,
    CHARGER_SET_POWER_ENTITY,
    CHARGER_STATUS_ENTITY,
    CHARGER_SWITCH_ENTITY,
    CHARGER_VOLTAGE,
    CONFIG_VERSION,
    CONF_BATTERIES,
    CONF_CHARGERS,
    DOMAIN,
    MODES,
    MODE_BALANCED,
    MODE_BOOST_BATTERY,
    MODE_BOOST_CAR,
    PLATFORMS,
    SERVICE_BOOST_BATTERY,
    SERVICE_BOOST_CAR,
    SERVICE_RESET,
    SERVICE_SET_MODE,
)
from .coordinator import SolarChargeCoordinator
from .ev_controller import EvController
from .notify import NotificationDispatcher

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

SET_MODE_SCHEMA = vol.Schema(
    {
        vol.Required("mode"): vol.In(MODES),
        vol.Optional("entry_id"): cv.string,
    }
)

BOOST_SCHEMA = vol.Schema(
    {
        vol.Optional("entry_id"): cv.string,
        vol.Optional("duration_minutes"): vol.All(vol.Coerce(int), vol.Range(min=1, max=720)),
    }
)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = SolarChargeCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    notifier = NotificationDispatcher(hass, entry, coordinator)
    ev_controller = EvController(hass, entry, coordinator)

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "notifier": notifier,
        "ev_controller": ev_controller,
    }

    notifier.async_start()
    ev_controller.async_start()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    _async_register_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    bundle = hass.data[DOMAIN].pop(entry.entry_id, None)
    if bundle:
        bundle["notifier"].async_stop()
        bundle["ev_controller"].async_stop()
    return unload_ok


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


# ---------------------------------------------------------------------------
# Migration: 1.x (single wallbox) -> 2.x (chargers list)
# ---------------------------------------------------------------------------
async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    _LOGGER.info(
        "Migrating Solar Charge entry %s from version %s to %s",
        entry.entry_id,
        entry.version,
        CONFIG_VERSION,
    )

    if entry.version >= CONFIG_VERSION:
        return True

    new_data = dict(entry.data)
    new_options = dict(entry.options or {})

    # ------------------------------------------------------------------
    # v1 -> v2: single wallbox keys -> chargers list
    # ------------------------------------------------------------------
    OLD_EV_CHARGER_POWER_ENTITY = "ev_charger_power_entity"
    OLD_EV_CHARGER_STATUS_ENTITY = "ev_charger_status_entity"
    OLD_EV_SET_CURRENT_ENTITY = "ev_set_current_entity"
    OLD_EV_SET_POWER_ENTITY = "ev_set_power_entity"
    OLD_EV_SWITCH_ENTITY = "ev_switch_entity"
    OLD_EV_PHASES = "ev_phases"
    OLD_EV_VOLTAGE = "ev_voltage"
    OLD_EV_MIN_CURRENT = "ev_min_current"
    OLD_EV_MAX_CURRENT = "ev_max_current"

    def _extract_charger(src: dict) -> dict | None:
        if not any(k in src for k in (OLD_EV_CHARGER_POWER_ENTITY, OLD_EV_SET_CURRENT_ENTITY)):
            return None
        return {
            CHARGER_ID: uuid.uuid4().hex,
            CHARGER_NAME: "Wallbox",
            CHARGER_POWER_ENTITY: src.pop(OLD_EV_CHARGER_POWER_ENTITY, None),
            CHARGER_STATUS_ENTITY: src.pop(OLD_EV_CHARGER_STATUS_ENTITY, None),
            CHARGER_SET_CURRENT_ENTITY: src.pop(OLD_EV_SET_CURRENT_ENTITY, None),
            CHARGER_SET_POWER_ENTITY: src.pop(OLD_EV_SET_POWER_ENTITY, None),
            CHARGER_SWITCH_ENTITY: src.pop(OLD_EV_SWITCH_ENTITY, None),
            CHARGER_PHASES: int(src.pop(OLD_EV_PHASES, 1) or 1),
            CHARGER_VOLTAGE: int(src.pop(OLD_EV_VOLTAGE, 230) or 230),
            CHARGER_MIN_CURRENT: int(src.pop(OLD_EV_MIN_CURRENT, 6) or 6),
            CHARGER_MAX_CURRENT: int(src.pop(OLD_EV_MAX_CURRENT, 16) or 16),
            CHARGER_PRIORITY: 10,
        }

    charger_from_data = _extract_charger(new_data)
    charger_from_opts = _extract_charger(new_options)

    existing_chargers = list(new_data.get(CONF_CHARGERS, []) or [])
    if charger_from_opts:
        existing_chargers.append(charger_from_opts)
    elif charger_from_data:
        existing_chargers.append(charger_from_data)
    new_data[CONF_CHARGERS] = existing_chargers

    # ------------------------------------------------------------------
    # v2 -> v3: single battery keys -> batteries list
    # ------------------------------------------------------------------
    OLD_BATTERY_POWER_ENTITY = "battery_power_entity"
    OLD_BATTERY_SOC_ENTITY = "battery_soc_entity"
    OLD_BATTERY_CHARGE_POSITIVE = "battery_charge_positive"
    OLD_BATTERY_CAPACITY_KWH = "battery_capacity_kwh"

    def _extract_battery(src: dict) -> dict | None:
        if not any(k in src for k in (OLD_BATTERY_POWER_ENTITY, OLD_BATTERY_SOC_ENTITY)):
            return None
        return {
            BATTERY_ID: uuid.uuid4().hex,
            BATTERY_NAME: "Batteria",
            BATTERY_POWER_ENTITY: src.pop(OLD_BATTERY_POWER_ENTITY, None),
            BATTERY_SOC_ENTITY: src.pop(OLD_BATTERY_SOC_ENTITY, None),
            BATTERY_CHARGE_POSITIVE: bool(src.pop(OLD_BATTERY_CHARGE_POSITIVE, True)),
            BATTERY_CAPACITY_KWH: float(src.pop(OLD_BATTERY_CAPACITY_KWH, 10.0) or 10.0),
        }

    battery_from_data = _extract_battery(new_data)
    battery_from_opts = _extract_battery(new_options)

    existing_batteries = list(new_data.get(CONF_BATTERIES, []) or [])
    if battery_from_opts:
        existing_batteries.append(battery_from_opts)
    elif battery_from_data:
        existing_batteries.append(battery_from_data)
    new_data[CONF_BATTERIES] = existing_batteries

    hass.config_entries.async_update_entry(
        entry, data=new_data, options=new_options, version=CONFIG_VERSION
    )
    return True


# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------
def _async_register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_SET_MODE):
        return

    def _resolve(call: ServiceCall) -> list[SolarChargeCoordinator]:
        entry_id = call.data.get("entry_id")
        bundles = hass.data.get(DOMAIN, {})
        if entry_id and entry_id in bundles:
            return [bundles[entry_id]["coordinator"]]
        return [b["coordinator"] for b in bundles.values()]

    async def _set_mode(call: ServiceCall) -> None:
        for coord in _resolve(call):
            coord.set_mode(call.data["mode"])

    async def _boost_car(call: ServiceCall) -> None:
        for coord in _resolve(call):
            coord.set_mode(MODE_BOOST_CAR)

    async def _boost_battery(call: ServiceCall) -> None:
        for coord in _resolve(call):
            coord.set_mode(MODE_BOOST_BATTERY)

    async def _reset(call: ServiceCall) -> None:
        for coord in _resolve(call):
            coord.set_mode(MODE_BALANCED)

    hass.services.async_register(DOMAIN, SERVICE_SET_MODE, _set_mode, schema=SET_MODE_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_BOOST_CAR, _boost_car, schema=BOOST_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_BOOST_BATTERY, _boost_battery, schema=BOOST_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_RESET, _reset, schema=BOOST_SCHEMA)
