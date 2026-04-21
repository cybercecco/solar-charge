"""Config & options flow for Solar Charge Balancer.

Design goals:
- Installation must be LINEAR: the user just confirms a name and gets the
  integration created immediately (no mandatory data required yet).
- All real configuration (PV, battery, chargers, thresholds, notifications)
  lives in the OPTIONS flow and is accessed through a menu. Each section is
  a separate step so the user can modify just what they need.
- Chargers are a LIST (multiple wallboxes): the options flow exposes a
  dedicated sub-menu with add/edit/remove operations.
- Multiple PV sources are supported through a multi-entity selector.

The resulting config entry follows this shape:

    {
        "title": "Solar Charge",
        "pv_power_entities": [...],
        "house_power_entity": "...",
        "grid_power_entity": "...",
        "grid_export_negative": true,
        "battery_power_entity": "...",
        "battery_soc_entity": "...",
        ...,
        "chargers": [
            {"id": "<uuid>", "name": "Wallbox salotto", ...},
            {"id": "<uuid>", "name": "Wallbox garage",  ...},
        ],
        "default_priority": "balanced",
        "charger_distribution": "priority",
        "overconsumption_threshold_w": 6000,
        "notify_targets": [...],
        ...
    }
"""
from __future__ import annotations

import uuid
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
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
    CONF_BATTERY_CAPACITY_KWH,
    CONF_BATTERY_CHARGE_POSITIVE,
    CONF_BATTERY_MAX_CHARGE_W,
    CONF_BATTERY_MIN_SOC,
    CONF_BATTERY_POWER_ENTITY,
    CONF_BATTERY_SOC_ENTITY,
    CONF_BATTERY_TARGET_SOC,
    CONF_CHARGER_DISTRIBUTION,
    CONF_CHARGERS,
    CONF_DEFAULT_PRIORITY,
    CONF_GRID_IS_EXPORT_NEGATIVE,
    CONF_GRID_POWER_ENTITY,
    CONF_HOUSE_POWER_ENTITY,
    CONF_HYSTERESIS_W,
    CONF_MIN_PV_SURPLUS_W,
    CONF_NOTIFY_ON_CHARGE_COMPLETE,
    CONF_NOTIFY_ON_MODE_CHANGE,
    CONF_NOTIFY_ON_OVERCONSUMPTION,
    CONF_NOTIFY_TARGETS,
    CONF_OVERCONSUMPTION_THRESHOLD_W,
    CONF_PV_POWER_ENTITIES,
    CONF_TITLE,
    CONF_UPDATE_INTERVAL,
    DEFAULT_BATTERY_MAX_CHARGE_W,
    DEFAULT_BATTERY_MIN_SOC,
    DEFAULT_BATTERY_TARGET_SOC,
    DEFAULT_CHARGER_DISTRIBUTION,
    DEFAULT_EV_MAX_CURRENT,
    DEFAULT_EV_MIN_CURRENT,
    DEFAULT_EV_PHASES,
    DEFAULT_EV_VOLTAGE,
    DEFAULT_HYSTERESIS_W,
    DEFAULT_MIN_PV_SURPLUS_W,
    DEFAULT_OVERCONSUMPTION_W,
    DEFAULT_UPDATE_INTERVAL,
    DISTRIBUTIONS,
    DOMAIN,
    MODES,
    MODE_BALANCED,
)


# ---------------------------------------------------------------------------
# Selector helpers
# ---------------------------------------------------------------------------
def _power_entity_selector(multiple: bool = False) -> selector.EntitySelector:
    return selector.EntitySelector(
        selector.EntitySelectorConfig(
            domain=["sensor", "input_number"], device_class="power", multiple=multiple
        )
    )


def _soc_entity_selector() -> selector.EntitySelector:
    return selector.EntitySelector(
        selector.EntitySelectorConfig(domain=["sensor", "input_number"], device_class="battery")
    )


def _number_entity_selector() -> selector.EntitySelector:
    return selector.EntitySelector(
        selector.EntitySelectorConfig(domain=["number", "input_number"])
    )


def _switch_entity_selector() -> selector.EntitySelector:
    return selector.EntitySelector(
        selector.EntitySelectorConfig(domain=["switch", "input_boolean"])
    )


