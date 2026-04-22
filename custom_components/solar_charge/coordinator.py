"""Data coordinator for Solar Charge Balancer.

Computes real-time energy flows (PV, house load, battery, EVs, grid) and the
recommended EV charging power/current per-wallbox based on the selected
operating mode, priority / distribution strategy and hysteresis.
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
    CHARGER_VOLTAGE,
    CONF_BATTERIES,
    CONF_BATTERY_MAX_CHARGE_W,
    CONF_BATTERY_MIN_SOC,
    CONF_BATTERY_TARGET_SOC,
    CONF_CHARGER_DISTRIBUTION,
    CONF_CHARGERS,
    CONF_DEFAULT_PRIORITY,
    CONF_GRID_IS_EXPORT_NEGATIVE,
    CONF_GRID_POWER_ENTITY,
    CONF_HOUSE_POWER_ENTITY,
    CONF_HYSTERESIS_W,
    CONF_MIN_PV_SURPLUS_W,
    CONF_MAX_HOUSEHOLD_POWER_W,
    CONF_OVERCONSUMPTION_THRESHOLD_W,
    CONF_PV_POWER_ENTITIES,
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
    DEFAULT_MAX_HOUSEHOLD_POWER_W,
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


# ---------------------------------------------------------------------------
# Per-battery snapshot
# ---------------------------------------------------------------------------
@dataclass
class BatterySnapshot:
    id: str
    name: str
    capacity_kwh: float = 0.0
    power: float = 0.0          # W, >0 = charging
    soc: float | None = None    # %


# ---------------------------------------------------------------------------
# Per-charger snapshot
# ---------------------------------------------------------------------------
@dataclass
class ChargerSnapshot:
    id: str
    name: str
    priority: int = 10
    phases: int = 1
    voltage: int = 230
    min_current: int = 6
    max_current: int = 16
    power: float = 0.0                  # current draw (W)
    recommended_power: float = 0.0      # W allocated now
    recommended_current: float = 0.0    # A derived from recommended_power
    charging: bool = False
    charge_complete: bool = False       # transition flag for this tick
    boost: bool = False                 # per-charger boost flag


@dataclass
class FlowSnapshot:
    pv_power: float = 0.0
    house_power: float = 0.0
    grid_power: float = 0.0
    battery_power: float = 0.0
    battery_soc: float | None = None
    ev_power_total: float = 0.0
    surplus: float = 0.0
    recommended_ev_power_total: float = 0.0
    battery_allocation: float = 0.0
    mode: str = MODE_BALANCED
    overconsumption: bool = False
    chargers: list[ChargerSnapshot] = field(default_factory=list)
    batteries: list[BatterySnapshot] = field(default_factory=list)
    # Fields that were computed via energy-balance instead of being measured.
    # Useful for UIs that want to show a "derived" badge.
    derived_fields: set[str] = field(default_factory=set)


def _as_float(state: State | None) -> float | None:
    if state is None or state.state in (None, "", "unknown", "unavailable"):
        return None
    try:
        return float(state.state)
    except (TypeError, ValueError):
        return None


class SolarChargeCoordinator(DataUpdateCoordinator[FlowSnapshot]):
    """Recompute energy flows at a fixed interval."""

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
        # Runtime-mutable state (exposed via number/switch/select)
        self.mode: str = self._data.get(CONF_DEFAULT_PRIORITY, MODE_BALANCED)
        self.distribution: str = self._data.get(CONF_CHARGER_DISTRIBUTION, DEFAULT_CHARGER_DISTRIBUTION)
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
        self.max_household_w: int = int(
            self._data.get(CONF_MAX_HOUSEHOLD_POWER_W, DEFAULT_MAX_HOUSEHOLD_POWER_W)
        )
        self._last_total_reco: float = 0.0
        self._per_charger_last_reco: dict[str, float] = {}
        self._per_charger_last_charging: dict[str, bool] = {}
        self._per_charger_boost: dict[str, bool] = {}
        # Round robin cursor for equal distribution strategy
        self._rr_cursor = 0

    # ------------------------------------------------------------------
    # Runtime helpers
    # ------------------------------------------------------------------
    @property
    def chargers_cfg(self) -> list[dict[str, Any]]:
        return list(self._data.get(CONF_CHARGERS, []) or [])

    @property
    def batteries_cfg(self) -> list[dict[str, Any]]:
        return list(self._data.get(CONF_BATTERIES, []) or [])

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.hass.async_create_task(self.async_request_refresh())

    def set_boost(self, charger_id: str, value: bool) -> None:
        self._per_charger_boost[charger_id] = value
        self.hass.async_create_task(self.async_request_refresh())

    def get_boost(self, charger_id: str) -> bool:
        return self._per_charger_boost.get(charger_id, False)

    @staticmethod
    def amps_from_watts(watts: float, voltage: int, phases: int) -> float:
        if phases == 3:
            return max(0.0, watts / (voltage * 1.732))
        return max(0.0, watts / max(voltage, 1))

    @staticmethod
    def watts_from_amps(amps: float, voltage: int, phases: int) -> float:
        if phases == 3:
            return amps * voltage * 1.732
        return amps * voltage

    # ------------------------------------------------------------------
    # Main cycle
    # ------------------------------------------------------------------
    async def _async_update_data(self) -> FlowSnapshot:
        try:
            snap = self._read_inputs()
            self._compute_recommendation(snap)
            self._detect_events(snap)
            return snap
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Solar Charge computation failed: {err}") from err

    # ------------------------------------------------------------------
    def _read_inputs(self) -> FlowSnapshot:
        hass = self.hass
        snap = FlowSnapshot(mode=self.mode)

        # ---- PV ----------------------------------------------------------
        # When at least one PV entity is configured we consider PV measured,
        # even if individual sensors return None: partial read still counts.
        pv_entities = self._data.get(CONF_PV_POWER_ENTITIES, []) or []
        pv_readings: list[float] = []
        for eid in pv_entities:
            val = _as_float(hass.states.get(eid))
            if val is not None:
                pv_readings.append(val)
        pv_measured: float | None = (
            sum(pv_readings) if pv_entities and pv_readings else None
        )

        # ---- House -------------------------------------------------------
        house_measured = _as_float(
            hass.states.get(self._data.get(CONF_HOUSE_POWER_ENTITY, "") or "")
        )

        # ---- Grid --------------------------------------------------------
        grid_raw = _as_float(
            hass.states.get(self._data.get(CONF_GRID_POWER_ENTITY, "") or "")
        )
        grid_measured: float | None
        if grid_raw is None:
            grid_measured = None
        else:
            export_negative = bool(self._data.get(CONF_GRID_IS_EXPORT_NEGATIVE, True))
            # Normalize to: positive = import, negative = export.
            grid_measured = grid_raw if export_negative else -grid_raw

        # ---- Batteries (aggregate across N units) ------------------------
        total_batt_power = 0.0
        any_battery_configured = False
        any_battery_measured = False
        weighted_soc_sum = 0.0
        weighted_soc_cap = 0.0
        soc_values: list[float] = []
        for bcfg in self.batteries_cfg:
            bid = bcfg.get(BATTERY_ID) or ""
            bname = bcfg.get(BATTERY_NAME) or bid or "battery"
            cap = float(bcfg.get(BATTERY_CAPACITY_KWH) or 0.0)
            b = BatterySnapshot(id=bid, name=bname, capacity_kwh=cap)

            if bcfg.get(BATTERY_POWER_ENTITY):
                any_battery_configured = True
            pw = _as_float(hass.states.get(bcfg.get(BATTERY_POWER_ENTITY, "") or ""))
            if pw is not None:
                charge_positive = bool(bcfg.get(BATTERY_CHARGE_POSITIVE, True))
                b.power = pw if charge_positive else -pw
                total_batt_power += b.power
                any_battery_measured = True

            soc_v = _as_float(hass.states.get(bcfg.get(BATTERY_SOC_ENTITY, "") or ""))
            if soc_v is not None:
                b.soc = soc_v
                soc_values.append(soc_v)
                if cap > 0:
                    weighted_soc_sum += soc_v * cap
                    weighted_soc_cap += cap

            snap.batteries.append(b)

        # battery_power: None if configured entities exist but none responded,
        # 0.0 if user has no batteries at all (legitimate zero, not missing).
        battery_measured: float | None
        if any_battery_measured:
            battery_measured = total_batt_power
        elif any_battery_configured:
            battery_measured = None  # configured but unavailable
        else:
            battery_measured = 0.0   # no batteries at all

        if weighted_soc_cap > 0:
            snap.battery_soc = weighted_soc_sum / weighted_soc_cap
        elif soc_values:
            snap.battery_soc = sum(soc_values) / len(soc_values)
        else:
            snap.battery_soc = None

        # ---- EV chargers -------------------------------------------------
        ev_total = 0.0
        for cfg in self.chargers_cfg:
            ch = ChargerSnapshot(
                id=cfg[CHARGER_ID],
                name=cfg.get(CHARGER_NAME, cfg[CHARGER_ID]),
                priority=int(cfg.get(CHARGER_PRIORITY, 10)),
                phases=int(cfg.get(CHARGER_PHASES, DEFAULT_EV_PHASES)),
                voltage=int(cfg.get(CHARGER_VOLTAGE, DEFAULT_EV_VOLTAGE)),
                min_current=int(cfg.get(CHARGER_MIN_CURRENT, DEFAULT_EV_MIN_CURRENT)),
                max_current=int(cfg.get(CHARGER_MAX_CURRENT, DEFAULT_EV_MAX_CURRENT)),
                boost=self._per_charger_boost.get(cfg[CHARGER_ID], False),
            )
            pw = _as_float(hass.states.get(cfg.get(CHARGER_POWER_ENTITY, "") or ""))
            ch.power = max(0.0, pw or 0.0)
            ev_total += ch.power
            snap.chargers.append(ch)
        snap.ev_power_total = ev_total

        # ---- Fill the snapshot + derive anything missing -----------------
        self._finalize_power_fields(
            snap,
            pv=pv_measured,
            house=house_measured,
            grid=grid_measured,
            battery=battery_measured,
        )
        return snap

    # ------------------------------------------------------------------
    # Energy-balance based derivation
    # ------------------------------------------------------------------
    # Fundamental identity (instantaneous, Watts, with signed grid/battery):
    #
    #   PV + max(-Battery, 0) + max(Grid, 0) = House + max(Battery, 0) + max(-Grid, 0)
    #
    # or equivalently, with signed values:
    #
    #   House = PV + Grid - Battery
    #
    # where `Grid > 0` means importing from the grid, `Battery > 0` means
    # charging, and `House` is the total instantaneous consumption of the
    # home as reported by the house meter, which *includes* any EV charger
    # installed downstream of it (the normal residential topology). The
    # downstream EV power is later stripped out inside the balancing
    # algorithm via `base_house = house - ev_total`.
    #
    # From the equation above we can recover any ONE missing quantity
    # when the other three are measured:
    #
    #   House   = PV + Grid - Battery
    #   PV      = House + Battery - Grid
    #   Grid    = House + Battery - PV
    #   Battery = PV + Grid - House
    @staticmethod
    def _derive_one_missing(
        pv: float | None,
        house: float | None,
        grid: float | None,
        battery: float | None,
    ) -> tuple[float, float, float, float, str | None]:
        """Return (pv, house, grid, battery, derived_name).

        When exactly one of pv/house/grid/battery is None and the other
        three are known we solve the balance equation. Otherwise any
        remaining None is coerced to 0 and nothing is flagged as derived.
        """
        missing = [
            n for n, v in (("pv", pv), ("house", house), ("grid", grid), ("battery", battery))
            if v is None
        ]
        derived: str | None = None
        if len(missing) == 1:
            name = missing[0]
            if name == "house" and pv is not None and grid is not None and battery is not None:
                house = pv + grid - battery
                derived = "house"
            elif name == "grid" and pv is not None and house is not None and battery is not None:
                grid = house + battery - pv
                derived = "grid"
            elif name == "pv" and house is not None and grid is not None and battery is not None:
                pv = house + battery - grid
                derived = "pv"
            elif name == "battery" and pv is not None and house is not None and grid is not None:
                battery = pv + grid - house
                derived = "battery"

        return (pv or 0.0, house or 0.0, grid or 0.0, battery or 0.0, derived)

    def _finalize_power_fields(
        self,
        snap: FlowSnapshot,
        *,
        pv: float | None,
        house: float | None,
        grid: float | None,
        battery: float | None,
    ) -> None:
        pv_v, house_v, grid_v, batt_v, derived = self._derive_one_missing(
            pv, house, grid, battery
        )
        snap.pv_power = max(0.0, pv_v)
        snap.house_power = max(0.0, house_v)
        snap.grid_power = grid_v
        snap.battery_power = batt_v
        if derived:
            snap.derived_fields.add(derived)
            _LOGGER.debug(
                "Derived %s from energy balance: PV=%.0f House=%.0f Grid=%.0f Batt=%.0f EV=%.0f",
                derived, snap.pv_power, snap.house_power, snap.grid_power,
                snap.battery_power, snap.ev_power_total,
            )

    # ------------------------------------------------------------------
    def _compute_recommendation(self, snap: FlowSnapshot) -> None:
        """Compute total EV allocation, then distribute across chargers."""
        # 1) Available PV after covering house load (excluding current EV draw,
        #    which is a controlled consumer we will re-allocate)
        base_house = max(0.0, snap.house_power - snap.ev_power_total)
        available = snap.pv_power - base_house
        snap.surplus = available

        soc = snap.battery_soc if snap.battery_soc is not None else 50.0
        batt_headroom = max(0.0, self.battery_target_soc - soc)
        batt_can_charge = batt_headroom > 0 and soc < self.battery_target_soc
        batt_max = float(self.battery_max_charge_w) if batt_can_charge else 0.0

        # Total EV max across all chargers
        ev_max_total = sum(
            self.watts_from_amps(c.max_current, c.voltage, c.phases) for c in snap.chargers
        )
        ev_min_first = min(
            (self.watts_from_amps(c.min_current, c.voltage, c.phases) for c in snap.chargers),
            default=0.0,
        )

        ev_total = 0.0
        batt_target = 0.0
        mode = self.mode

        if mode == MODE_OFF:
            batt_target = min(batt_max, max(0.0, available))
        elif mode == MODE_FAST:
            ev_total = ev_max_total
            leftover = available - ev_total
            batt_target = min(batt_max, max(0.0, leftover))
        elif mode == MODE_ECO:
            effective = max(0.0, available - batt_max) if batt_can_charge else max(0.0, available)
            if effective >= self.min_pv_surplus + ev_min_first:
                ev_total = min(ev_max_total, effective)
            batt_target = min(batt_max, max(0.0, available - ev_total))
        elif mode == MODE_BOOST_CAR:
            if available >= ev_min_first:
                ev_total = min(ev_max_total, max(available, ev_min_first))
            else:
                ev_total = ev_min_first if soc >= self.battery_min_soc else 0.0
            batt_target = min(batt_max, max(0.0, available - ev_total))
        elif mode == MODE_BOOST_BATTERY:
            batt_target = min(batt_max, max(0.0, available))
            leftover = available - batt_target
            if leftover >= self.min_pv_surplus + ev_min_first:
                ev_total = min(ev_max_total, leftover)
        else:  # MODE_BALANCED
            if soc < self.battery_min_soc:
                batt_target = min(batt_max, max(0.0, available))
                leftover = available - batt_target
                if leftover >= self.min_pv_surplus + ev_min_first:
                    ev_total = min(ev_max_total, leftover)
            else:
                if available >= self.min_pv_surplus:
                    half = available / 2.0
                    batt_target = min(batt_max, half)
                    ev_candidate = available - batt_target
                    if ev_candidate >= ev_min_first:
                        ev_total = min(ev_max_total, ev_candidate)
                    else:
                        batt_target = min(batt_max, available)

        # Hard safety cap: no matter the mode (boost included), the total
        # instantaneous household draw must not exceed max_household_w.
        # `base_house` already excludes current EV draw, so the headroom
        # available to EVs is `cap - base_house`.
        if self.max_household_w > 0:
            ev_cap = max(0.0, self.max_household_w - base_house)
            if ev_total > ev_cap:
                _LOGGER.debug(
                    "EV allocation capped by household limit: %.0f -> %.0f "
                    "(cap=%d, base_house=%.0f)",
                    ev_total, ev_cap, self.max_household_w, base_house,
                )
                ev_total = ev_cap

        # Global hysteresis
        if ev_total > 0 and abs(ev_total - self._last_total_reco) < self.hysteresis:
            ev_total = self._last_total_reco

        self._distribute_to_chargers(snap, ev_total)

        snap.recommended_ev_power_total = round(sum(c.recommended_power for c in snap.chargers), 1)
        snap.battery_allocation = round(batt_target, 1)
        self._last_total_reco = snap.recommended_ev_power_total

    # ------------------------------------------------------------------
    def _distribute_to_chargers(self, snap: FlowSnapshot, ev_total: float) -> None:
        """Split the total EV allocation between chargers."""
        if not snap.chargers or ev_total <= 0:
            for ch in snap.chargers:
                ch.recommended_power = 0.0
                ch.recommended_current = 0.0
            return

        # Boosted chargers jump to priority 0
        def effective_priority(ch: ChargerSnapshot) -> int:
            return 0 if ch.boost else ch.priority

        remaining = ev_total

        if self.distribution == "equal":
            active = [c for c in snap.chargers if c.max_current > 0]
            if not active:
                return
            # Each gets an equal share but clamped to its own min/max
            share = remaining / len(active)
            for ch in active:
                cap_max = self.watts_from_amps(ch.max_current, ch.voltage, ch.phases)
                cap_min = self.watts_from_amps(ch.min_current, ch.voltage, ch.phases)
                alloc = min(cap_max, share)
                if alloc < cap_min:
                    alloc = 0.0
                ch.recommended_power = alloc
            # Redistribute unused bits to first that can take more
            used = sum(c.recommended_power for c in active)
            extra = remaining - used
            for ch in sorted(active, key=effective_priority):
                cap_max = self.watts_from_amps(ch.max_current, ch.voltage, ch.phases)
                room = cap_max - ch.recommended_power
                if room > 0 and extra > 0:
                    take = min(room, extra)
                    ch.recommended_power += take
                    extra -= take
        elif self.distribution == "roundrobin":
            active = sorted(snap.chargers, key=effective_priority)
            self._rr_cursor = (self._rr_cursor + 1) % max(1, len(active))
            ordered = active[self._rr_cursor:] + active[: self._rr_cursor]
            self._fill_in_order(ordered, ev_total)
        else:  # priority (default)
            ordered = sorted(snap.chargers, key=effective_priority)
            self._fill_in_order(ordered, ev_total)

        # Post-process: apply min-current clamp and per-charger hysteresis
        for ch in snap.chargers:
            cap_min = self.watts_from_amps(ch.min_current, ch.voltage, ch.phases)
            if 0 < ch.recommended_power < cap_min:
                ch.recommended_power = 0.0
            # per-charger hysteresis
            prev = self._per_charger_last_reco.get(ch.id, 0.0)
            if ch.recommended_power > 0 and abs(ch.recommended_power - prev) < self.hysteresis:
                ch.recommended_power = prev
            self._per_charger_last_reco[ch.id] = ch.recommended_power
            ch.recommended_power = round(ch.recommended_power, 1)
            ch.recommended_current = round(
                self.amps_from_watts(ch.recommended_power, ch.voltage, ch.phases), 2
            )

    def _fill_in_order(self, ordered: list[ChargerSnapshot], total: float) -> None:
        """Greedy fill: each charger gets up to its max, in order."""
        remaining = total
        for ch in ordered:
            cap_max = self.watts_from_amps(ch.max_current, ch.voltage, ch.phases)
            cap_min = self.watts_from_amps(ch.min_current, ch.voltage, ch.phases)
            if remaining >= cap_min:
                alloc = min(cap_max, remaining)
                ch.recommended_power = alloc
                remaining -= alloc
            else:
                ch.recommended_power = 0.0

    # ------------------------------------------------------------------
    def _detect_events(self, snap: FlowSnapshot) -> None:
        total_load = snap.house_power + snap.ev_power_total
        snap.overconsumption = total_load >= self.overconsumption_w

        for ch in snap.chargers:
            was_charging = self._per_charger_last_charging.get(ch.id, False)
            ch.charging = ch.power >= 200.0
            ch.charge_complete = bool(was_charging and not ch.charging)
            self._per_charger_last_charging[ch.id] = ch.charging
