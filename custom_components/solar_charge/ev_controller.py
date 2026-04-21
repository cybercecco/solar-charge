"""Applies the recommended charging power/current to each configured wallbox.

Listens to the coordinator and for each charger writes the set_current (A) or
set_power (W) entity, and toggles the optional enable switch. Per-charger
hysteresis prevents chattering.
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback

from .const import (
    CHARGER_ID,
    CHARGER_SET_CURRENT_ENTITY,
    CHARGER_SET_POWER_ENTITY,
    CHARGER_SWITCH_ENTITY,
    CONF_CHARGERS,
)
from .coordinator import ChargerSnapshot, FlowSnapshot, SolarChargeCoordinator

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
        self._last_current: dict[str, float] = {}
        self._last_power: dict[str, float] = {}
        self._last_switch: dict[str, bool] = {}

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
        cfg_by_id = {
            c[CHARGER_ID]: c
            for c in (self._cfg.get(CONF_CHARGERS, []) or [])
            if CHARGER_ID in c
        }
        for ch in snap.chargers:
            cfg = cfg_by_id.get(ch.id)
            if not cfg:
                continue
            await self._apply_one(ch, cfg)

    async def _apply_one(self, ch: ChargerSnapshot, cfg: dict[str, Any]) -> None:
        switch_entity = cfg.get(CHARGER_SWITCH_ENTITY)
        current_entity = cfg.get(CHARGER_SET_CURRENT_ENTITY)
        power_entity = cfg.get(CHARGER_SET_POWER_ENTITY)

        should_charge = ch.recommended_power > 0

        # Enable/disable switch with hysteresis
        if switch_entity and self._last_switch.get(ch.id) != should_charge:
            service = "turn_on" if should_charge else "turn_off"
            domain = switch_entity.split(".")[0]
            try:
                await self.hass.services.async_call(
                    domain, service, {"entity_id": switch_entity}, blocking=False
                )
                self._last_switch[ch.id] = should_charge
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("Failed to %s %s: %s", service, switch_entity, err)

        if not should_charge:
            return

        if current_entity:
            amps = max(ch.min_current, min(ch.max_current, round(ch.recommended_current)))
            prev = self._last_current.get(ch.id)
            if prev is None or abs(amps - prev) >= _CURRENT_EPSILON:
                await self._set_number(current_entity, amps)
                self._last_current[ch.id] = amps

        if power_entity:
            watts = round(ch.recommended_power)
            prev = self._last_power.get(ch.id)
            if prev is None or abs(watts - prev) >= _POWER_EPSILON:
                await self._set_number(power_entity, watts)
                self._last_power[ch.id] = watts

    async def _set_number(self, entity_id: str, value: float) -> None:
        domain = entity_id.split(".")[0]
        try:
            await self.hass.services.async_call(
                domain, "set_value", {"entity_id": entity_id, "value": value}, blocking=False
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Failed to set %s = %s: %s", entity_id, value, err)