def _status_entity_selector() -> selector.EntitySelector:
    return selector.EntitySelector(
        selector.EntitySelectorConfig(domain=["sensor", "binary_sensor"])
    )


def _notify_service_selector() -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[], multiple=True, custom_value=True,
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
def _schema_pv(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Optional(
                CONF_PV_POWER_ENTITIES, default=defaults.get(CONF_PV_POWER_ENTITIES, [])
            ): _power_entity_selector(multiple=True),
        }
    )


def _schema_house(defaults: dict[str, Any]) -> vol.Schema:
    d = defaults
    return vol.Schema(
        {
            vol.Optional(
                CONF_HOUSE_POWER_ENTITY, default=d.get(CONF_HOUSE_POWER_ENTITY) or vol.UNDEFINED
            ): _power_entity_selector(),
            vol.Optional(
                CONF_GRID_POWER_ENTITY, default=d.get(CONF_GRID_POWER_ENTITY) or vol.UNDEFINED
            ): _power_entity_selector(),
            vol.Required(
                CONF_GRID_IS_EXPORT_NEGATIVE,
                default=d.get(CONF_GRID_IS_EXPORT_NEGATIVE, True),
            ): selector.BooleanSelector(),
        }
    )


def _schema_battery(defaults: dict[str, Any]) -> vol.Schema:
    d = defaults
    return vol.Schema(
        {
            vol.Optional(
                CONF_BATTERY_POWER_ENTITY, default=d.get(CONF_BATTERY_POWER_ENTITY) or vol.UNDEFINED
            ): _power_entity_selector(),
            vol.Optional(
                CONF_BATTERY_SOC_ENTITY, default=d.get(CONF_BATTERY_SOC_ENTITY) or vol.UNDEFINED
            ): _soc_entity_selector(),
            vol.Required(
                CONF_BATTERY_CHARGE_POSITIVE,
                default=d.get(CONF_BATTERY_CHARGE_POSITIVE, True),
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_BATTERY_CAPACITY_KWH, default=d.get(CONF_BATTERY_CAPACITY_KWH, 10.0)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=200, step=0.1, unit_of_measurement="kWh")
            ),
            vol.Required(
                CONF_BATTERY_MIN_SOC, default=d.get(CONF_BATTERY_MIN_SOC, DEFAULT_BATTERY_MIN_SOC)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=100, step=1, unit_of_measurement="%")
            ),
            vol.Required(
                CONF_BATTERY_TARGET_SOC,
                default=d.get(CONF_BATTERY_TARGET_SOC, DEFAULT_BATTERY_TARGET_SOC),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=100, step=1, unit_of_measurement="%")
            ),
            vol.Required(
                CONF_BATTERY_MAX_CHARGE_W,
                default=d.get(CONF_BATTERY_MAX_CHARGE_W, DEFAULT_BATTERY_MAX_CHARGE_W),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=500, max=20000, step=100, unit_of_measurement="W")
            ),
        }
    )


def _schema_charger(defaults: dict[str, Any] | None = None) -> vol.Schema:
    d = defaults or {}
    return vol.Schema(
        {
            vol.Required(CHARGER_NAME, default=d.get(CHARGER_NAME, "Wallbox")): selector.TextSelector(),
            vol.Optional(
                CHARGER_POWER_ENTITY, default=d.get(CHARGER_POWER_ENTITY) or vol.UNDEFINED
            ): _power_entity_selector(),
            vol.Optional(
                CHARGER_STATUS_ENTITY, default=d.get(CHARGER_STATUS_ENTITY) or vol.UNDEFINED
            ): _status_entity_selector(),
            vol.Optional(
                CHARGER_SET_CURRENT_ENTITY,
                default=d.get(CHARGER_SET_CURRENT_ENTITY) or vol.UNDEFINED,
            ): _number_entity_selector(),
            vol.Optional(
                CHARGER_SET_POWER_ENTITY,
                default=d.get(CHARGER_SET_POWER_ENTITY) or vol.UNDEFINED,
            ): _number_entity_selector(),
            vol.Optional(
                CHARGER_SWITCH_ENTITY, default=d.get(CHARGER_SWITCH_ENTITY) or vol.UNDEFINED
            ): _switch_entity_selector(),
            vol.Required(CHARGER_PHASES, default=str(d.get(CHARGER_PHASES, DEFAULT_EV_PHASES))): selector.SelectSelector(
                selector.SelectSelectorConfig(options=["1", "3"], mode=selector.SelectSelectorMode.DROPDOWN)
            ),
            vol.Required(
                CHARGER_VOLTAGE, default=d.get(CHARGER_VOLTAGE, DEFAULT_EV_VOLTAGE)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=110, max=420, step=1, unit_of_measurement="V")
            ),
            vol.Required(
                CHARGER_MIN_CURRENT, default=d.get(CHARGER_MIN_CURRENT, DEFAULT_EV_MIN_CURRENT)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=5, max=16, step=1, unit_of_measurement="A")
            ),
            vol.Required(
                CHARGER_MAX_CURRENT, default=d.get(CHARGER_MAX_CURRENT, DEFAULT_EV_MAX_CURRENT)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=6, max=63, step=1, unit_of_measurement="A")
            ),
            vol.Required(CHARGER_PRIORITY, default=d.get(CHARGER_PRIORITY, 10)): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=99, step=1)
            ),
        }
    )


