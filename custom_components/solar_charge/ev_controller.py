"""Applies the recommended charging power/current to each configured wallbox.

Listens to the coordinator and for each charger writes the set_current (A) or
set_power (W) entity, and toggles the optional enable switch. Per-charger
hysteresis prevents chattering.
"""
from __future__ import annotations

import asyncio
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
_SWITCH_DOMAINS = frozenset({"switch", "input_boolean"})
_NUMBER_DOMAINS = frozenset({"number", "input_number"})
# Consecutive apply cycles with a failed write before latching the problem sensor.
_FAULT_STREAK = 3


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
        self._apply_task: asyncio.Task | None = None
        self._last_current: dict[str, float] = {}
        self._last_power: dict[str, float] = {}
        self._last_switch: dict[str, bool] = {}
        # Tracks the previous coordinator mode so we can detect a
        # MANUAL → other transition and immediately reapply control.
        self._prev_manual: bool = False
        self._fail_streak: int = 0
        self._fault_notified: bool = False
        self._cycle_failed: bool = False

    @callback
    def async_start(self) -> None:
        self._unsub = self.coordinator.async_add_listener(self._handle_update)

    @callback
    def async_stop(self) -> None:
        if self._unsub is not None:
            self._unsub()
            self._unsub = None
        if self._apply_task and not self._apply_task.done():
            self._apply_task.cancel()
            self._apply_task = None

    # ------------------------------------------------------------------
    @callback
    def _handle_update(self) -> None:
        snap: FlowSnapshot | None = self.coordinator.data
        if snap is None:
            return
        # Serialize applies: cancel any in-flight write cycle so overlapping
        # coordinator ticks cannot chatter switches/numbers.
        if self._apply_task and not self._apply_task.done():
            self._apply_task.cancel()
        self._apply_task = self.hass.async_create_task(self._apply(snap))

    async def _apply(self, snap: FlowSnapshot) -> None:
        self._cycle_failed = False
        try:
            await self._apply_inner(snap)
        except asyncio.CancelledError:
            raise
        except Exception as err:  # noqa: BLE001
            self._cycle_failed = True
            _LOGGER.warning("EV apply failed: %s", err)
        self._record_cycle("" if not self._cycle_failed else "wallbox write failed")

    async def _apply_inner(self, snap: FlowSnapshot) -> None:
        # Manual mode: stay out of the way completely.
        if snap.manual:
            self._prev_manual = True
            return

        # Detect "manual → automatic" transition: clear all hysteresis
        # caches so the next write is forced regardless of how close the
        # new value is to the last written one. This guarantees the user
        # gets immediate control back when they leave manual mode.
        if self._prev_manual:
            self._last_current.clear()
            self._last_power.clear()
            self._last_switch.clear()
            self._prev_manual = False
            _LOGGER.info(
                "Solar Charge: leaving manual mode → forcing immediate "
                "re-apply on all chargers"
            )

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

        # Enable/disable switch. Stop ignores hysteresis and retries until
        # the entity actually reports off — a scheduled call that returns
        # without raising is not proof the wallbox stopped.
        if switch_entity:
            if not should_charge:
                if not self._switch_matches(switch_entity, False):
                    ok = await self._call_switch(
                        switch_entity, "turn_off", blocking=True
                    )
                    if ok and self._switch_matches(switch_entity, False):
                        self._last_switch[ch.id] = False
                    else:
                        self._cycle_failed = True
                        _LOGGER.warning(
                            "Stop of %s not confirmed off", switch_entity
                        )
                else:
                    self._last_switch[ch.id] = False
            elif self._last_switch.get(ch.id) is not True:
                ok = await self._call_switch(
                    switch_entity, "turn_on", blocking=False
                )
                if ok:
                    self._last_switch[ch.id] = True
                else:
                    self._cycle_failed = True

        if not should_charge:
            # Fail-safe stop: always drive current/power to 0 even when no
            # enable switch is configured (common for Tuya / OEM number-only
            # wallboxes that would otherwise keep the last setpoint).
            # Cache the zero only after a confirmed write so a failure retries.
            if current_entity:
                if await self._set_number(current_entity, 0, blocking=True):
                    self._last_current[ch.id] = 0.0
                else:
                    self._cycle_failed = True
            if power_entity:
                if await self._set_number(power_entity, 0, blocking=True):
                    self._last_power[ch.id] = 0.0
                else:
                    self._cycle_failed = True
            return

        if current_entity:
            amps = max(ch.min_current, min(ch.max_current, round(ch.recommended_current)))
            prev = self._last_current.get(ch.id)
            if prev is None or abs(amps - prev) >= _CURRENT_EPSILON:
                if await self._set_number(current_entity, amps):
                    self._last_current[ch.id] = amps
                else:
                    self._cycle_failed = True

        if power_entity:
            watts = round(ch.recommended_power)
            prev = self._last_power.get(ch.id)
            if prev is None or abs(watts - prev) >= _POWER_EPSILON:
                if await self._set_number(power_entity, watts):
                    self._last_power[ch.id] = watts
                else:
                    self._cycle_failed = True

    def _switch_matches(self, entity_id: str, want_on: bool) -> bool:
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable", ""):
            return False
        return (state.state == "on") is want_on

    def _record_cycle(self, detail: str) -> None:
        if not detail:
            self._fail_streak = 0
            if self.coordinator.actuation_fault:
                self.coordinator.actuation_fault = False
                self.coordinator.actuation_fault_detail = ""
                if self._fault_notified:
                    self._fault_notified = False
                    self.hass.async_create_task(self._clear_fault_notification())
            return
        self._fail_streak += 1
        if self._fail_streak < _FAULT_STREAK:
            return
        self.coordinator.actuation_fault = True
        self.coordinator.actuation_fault_detail = detail
        if self._fault_notified:
            return
        self._fault_notified = True
        self.hass.async_create_task(self._notify_fault(detail))

    async def _notify_fault(self, detail: str) -> None:
        try:
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": "Solar Charge: errore wallbox",
                    "message": (
                        "Scritture verso la colonnina fallite per "
                        f"{_FAULT_STREAK} cicli consecutivi ({detail}). "
                        "Il sensore «Errore controllo EV» è attivo."
                    ),
                    "notification_id": "solar_charge_actuation_fault",
                },
                blocking=False,
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Could not raise actuation fault notification: %s", err)

    async def _clear_fault_notification(self) -> None:
        try:
            await self.hass.services.async_call(
                "persistent_notification",
                "dismiss",
                {"notification_id": "solar_charge_actuation_fault"},
                blocking=False,
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Could not dismiss actuation fault notification: %s", err)

    async def _call_switch(
        self, entity_id: str, service: str, *, blocking: bool = False
    ) -> bool:
        if not isinstance(entity_id, str) or "." not in entity_id:
            _LOGGER.warning("Ignoring invalid switch entity_id: %s", entity_id)
            return False
        domain = entity_id.split(".", 1)[0]
        if domain not in _SWITCH_DOMAINS:
            _LOGGER.warning(
                "Refusing to call %s.%s on non-switch entity %s",
                domain,
                service,
                entity_id,
            )
            return False
        try:
            await self.hass.services.async_call(
                domain, service, {"entity_id": entity_id}, blocking=blocking
            )
            return True
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Failed to %s %s: %s", service, entity_id, err)
            return False

    async def _set_number(
        self, entity_id: str, value: float, *, blocking: bool = False
    ) -> bool:
        if not isinstance(entity_id, str) or "." not in entity_id:
            _LOGGER.warning("Ignoring invalid number entity_id: %s", entity_id)
            return False
        domain = entity_id.split(".", 1)[0]
        if domain not in _NUMBER_DOMAINS:
            _LOGGER.warning(
                "Refusing to set_value on non-number entity %s", entity_id
            )
            return False
        try:
            await self.hass.services.async_call(
                domain,
                "set_value",
                {"entity_id": entity_id, "value": value},
                blocking=blocking,
            )
            return True
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Failed to set %s = %s: %s", entity_id, value, err)
            return False
