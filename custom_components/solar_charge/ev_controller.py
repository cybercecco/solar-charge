"""Applies the recommended EV charging power/current to the wallbox.

Listens to coordinator updates and writes on the configured number/switch
entities. All actions are throttled by hysteresis to avoid flapping and
respect min/max charger limits.
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback

from .const import (
    CONF_EV_SET_CURRENT_ENTITY,
    CONF_EV_SET_POWER_ENTITY,
    CONF_EV_SWITCH_ENTITY,
)
from .coordinator import FlowSnapshot, SolarChargeCoordinator

_LOGGER = logging.getLogger(__name__)

_CURRENT_EPSILON = 0.5  # A
_POWER_EPSILON = 100.0  # W


class EvController:
    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator: SolarChargeCoordinator,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.coordinator = coordinator
        self._cfg: dict[str, Any] = {**entry.data, **(entry.options or {})}
        self._unsub = None
        self._last_current: float | None = None
        self._last_power: float | None = None
        self._last_switch: bool | None = None

    @callback
    def async_start(self) -> None:
        self._unsub = self.coordinator.async_add_listener(self._handle_update)

    @callback
    def async_stop(self) -> None:
        if self._unsub is not None:
            self._unsub()
            self._unsub = None

    # ------------------------------------------------------------------
    @callback
    def _handle_update(self) -> None:
        snap: FlowSnapshot | None = self.coordinator.data
        if snap is None:
            return
        self.hass.async_create_task(self._apply(snap))

    async def _apply(self, snap: FlowSnapshot) -> None:
        switch_entity = self._cfg.get(CONF_EV_SWITCH_ENTITY)
        current_entity = self._cfg.get(CONF_EV_SET_CURRENT_ENTITY)
        power_entity = self._cfg.get(CONF_EV_SET_POWER_ENTITY)

        should_charge = snap.recommended_ev_power > 0
        # Toggle switch with hysteresis
        if switch_entity and self._last_switch != should_charge:
            service = "turn_on" if should_charge else "turn_off"
            domain = switch_entity.split(".")[0]
            try:
                await self.hass.services.async_call(
                    domain, service, {"entity_id": switch_entity}, blocking=False
                )
                self._last_switch = should_charge
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("Failed to %s %s: %s", service, switch_entity, err)

        if not should_charge:
            return

        # Prefer current control where available (more granular on most wallboxes)
        if current_entity:
            amps = max(
                self.coordinator.ev_min_current,
                min(self.coordinator.ev_max_current, round(snap.recommended_ev_current)),
            )
            if self._last_current is None or abs(amps - self._last_current) >= _CURRENT_EPSILON:
                await self._set_number(current_entity, amps)
                self._last_current = amps

        if power_entity:
            watts = round(snap.recommended_ev_power)
            if self._last_power is None or abs(watts - self._last_power) >= _POWER_EPSILON:
                await self._set_number(power_entity, watts)
                self._last_power = watts

    async def _set_number(self, entity_id: str, value: float) -> None:
        domain = entity_id.split(".")[0]
        service = "set_value"
        try:
            await self.hass.services.async_call(
                domain, service, {"entity_id": entity_id, "value": value}, blocking=False
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Failed to set %s = %s: %s", entity_id, value, err)
