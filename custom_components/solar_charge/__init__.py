"""Solar Charge Balancer — Home Assistant custom integration."""
from __future__ import annotations

import logging
import uuid
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
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

# Where the bundled Lovelace card is served from. We keep it versioned via a
# querystring so browsers reload it after an integration update.
FRONTEND_URL_BASE = "/solar_charge_static"
FRONTEND_SCRIPT = "solar-charge-card.js"
FRONTEND_CARD_VERSION = "0.12.2"


def _frontend_card_url() -> str:
    return f"{FRONTEND_URL_BASE}/{FRONTEND_SCRIPT}?v={FRONTEND_CARD_VERSION}"


async def _async_register_lovelace_resource(hass: HomeAssistant, url: str) -> bool:
    """Register the card as a persistent Lovelace resource (storage mode).

    This is what makes the card appear in the *Add card* picker: Lovelace
    enumerates resources at dashboard load and calls the scripts; only
    after one of them registers a custom element does the custom card
    become selectable.

    Returns True if we successfully registered or found an existing entry.
    """
    try:
        lovelace_data = hass.data.get("lovelace")
        if lovelace_data is None:
            return False

        resources = getattr(lovelace_data, "resources", None)
        if resources is None and isinstance(lovelace_data, dict):
            resources = lovelace_data.get("resources")
        if resources is None:
            _LOGGER.debug("Lovelace resources collection not available")
            return False

        # YAML mode: resources are read-only (mode attribute is 'yaml').
        mode = getattr(lovelace_data, "mode", None)
        if mode == "yaml":
            _LOGGER.debug(
                "Lovelace is in YAML mode; skipping resource registration. "
                "Add `%s` to your resources: block manually or rely on extra_js_url.",
                url,
            )
            return False

        if hasattr(resources, "async_load") and not getattr(resources, "loaded", True):
            await resources.async_load()

        items_iter = (
            resources.async_items()
            if hasattr(resources, "async_items")
            else list(getattr(resources, "data", {}).values())
        )
        base_url = url.split("?", 1)[0]
        for item in items_iter:
            existing = item.get("url", "")
            if existing.split("?", 1)[0] == base_url:
                if existing != url:
                    # URL changed (version bump) → update so browsers refetch.
                    try:
                        await resources.async_update_item(
                            item["id"], {"url": url, "res_type": "module"}
                        )
                        _LOGGER.info(
                            "Solar Charge Lovelace resource URL updated to %s", url
                        )
                    except Exception as err:  # pragma: no cover
                        _LOGGER.debug("Could not update Lovelace resource: %s", err)
                return True

        await resources.async_create_item({"url": url, "res_type": "module"})
        _LOGGER.info("Solar Charge Lovelace resource registered: %s", url)
        return True
    except Exception as err:  # pragma: no cover - defensive
        _LOGGER.warning("Could not register Lovelace resource automatically: %s", err)
        return False


async def _async_register_frontend(hass: HomeAssistant) -> None:
    """Serve the bundled Lovelace card and register it in the dashboard.

    Registration happens on three layers for maximum compatibility:
      1. static path   -> the JS file is served under /solar_charge_static/.
      2. extra JS URL  -> included in every frontend page (YAML-mode fallback).
      3. Lovelace resource -> persistent entry shown in the *Add card* picker.
    """
    if hass.data.get(DOMAIN, {}).get("_frontend_registered"):
        return

    frontend_dir = str(Path(__file__).parent / "frontend")

    # 1) Static path (HA 2024.7+ prefers async_register_static_paths)
    try:
        from homeassistant.components.http import StaticPathConfig  # type: ignore

        await hass.http.async_register_static_paths(
            [StaticPathConfig(FRONTEND_URL_BASE, frontend_dir, cache_headers=False)]
        )
    except ImportError:
        await hass.async_add_executor_job(
            hass.http.register_static_path,
            FRONTEND_URL_BASE,
            frontend_dir,
            False,  # cache_headers
        )

    url = _frontend_card_url()

    # 2) Extra JS URL (YAML mode + defensive belt-and-braces for storage mode)
    add_extra_js_url(hass, url)

    # 3) Persistent Lovelace resource (storage mode): this is what makes the
    #    card appear in the picker on dashboards that use the UI editor.
    await _async_register_lovelace_resource(hass, url)

    hass.data.setdefault(DOMAIN, {})["_frontend_registered"] = True
    _LOGGER.info(
        "Solar Charge Lovelace card served at %s (v%s)", url, FRONTEND_CARD_VERSION
    )

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
    await _async_register_frontend(hass)

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
