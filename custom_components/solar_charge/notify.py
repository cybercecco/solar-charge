"""Notification dispatcher for Solar Charge Balancer.

Supports multiple chargers: emits a charge-complete notification for each
wallbox that transitions from charging → stopped, and one global
over-consumption alert (with de-duplication).
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.util import dt as dt_util

from .const import (
    CONF_MAX_HOUSEHOLD_POWER_W,
    CONF_NOTIFY_ON_CHARGE_COMPLETE,
    CONF_NOTIFY_ON_MODE_CHANGE,
    CONF_NOTIFY_ON_OVERCONSUMPTION,
    CONF_NOTIFY_TARGETS,
    CONF_OVERCONSUMPTION_THRESHOLD_W,
)
from .coordinator import FlowSnapshot, SolarChargeCoordinator

_LOGGER = logging.getLogger(__name__)
_OVERCONSUMPTION_COOLDOWN = timedelta(minutes=5)
_CAP_COOLDOWN = timedelta(minutes=2)


class NotificationDispatcher:
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
        self._last_overconsumption = None
        self._last_cap_warning = None
        self._last_cap_alarm = None
        self._last_mode = coordinator.mode

    @callback
    def async_start(self) -> None:
        self._unsub = self.coordinator.async_add_listener(self._handle_update)

    @callback
    def async_stop(self) -> None:
        if self._unsub is not None:
            self._unsub()
            self._unsub = None

    @callback
    def _handle_update(self) -> None:
        snap: FlowSnapshot | None = self.coordinator.data
        if snap is None:
            return

        # Per-charger charge complete
        if self._cfg.get(CONF_NOTIFY_ON_CHARGE_COMPLETE, True):
            for ch in snap.chargers:
                if ch.charge_complete:
                    self.hass.async_create_task(
                        self._send(
                            title="Ricarica completata",
                            message=(
                                f"La ricarica di '{ch.name}' si è conclusa. "
                                f"Ultima potenza: {ch.power:.0f} W, SOC batteria casa: "
                                f"{snap.battery_soc if snap.battery_soc is not None else 'n/a'}%."
                            ),
                            tag=f"charge_complete_{ch.id}",
                        )
                    )

        notify_overconsumption = self._cfg.get(CONF_NOTIFY_ON_OVERCONSUMPTION, True)
        now = dt_util.utcnow()
        total_load = snap.house_power + snap.ev_power_total
        cap = self._cfg.get(CONF_MAX_HOUSEHOLD_POWER_W, 0) or 0

        # Over-consumption (independent absolute threshold)
        if notify_overconsumption and snap.overconsumption:
            if (
                self._last_overconsumption is None
                or now - self._last_overconsumption > _OVERCONSUMPTION_COOLDOWN
            ):
                threshold = self._cfg.get(CONF_OVERCONSUMPTION_THRESHOLD_W, 0)
                self.hass.async_create_task(
                    self._send(
                        title="Sovraconsumo rilevato",
                        message=(
                            f"Consumo totale {total_load:.0f} W "
                            f"oltre la soglia di {threshold} W."
                        ),
                        tag="overconsumption",
                    )
                )
                self._last_overconsumption = now

        # Hard cap reached: high-priority alarm
        if notify_overconsumption and snap.cap_reached and cap > 0:
            if (
                self._last_cap_alarm is None
                or now - self._last_cap_alarm > _CAP_COOLDOWN
            ):
                self.hass.async_create_task(
                    self._send(
                        title="⚠ Limite contatore raggiunto",
                        message=(
                            f"Carico totale {total_load:.0f} W al limite "
                            f"impostato di {cap:.0f} W. La ricarica EV "
                            f"è stata limitata per evitare lo stacco."
                        ),
                        tag="cap_reached",
                    )
                )
                self._last_cap_alarm = now
        # Approaching cap: soft warning (within tolerance band)
        elif (
            notify_overconsumption
            and snap.approaching_cap
            and not snap.cap_reached
            and cap > 0
        ):
            if (
                self._last_cap_warning is None
                or now - self._last_cap_warning > _CAP_COOLDOWN
            ):
                self.hass.async_create_task(
                    self._send(
                        title="Attenzione: vicino al limite contatore",
                        message=(
                            f"Carico totale {total_load:.0f} W: stai entrando "
                            f"nella tolleranza del limite ({cap:.0f} W)."
                        ),
                        tag="cap_warning",
                    )
                )
                self._last_cap_warning = now

        # Mode change
        if (
            self._cfg.get(CONF_NOTIFY_ON_MODE_CHANGE, False)
            and self._last_mode != snap.mode
        ):
            self.hass.async_create_task(
                self._send(
                    title="Modalità cambiata",
                    message=f"Nuova modalità di bilanciamento: {snap.mode}",
                    tag="mode_change",
                )
            )
            self._last_mode = snap.mode

    async def _send(self, title: str, message: str, tag: str) -> None:
        targets: list[str] = list(self._cfg.get(CONF_NOTIFY_TARGETS, []) or [])
        payload = {"title": title, "message": message, "data": {"tag": tag}}

        if not targets:
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {"title": title, "message": message, "notification_id": f"solar_charge_{tag}"},
                blocking=False,
            )
            return

        for target in targets:
            if "." in target:
                domain, service = target.split(".", 1)
            else:
                domain, service = "notify", target
            try:
                await self.hass.services.async_call(domain, service, payload, blocking=False)
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("Notification to %s.%s failed: %s", domain, service, err)
