"""Solar Charge Balancer — Home Assistant custom integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
import voluptuous as vol

from .const import (
    DOMAIN,
    MODES,
    MODE_BOOST_BATTERY,
    MODE_BOOST_CAR,
    MODE_BALANCED,
    PLATFORMS,
    SERVICE_BOOST_BATTERY,
    SERVICE_BOOST_CAR,
    SERVICE_RESET,
    SERVICE_SET_MODE,
)
from .coordinator import SolarChargeCoordinator
from .notify import NotificationDispatcher
from .ev_controller import EvController

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
    """Set up a config entry."""
    coordinator = SolarChargeCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    notifier = NotificationDispatcher(hass, entry, coordinator)
    ev_controller = EvController(hass, entry, coordinator)

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "notifier": notifier,
        "ev_controller": ev_controller,
    }

    # Start background listeners
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