def _schema_thresholds(defaults: dict[str, Any]) -> vol.Schema:
    d = defaults
    return vol.Schema(
        {
            vol.Required(
                CONF_DEFAULT_PRIORITY, default=d.get(CONF_DEFAULT_PRIORITY, MODE_BALANCED)
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=MODES, mode=selector.SelectSelectorMode.DROPDOWN, translation_key="mode"
                )
            ),
            vol.Required(
                CONF_CHARGER_DISTRIBUTION,
                default=d.get(CONF_CHARGER_DISTRIBUTION, DEFAULT_CHARGER_DISTRIBUTION),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=DISTRIBUTIONS, mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="distribution",
                )
            ),
            vol.Required(
                CONF_MIN_PV_SURPLUS_W, default=d.get(CONF_MIN_PV_SURPLUS_W, DEFAULT_MIN_PV_SURPLUS_W)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=5000, step=50, unit_of_measurement="W")
            ),
            vol.Required(
                CONF_HYSTERESIS_W, default=d.get(CONF_HYSTERESIS_W, DEFAULT_HYSTERESIS_W)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=2000, step=25, unit_of_measurement="W")
            ),
            vol.Required(
                CONF_OVERCONSUMPTION_THRESHOLD_W,
                default=d.get(CONF_OVERCONSUMPTION_THRESHOLD_W, DEFAULT_OVERCONSUMPTION_W),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1000, max=30000, step=100, unit_of_measurement="W")
            ),
            vol.Required(
                CONF_UPDATE_INTERVAL, default=d.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=5, max=120, step=1, unit_of_measurement="s")
            ),
        }
    )


def _schema_notifications(defaults: dict[str, Any]) -> vol.Schema:
    d = defaults
    return vol.Schema(
        {
            vol.Optional(
                CONF_NOTIFY_TARGETS, default=d.get(CONF_NOTIFY_TARGETS, ["persistent_notification"])
            ): _notify_service_selector(),
            vol.Required(
                CONF_NOTIFY_ON_CHARGE_COMPLETE, default=d.get(CONF_NOTIFY_ON_CHARGE_COMPLETE, True)
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_NOTIFY_ON_OVERCONSUMPTION, default=d.get(CONF_NOTIFY_ON_OVERCONSUMPTION, True)
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_NOTIFY_ON_MODE_CHANGE, default=d.get(CONF_NOTIFY_ON_MODE_CHANGE, False)
            ): selector.BooleanSelector(),
        }
    )


