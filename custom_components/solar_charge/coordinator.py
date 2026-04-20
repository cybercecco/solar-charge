"""Data coordinator for Solar Charge Balancer.

Computes real-time energy flows (PV, house load, battery, EV, grid) and the
recommended EV charging power/current based on the selected operating mode,
configurable thresholds and hysteresis.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ATTR_BATTERY_ALLOCATION,
    ATTR_BATTERY_POWER,
    ATTR_BATTERY_SOC,
    ATTR_EV_POWER,
    ATTR_GRID_POWER,
    ATTR_HOUSE_POWER,
    ATTR_MODE,
    ATTR_PV_POWER,
    ATTR_RECOMMENDED_EV_CURRENT,
    ATTR_RECOMMENDED_EV_POWER,
    ATTR_SURPLUS,
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
    CONF_EV_VOLTAGE,
    CONF_GRID_IS_EXPORT_NEGATIVE,
    CONF_GRID_POWER_ENTITY,
    CONF_HOUSE_POWER_ENTITY,
    CONF_HYSTERESIS_W,
    CONF_MIN_PV_SURPLUS_W,
    CONF_OVERCONSUMPTION_THRESHOLD_W,
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
    MODE_BALANCED,
    MODE_BOOST_BATTERY,
    MODE_BOOST_CAR,
    MODE_ECO,
    MODE_FAST,
    MODE_OFF,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class FlowSnapshot:
    """Snapshot of computed electrical flows and EV recommendation."""

    pv_power: float = 0.0
    house_power: float = 0.0
    grid_power: float = 0.0          # >0 importing, <0 exporting (normalised)
    battery_power: float = 0.0       # >0 charging, <0 discharging (normalised)
    battery_soc: float | None = None
    ev_power: float = 0.0
    surplus: float = 0.0             # PV - house - battery target - ev target
    recommended_ev_power: float = 0.0
    recommended_ev_current: float = 0.0
    battery_allocation: float = 0.0  # power allocated to battery
    mode: str = MODE_BALANCED
    overconsumption: bool = False
    charge_complete: bool = False
    raw: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            ATTR_PV_POWER: self.pv_power,
            ATTR_HOUSE_POWER: self.house_power,
            ATTR_GRID_POWER: self.grid_power,
            ATTR_BATTERY_POWER: self.battery_power,
            ATTR_BATTERY_SOC: self.battery_soc,
            ATTR_EV_POWER: self.ev_power,
            ATTR_SURPLUS: self.surplus,
            ATTR_RECOMMENDED_EV_POWER: self.recommended_ev_power,
            ATTR_RECOMMENDED_EV_CURRENT: self.recommended_ev_current,
            ATTR_BATTERY_ALLOCATION: self.battery_allocation,
            ATTR_MODE: self.mode,
            "overconsumption": self.overconsumption,
            "charge_complete": self.charge_complete,
        }


def _as_float(state: State | None) -> float | None:
    if state is None or state.state in (None, "", "unknown", "unavailable"):
        return None
    try:
        return float(state.state)
    except (TypeError, ValueError):
        return None


class SolarChargeCoordinator(DataUpdateCoordinator[FlowSnapshot]):
    """Coordinator that recomputes energy flows on a fixed interval."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        self._data = {**entry.data, **(entry.options or {})}
        interval = int(self._data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL))
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(seconds=interval),
        )
        # runtime-mutable state (exposed via number/switch/select entities)
        self.mode: str = self._data.get(CONF_DEFAULT_PRIORITY, MODE_BALANCED)
        self.battery_min_soc: int = int(self._data.get(CONF_BATTERY_MIN_SOC, DEFAULT_BATTERY_MIN_SOC))
        self.battery_target_soc: int = int(
            self._data.get(CONF_BATTERY_TARGET_SOC, DEFAULT_BATTERY_TARGET_SOC)
        )
        self.battery_max_charge_w: int = int(
            self._data.get(CONF_BATTERY_MAX_CHARGE_W, DEFAULT_BATTERY_MAX_CHARGE_W)
        )
        self.min_pv_surplus: int = int(self._data.get(CONF_MIN_PV_SURPLUS_W, DEFAULT_MIN_PV_SURPLUS_W))
        self.hysteresis: int = int(self._data.get(CONF_HYSTERESIS_W, DEFAULT_HYSTERESIS_W))
        self.overconsumption_w: int = int(
            self._data.get(CONF_OVERCONSUMPTION_THRESHOLD_W, DEFAULT_OVERCONSUMPTION_W)
        )
        self.ev_voltage: int = int(self._data.get(CONF_EV_VOLTAGE, DEFAULT_EV_VOLTAGE))
        self.ev_phases: int = int(self._data.get(CONF_EV_PHASES, DEFAULT_EV_PHASES))
        self.ev_min_current: int = int(self._data.get(CONF_EV_MIN_CURRENT, DEFAULT_EV_MIN_CURRENT))
        self.ev_max_current: int = int(self._data.get(CONF_EV_MAX_CURRENT, DEFAULT_EV_MAX_CURRENT))
        self._last_recommended_power: float = 0.0
        self._last_charge_state: bool = False

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------
    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.async_set_updated_data(self.data or FlowSnapshot(mode=mode))
        self.hass.async_create_task(self.async_request_refresh())

    @property
    def ev_power_per_amp(self) -> float:
        return float(self.ev_voltage) * (1.732 if self.ev_phases == 3 else 1.0) * float(self.ev_phases if self.ev_phases != 3 else 1)

    # For 1 phase: P = V*I ; for 3 phase (line-to-line 400V typical) we use V*I*sqrt(3)
    def amps_from_watts(self, watts: float) -> float:
        if self.ev_phases == 3:
            return max(0.0, watts / (self.ev_voltage * 1.732))
        return max(0.0, watts / self.ev_voltage)

    def watts_from_amps(self, amps: float) -> float:
        if self.ev_phases == 3:
            return amps * self.ev_voltage * 1.732
        return amps * self.ev_voltage

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------
    async def _async_update_data(self) -> FlowSnapshot:
        try:
            snap = self._read_inputs()
            self._compute_recommendation(snap)
            self._detect_events(snap)
            self._last_recommended_power = snap.recommended_ev_power
            return snap
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Solar Charge computation failed: {err}") from err

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _read_inputs(self) -> FlowSnapshot:
        hass = self.hass
        snap = FlowSnapshot(mode=self.mode)

        # PV
        pv_total = 0.0
        for eid in self._data.get(CONF_PV_POWER_ENTITIES, []) or []:
            val = _as_float(hass.states.get(eid))
            if val is not None:
                pv_total += val
        snap.pv_power = max(0.0, pv_total)

        # House load
        house_val = _as_float(hass.states.get(self._data.get(CONF_HOUSE_POWER_ENTITY, "")))
        snap.house_power = max(0.0, house_val or 0.0)

        # Grid: normalise so that >0 means import, <0 means export
        grid_val = _as_float(hass.states.get(self._data.get(CONF_GRID_POWER_ENTITY, "")))
        if grid_val is not None:
            export_negative = bool(self._data.get(CONF_GRID_IS_EXPORT_NEGATIVE, True))
            snap.grid_power = grid_val if export_negative else -grid_val

        # Battery: normalise so that >0 means charging, <0 means discharging
        batt_val = _as_float(hass.states.get(self._data.get(CONF_BATTERY_POWER_ENTITY, "")))
        if batt_val is not None:
            charge_positive = bool(self._data.get(CONF_BATTERY_CHARGE_POSITIVE, True))
            snap.battery_power = batt_val if charge_positive else -batt_val
        snap.battery_soc = _as_float(hass.states.get(self._data.get(CONF_BATTERY_SOC_ENTITY, "")))

        # EV current draw
        ev_val = _as_float(hass.states.get(self._data.get(CONF_EV_CHARGER_POWER_ENTITY, "")))
        snap.ev_power = max(0.0, ev_val or 0.0)

        return snap

    def _compute_recommendation(self, snap: FlowSnapshot) -> None:
        """Run the balancing algorithm.

        Definition:
            available = PV - (house_load - current_ev_power)
        i.e. what PV leaves after covering the real household demand. The
        currently flowing EV power is treated as a *consumer* we control so it
        must be excluded from the "house" component before re-allocation.
        """
        base_house = max(0.0, snap.house_power - snap.ev_power)
        available = snap.pv_power - base_house  # can be negative
        snap.surplus = available

        soc = snap.battery_soc if snap.battery_soc is not None else 50.0
        batt_headroom = max(0.0, self.battery_target_soc - soc)
        batt_can_charge = batt_headroom > 0 and soc < self.battery_target_soc
        batt_max = float(self.battery_max_charge_w) if batt_can_charge else 0.0
        ev_max_w = self.watts_from_amps(self.ev_max_current)
        ev_min_w = self.watts_from_amps(self.ev_min_current)

        ev_target = 0.0
        batt_target = 0.0

        mode = self.mode
        if mode == MODE_OFF:
            ev_target = 0.0
            batt_target = min(batt_max, max(0.0, available))
        elif mode == MODE_FAST:
            ev_target = ev_max_w
            leftover = available - ev_target
            batt_target = min(batt_max, max(0.0, leftover))
        elif mode == MODE_ECO:
            # only route surplus to EV, never import from grid
            effective = max(0.0, available - batt_max) if batt_can_charge else max(0.0, available)
            if effective >= self.min_pv_surplus + ev_min_w:
                ev_target = min(ev_max_w, effective)
            batt_target = min(batt_max, max(0.0, available - ev_target))
        elif mode == MODE_BOOST_CAR:
            # car first, then battery with remaining PV
            if available >= ev_min_w:
                ev_target = min(ev_max_w, max(available, ev_min_w))
            else:
                # boost: allow a bit of grid import if soc is acceptable
                ev_target = ev_min_w if soc >= self.battery_min_soc else 0.0
            batt_target = min(batt_max, max(0.0, available - ev_target))
        elif mode == MODE_BOOST_BATTERY:
            batt_target = min(batt_max, max(0.0, available))
            leftover = available - batt_target
            if leftover >= self.min_pv_surplus + ev_min_w:
                ev_target = min(ev_max_w, leftover)
        else:  # MODE_BALANCED
            if soc < self.battery_min_soc:
                # protect battery first
                batt_target = min(batt_max, max(0.0, available))
                leftover = available - batt_target
                if leftover >= self.min_pv_surplus + ev_min_w:
                    ev_target = min(ev_max_w, leftover)
            else:
                # split 50/50 above min surplus
                if available >= self.min_pv_surplus:
                    half = available / 2.0
                    batt_target = min(batt_max, half)
                    ev_candidate = available - batt_target
                    if ev_candidate >= ev_min_w:
                        ev_target = min(ev_max_w, ev_candidate)
                    else:
                        batt_target = min(batt_max, available)

        # Hysteresis to avoid flapping around the min threshold
        if ev_target > 0 and abs(ev_target - self._last_recommended_power) < self.hysteresis:
            ev_target = self._last_recommended_power
        if 0 < ev_target < ev_min_w:
            ev_target = 0.0

        snap.recommended_ev_power = round(ev_target, 1)
        snap.recommended_ev_current = round(self.amps_from_watts(ev_target), 2)
        snap.battery_allocation = round(batt_target, 1)

    def _detect_events(self, snap: FlowSnapshot) -> None:
        # Overconsumption flag — compared on total house side (excluding EV)
        total_load = snap.house_power + snap.ev_power
        snap.overconsumption = total_load >= self.overconsumption_w

        # Charge complete transition: was charging, now at 0 while status says stopped
        was_charging = self._last_charge_state
        is_charging = snap.ev_power >= 200.0  # hysteresis threshold
        snap.charge_complete = bool(was_charging and not is_charging)
        self._last_charge_state = is_charging
