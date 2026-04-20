"""Config & options flow for Solar Charge Balancer.

The flow is split in logical steps so the user is guided through the
configuration: PV → House/Grid → Battery → EV wallbox → Thresholds → Notifications.
Every field uses Home Assistant selectors so the UI shows entity pickers,
sliders and proper tooltips (via ``translations/*.json``).
"""
from __future__ import annotations

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
    CONF_BATTERY_CAPACITY_KWH,
    CONF_BATTERY_CHARGE_POSITIVE,
    CONF_BATTERY_MAX_CHARGE_W,
    CONF_BATTERY_MIN_SOC,
    CONF_BATTERY_POWER_ENTITY,
    CONF_BATTERY_SOC_ENTITY,
    CONF_BATTERY_TARGET_SOC,
    CONF_DEFAULT_PRIORITY,
    CONF_EV_CHARGER_POWER_ENTITY,
    CONF_EV_CHARGER_STATUS_ENTITY,
    CONF_EV_MAX_CURRENT,
    CONF_EV_MIN_CURRENT,
    CONF_EV_PHASES,
    CONF_EV_SET_CURRENT_ENTITY,
    CONF_EV_SET_POWER_ENTITY,
    CONF_EV_SWITCH_ENTITY,
    CONF_EV_VOLTAGE,
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
    CONF_PV_ENERGY_ENTITIES,
    CONF_PV_POWER_ENTITIES,
    CONF_UPDATE_INTERVAL,
    DEFAULT_BATTERY_MAX_CHARGE_W,
    DEFAULT_BATTERY_MIN_SOC,
    DEFAULT_BATTERY_TARGET_SOC,
    DEFAULT_EV_MAX_CURRENT,
    DEFAULT_EV_MIN_CURRENT,
    DEFAULT_EV_PHASES,
    DEFAULT_EV_VOLTAGE,
    DEFAULT_HYSTERESIS_W,
    DEFAULT_MIN_PV_SURPLUS_W,
    DEFAULT_OVERCONSUMPTION_W,
    DEFAULT_UPDATE_INTERVAL,
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
            domain=["sensor", "input_number"],
            device_class="power",
            multiple=multiple,
        )
    )


def _energy_entity_selector() -> selector.EntitySelector:
    return selector.EntitySelector(
        selector.EntitySelectorConfig(
            domain=["sensor"], device_class="energy", multiple=True
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
    """Build a freeform-but-guided selector for notify services."""
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[],
            multiple=True,
            custom_value=True,
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


# ---------------------------------------------------------------------------
# Schemas (per step)
# ---------------------------------------------------------------------------
def _schema_pv(defaults: dict[str, Any] | None = None) -> vol.Schema:
    d = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_PV_POWER_ENTITIES, default=d.get(CONF_PV_POWER_ENTITIES, [])
            ): _power_entity_selector(multiple=True),
            vol.Optional(
                CONF_PV_ENERGY_ENTITIES, default=d.get(CONF_PV_ENERGY_ENTITIES, [])
            ): _energy_entity_selector(),
        }
    )


def _schema_house(defaults: dict[str, Any] | None = None) -> vol.Schema:
    d = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_HOUSE_POWER_ENTITY, default=d.get(CONF_HOUSE_POWER_ENTITY)
            ): _power_entity_selector(),
            vol.Required(
                CONF_GRID_POWER_ENTITY, default=d.get(CONF_GRID_POWER_ENTITY)
            ): _power_entity_selector(),
            vol.Required(
                CONF_GRID_IS_EXPORT_NEGATIVE,
                default=d.get(CONF_GRID_IS_EXPORT_NEGATIVE, True),
            ): selector.BooleanSelector(),
        }
    )


def _schema_battery(defaults: dict[str, Any] | None = None) -> vol.Schema:
    d = defaults or {}
    return vol.Schema(
        {
            vol.Optional(
                CONF_BATTERY_POWER_ENTITY, default=d.get(CONF_BATTERY_POWER_ENTITY)
            ): _power_entity_selector(),
            vol.Optional(
                CONF_BATTERY_SOC_ENTITY, default=d.get(CONF_BATTERY_SOC_ENTITY)
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


def _schema_ev(defaults: dict[str, Any] | None = None) -> vol.Schema:
    d = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_EV_CHARGER_POWER_ENTITY, default=d.get(CONF_EV_CHARGER_POWER_ENTITY)
            ): _power_entity_selector(),
            vol.Optional(
                CONF_EV_CHARGER_STATUS_ENTITY, default=d.get(CONF_EV_CHARGER_STATUS_ENTITY)
            ): _status_entity_selector(),
            vol.Required(
                CONF_EV_SET_CURRENT_ENTITY, default=d.get(CONF_EV_SET_CURRENT_ENTITY)
            ): _number_entity_selector(),
            vol.Optional(
                CONF_EV_SET_POWER_ENTITY, default=d.get(CONF_EV_SET_POWER_ENTITY)
            ): _number_entity_selector(),
            vol.Optional(
                CONF_EV_SWITCH_ENTITY, default=d.get(CONF_EV_SWITCH_ENTITY)
            ): _switch_entity_selector(),
            vol.Required(
                CONF_EV_PHASES, default=d.get(CONF_EV_PHASES, DEFAULT_EV_PHASES)
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=["1", "3"],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(
                CONF_EV_VOLTAGE, default=d.get(CONF_EV_VOLTAGE, DEFAULT_EV_VOLTAGE)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=110, max=420, step=1, unit_of_measurement="V")
            ),
            vol.Required(
                CONF_EV_MIN_CURRENT, default=d.get(CONF_EV_MIN_CURRENT, DEFAULT_EV_MIN_CURRENT)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=5, max=16, step=1, unit_of_measurement="A")
            ),
            vol.Required(
                CONF_EV_MAX_CURRENT, default=d.get(CONF_EV_MAX_CURRENT, DEFAULT_EV_MAX_CURRENT)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=6, max=63, step=1, unit_of_measurement="A")
            ),
        }
    )