# ---------------------------------------------------------------------------
# CONFIG FLOW — trivial single-step (just a name)
# ---------------------------------------------------------------------------
class SolarChargeConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = CONFIG_VERSION
    MINOR_VERSION = 0

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Single setup step: create the entry with just a friendly name."""
        if user_input is not None:
            title = user_input.get(CONF_TITLE, "Solar Charge Balancer").strip() or "Solar Charge Balancer"
            return self.async_create_entry(
                title=title,
                data={CONF_TITLE: title, CONF_CHARGERS: []},
            )

        schema = vol.Schema(
            {vol.Required(CONF_TITLE, default="Solar Charge Balancer"): selector.TextSelector()}
        )
        return self.async_show_form(step_id="user", data_schema=schema, last_step=True)

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> OptionsFlow:
        return SolarChargeOptionsFlow(entry)


# ---------------------------------------------------------------------------
# OPTIONS FLOW — menu with dedicated steps
# ---------------------------------------------------------------------------
class SolarChargeOptionsFlow(OptionsFlow):
    """All data is modified here. Entry-level data is kept minimal."""

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        self._data: dict[str, Any] = {**entry.data, **(entry.options or {})}
        self._data.setdefault(CONF_CHARGERS, [])
        # Staging state for the charger sub-flow
        self._charger_edit_idx: int | None = None

    # ------------------------------------------------------------------
    # Main menu
    # ------------------------------------------------------------------
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "pv",
                "house",
                "battery",
                "chargers",
                "thresholds",
                "notifications",
                "save",
            ],
        )

    async def async_step_save(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Persist everything and close the flow."""
        return self.async_create_entry(title="", data=self._data)

    # ------------------------------------------------------------------
    # PV / House / Battery / Thresholds / Notifications
    # ------------------------------------------------------------------
    async def async_step_pv(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_init()
        return self.async_show_form(step_id="pv", data_schema=_schema_pv(self._data))

    async def async_step_house(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_init()
        return self.async_show_form(step_id="house", data_schema=_schema_house(self._data))

    async def async_step_battery(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_init()
        return self.async_show_form(step_id="battery", data_schema=_schema_battery(self._data))

    async def async_step_thresholds(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_init()
        return self.async_show_form(step_id="thresholds", data_schema=_schema_thresholds(self._data))

    async def async_step_notifications(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_init()
        return self.async_show_form(step_id="notifications", data_schema=_schema_notifications(self._data))

    # ------------------------------------------------------------------
    # Chargers sub-flow
    # ------------------------------------------------------------------
    async def async_step_chargers(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Pick one action on the charger list."""
        chargers = self._data.get(CONF_CHARGERS, []) or []

        if user_input is not None:
            action = user_input["action"]
            if action == "add":
                self._charger_edit_idx = None
                return await self.async_step_charger_form()
            if action == "back":
                return await self.async_step_init()
            if action.startswith("edit_"):
                self._charger_edit_idx = int(action.split("_", 1)[1])
                return await self.async_step_charger_form()
            if action.startswith("remove_"):
                idx = int(action.split("_", 1)[1])
                if 0 <= idx < len(chargers):
                    chargers = list(chargers)
                    chargers.pop(idx)
                    self._data[CONF_CHARGERS] = chargers
                return await self.async_step_chargers()

        options: list[dict[str, str]] = [{"value": "add", "label": "+  Aggiungi colonnina"}]
        for i, c in enumerate(chargers):
            name = c.get(CHARGER_NAME) or f"Colonnina {i + 1}"
            options.append({"value": f"edit_{i}", "label": f"{chr(0x270F)}  Modifica: {name}"})
            options.append({"value": f"remove_{i}", "label": f"{chr(0x2716)}  Elimina: {name}"})
        options.append({"value": "back", "label": f"{chr(0x2190)}  Indietro"})

        schema = vol.Schema(
            {
                vol.Required("action"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options, mode=selector.SelectSelectorMode.LIST
                    )
                )
            }
        )
        return self.async_show_form(step_id="chargers", data_schema=schema)

    async def async_step_charger_form(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Add or edit a single charger."""
        chargers = list(self._data.get(CONF_CHARGERS, []) or [])
        defaults: dict[str, Any] = {}
        if self._charger_edit_idx is not None and 0 <= self._charger_edit_idx < len(chargers):
            defaults = dict(chargers[self._charger_edit_idx])

        if user_input is not None:
            user_input[CHARGER_PHASES] = int(user_input[CHARGER_PHASES])
            if self._charger_edit_idx is None:
                user_input[CHARGER_ID] = uuid.uuid4().hex
                chargers.append(user_input)
            else:
                user_input[CHARGER_ID] = defaults.get(CHARGER_ID) or uuid.uuid4().hex
                chargers[self._charger_edit_idx] = user_input
            self._data[CONF_CHARGERS] = chargers
            self._charger_edit_idx = None
            return await self.async_step_chargers()

        return self.async_show_form(
            step_id="charger_form", data_schema=_schema_charger(defaults)
        )