def _schema_thresholds(defaults: dict[str, Any] | None = None) -> vol.Schema:
    d = defaults or {}
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
                selector.NumberSelectorConfig(
                    min=1000, max=30000, step=100, unit_of_measurement="W"
                )
            ),
            vol.Required(
                CONF_UPDATE_INTERVAL, default=d.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=5, max=120, step=1, unit_of_measurement="s")
            ),
        }
    )


def _schema_notifications(defaults: dict[str, Any] | None = None) -> vol.Schema:
    d = defaults or {}
    return vol.Schema(
        {
            vol.Optional(
                CONF_NOTIFY_TARGETS, default=d.get(CONF_NOTIFY_TARGETS, ["persistent_notification"])
            ): _notify_service_selector(),
            vol.Required(
                CONF_NOTIFY_ON_CHARGE_COMPLETE,
                default=d.get(CONF_NOTIFY_ON_CHARGE_COMPLETE, True),
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_NOTIFY_ON_OVERCONSUMPTION,
                default=d.get(CONF_NOTIFY_ON_OVERCONSUMPTION, True),
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_NOTIFY_ON_MODE_CHANGE,
                default=d.get(CONF_NOTIFY_ON_MODE_CHANGE, False),
            ): selector.BooleanSelector(),
        }
    )


# ---------------------------------------------------------------------------
# Config flow
# ---------------------------------------------------------------------------
class SolarChargeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Walk the user through the initial configuration."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_house()
        return self.async_show_form(step_id="user", data_schema=_schema_pv(), last_step=False)

    async def async_step_house(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_battery()
        return self.async_show_form(step_id="house", data_schema=_schema_house(), last_step=False)

    async def async_step_battery(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_ev()
        return self.async_show_form(step_id="battery", data_schema=_schema_battery(), last_step=False)

    async def async_step_ev(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            # SelectSelector returns strings; cast phases back to int
            if CONF_EV_PHASES in user_input:
                user_input[CONF_EV_PHASES] = int(user_input[CONF_EV_PHASES])
            self._data.update(user_input)
            return await self.async_step_thresholds()
        return self.async_show_form(step_id="ev", data_schema=_schema_ev(), last_step=False)

    async def async_step_thresholds(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_notifications()
        return self.async_show_form(
            step_id="thresholds", data_schema=_schema_thresholds(), last_step=False
        )

    async def async_step_notifications(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return self.async_create_entry(title="Solar Charge Balancer", data=self._data)
        return self.async_show_form(
            step_id="notifications", data_schema=_schema_notifications(), last_step=True
        )

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> OptionsFlow:
        return SolarChargeOptionsFlow(entry)


# ---------------------------------------------------------------------------
# Options flow (same steps, pre-filled)
# ---------------------------------------------------------------------------
class SolarChargeOptionsFlow(OptionsFlow):
    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        self._data: dict[str, Any] = {**entry.data, **(entry.options or {})}

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_house()
        return self.async_show_form(
            step_id="init", data_schema=_schema_pv(self._data), last_step=False
        )

    async def async_step_house(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_battery()
        return self.async_show_form(
            step_id="house", data_schema=_schema_house(self._data), last_step=False
        )

    async def async_step_battery(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_ev()
        return self.async_show_form(
            step_id="battery", data_schema=_schema_battery(self._data), last_step=False
        )

    async def async_step_ev(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            if CONF_EV_PHASES in user_input:
                user_input[CONF_EV_PHASES] = int(user_input[CONF_EV_PHASES])
            self._data.update(user_input)
            return await self.async_step_thresholds()
        return self.async_show_form(
            step_id="ev", data_schema=_schema_ev(self._data), last_step=False
        )

    async def async_step_thresholds(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_notifications()
        return self.async_show_form(
            step_id="thresholds", data_schema=_schema_thresholds(self._data), last_step=False
        )

    async def async_step_notifications(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return self.async_create_entry(title="", data=self._data)
        return self.async_show_form(
            step_id="notifications",
            data_schema=_schema_notifications(self._data),
            last_step=True,
        )
