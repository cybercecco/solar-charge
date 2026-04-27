"""Constants for the Solar Charge Balancer integration."""
from __future__ import annotations

from typing import Final

DOMAIN: Final = "solar_charge"
PLATFORMS: Final = ["sensor", "number", "switch", "select", "binary_sensor"]

# ---------------------------------------------------------------------------
# Configuration schema version (bump together with async_migrate_entry)
# ---------------------------------------------------------------------------
CONFIG_VERSION: Final = 3

# ---------------------------------------------------------------------------
# Top-level keys
# ---------------------------------------------------------------------------
CONF_TITLE: Final = "title"
CONF_CONFIGURED: Final = "_configured"  # internal flag set once the user runs the wizard

# PV production
CONF_PV_POWER_ENTITIES: Final = "pv_power_entities"          # list[str] W
CONF_PV_ENERGY_ENTITIES: Final = "pv_energy_entities"        # optional list[str] Wh/kWh

# House / grid
CONF_HOUSE_POWER_ENTITY: Final = "house_power_entity"
CONF_GRID_POWER_ENTITY: Final = "grid_power_entity"
CONF_GRID_IS_EXPORT_NEGATIVE: Final = "grid_export_negative"

# ---------------------------------------------------------------------------
# Home batteries — list of dicts under CONF_BATTERIES.
# Global thresholds (min/target SOC, max charge power) stay at entry level
# because they act on the aggregated system.
# ---------------------------------------------------------------------------
CONF_BATTERIES: Final = "batteries"
BATTERY_ID: Final = "id"                        # stable uuid4
BATTERY_NAME: Final = "name"
BATTERY_POWER_ENTITY: Final = "power_entity"
BATTERY_SOC_ENTITY: Final = "soc_entity"
BATTERY_CHARGE_POSITIVE: Final = "charge_positive"
BATTERY_CAPACITY_KWH: Final = "capacity_kwh"

# Global battery strategy knobs
CONF_BATTERY_MIN_SOC: Final = "battery_min_soc"
CONF_BATTERY_TARGET_SOC: Final = "battery_target_soc"
CONF_BATTERY_MAX_CHARGE_W: Final = "battery_max_charge_w"

# Legacy v1/v2 single-battery keys (kept for migration only)
CONF_BATTERY_POWER_ENTITY_LEGACY: Final = "battery_power_entity"
CONF_BATTERY_SOC_ENTITY_LEGACY: Final = "battery_soc_entity"
CONF_BATTERY_CHARGE_POSITIVE_LEGACY: Final = "battery_charge_positive"
CONF_BATTERY_CAPACITY_KWH_LEGACY: Final = "battery_capacity_kwh"

# ---------------------------------------------------------------------------
# EV chargers — list of dicts under CONF_CHARGERS
# Each item is a dict with the CHARGER_* keys below.
# ---------------------------------------------------------------------------
CONF_CHARGERS: Final = "chargers"
CHARGER_ID: Final = "id"                    # stable uuid4 (auto-generated)
CHARGER_NAME: Final = "name"                # user-friendly label
CHARGER_POWER_ENTITY: Final = "power_entity"
CHARGER_STATUS_ENTITY: Final = "status_entity"
CHARGER_SET_CURRENT_ENTITY: Final = "set_current_entity"
CHARGER_SET_POWER_ENTITY: Final = "set_power_entity"
CHARGER_SWITCH_ENTITY: Final = "switch_entity"
CHARGER_PHASES: Final = "phases"
CHARGER_VOLTAGE: Final = "voltage"
CHARGER_MIN_CURRENT: Final = "min_current"
CHARGER_MAX_CURRENT: Final = "max_current"
CHARGER_PRIORITY: Final = "priority"        # 1 = highest; lower ints get energy first

# Behaviour / thresholds
CONF_OVERCONSUMPTION_THRESHOLD_W: Final = "overconsumption_threshold_w"
# Hard cap on total instantaneous household power (grid + battery_discharge
# + pv consumed locally). When > 0 the coordinator will CLAMP the EV
# allocation so that `house_non_ev + ev_total <= cap`, regardless of boost
# or mode. 0 disables the cap.
CONF_MAX_HOUSEHOLD_POWER_W: Final = "max_household_power_w"
# Tolerance (% of the cap) used to emit an "approaching cap" warning before
# the hard limit is hit. E.g. 10% means: warn at >= 90% of cap, alarm at >= 100%.
CONF_MAX_HOUSEHOLD_TOLERANCE_PCT: Final = "max_household_tolerance_pct"
# In FAST mode: maximum amount of grid power (W) we are willing to *import*
# in addition to PV in order to feed the EV charger. When 0 the FAST mode
# behaves identically to "use all PV but do not buy from the grid".
CONF_FAST_GRID_BUDGET_W: Final = "fast_grid_budget_w"
# In BATTERY-FAST mode: SOC % the home battery must reach before any of the
# PV surplus is allowed to flow into the EV charger.
CONF_BATTERY_FAST_SOC: Final = "battery_fast_soc"
CONF_MIN_PV_SURPLUS_W: Final = "min_pv_surplus_w"
CONF_HYSTERESIS_W: Final = "hysteresis_w"
CONF_UPDATE_INTERVAL: Final = "update_interval"
CONF_DEFAULT_PRIORITY: Final = "default_priority"            # car | battery | balanced
CONF_CHARGER_DISTRIBUTION: Final = "charger_distribution"    # priority | equal | roundrobin

# Notifications
CONF_NOTIFY_TARGETS: Final = "notify_targets"
CONF_NOTIFY_ON_CHARGE_COMPLETE: Final = "notify_on_charge_complete"
CONF_NOTIFY_ON_OVERCONSUMPTION: Final = "notify_on_overconsumption"
CONF_NOTIFY_ON_MODE_CHANGE: Final = "notify_on_mode_change"

# ---------------------------------------------------------------------------
# Default values
# ---------------------------------------------------------------------------
DEFAULT_EV_VOLTAGE: Final = 230
DEFAULT_EV_PHASES: Final = 1
DEFAULT_EV_MIN_CURRENT: Final = 6
DEFAULT_EV_MAX_CURRENT: Final = 16
DEFAULT_BATTERY_MIN_SOC: Final = 20
DEFAULT_BATTERY_TARGET_SOC: Final = 90
DEFAULT_BATTERY_MAX_CHARGE_W: Final = 3000
DEFAULT_HYSTERESIS_W: Final = 150
DEFAULT_MIN_PV_SURPLUS_W: Final = 300
DEFAULT_OVERCONSUMPTION_W: Final = 6000
DEFAULT_MAX_HOUSEHOLD_POWER_W: Final = 0  # 0 = no cap
DEFAULT_MAX_HOUSEHOLD_TOLERANCE_PCT: Final = 10
DEFAULT_FAST_GRID_BUDGET_W: Final = 3000  # +3 kW from grid in FAST mode
DEFAULT_BATTERY_FAST_SOC: Final = 98      # battery must hit 98% before EV gets PV
DEFAULT_UPDATE_INTERVAL: Final = 10  # seconds
DEFAULT_CHARGER_DISTRIBUTION: Final = "priority"

# ---------------------------------------------------------------------------
# Priority / operating modes
# ---------------------------------------------------------------------------
MODE_OFF: Final = "off"
MODE_ECO: Final = "eco"
MODE_BALANCED: Final = "balanced"
MODE_FAST: Final = "fast"
# Battery-first: PV is reserved for the home battery; the EV charger only
# receives PV once the battery reaches `battery_fast_soc`. Internally the
# id is `boost_battery` for backward compat with existing config entries.
MODE_BATTERY_FAST: Final = "boost_battery"
# Manual: the integration stops driving the chargers; the user can change
# their set_current/set_power/switch entities by hand. Switching out of
# manual reapplies the new mode immediately (no hysteresis hold).
MODE_MANUAL: Final = "manual"

# Legacy alias kept for backward compatibility (selectable via the service
# `solar_charge.set_mode` and existing automations) but hidden from cards.
MODE_BOOST_CAR: Final = "boost_car"

# Legacy name preserved for callers that import `MODE_BOOST_BATTERY`
# (switch.py, services). The selected behaviour is the new "Battery Fast".
MODE_BOOST_BATTERY: Final = MODE_BATTERY_FAST

MODES: Final = [
    MODE_OFF,
    MODE_ECO,
    MODE_BALANCED,
    MODE_FAST,
    MODE_BATTERY_FAST,
    MODE_MANUAL,
    # Legacy values still accepted by the select entity
    MODE_BOOST_CAR,
]

DISTRIBUTIONS: Final = ["priority", "equal", "roundrobin"]

# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------
SERVICE_SET_MODE: Final = "set_mode"
SERVICE_BOOST_CAR: Final = "boost_car"
SERVICE_BOOST_BATTERY: Final = "boost_battery"
SERVICE_RESET: Final = "reset"

SIGNAL_UPDATE: Final = f"{DOMAIN}_update"

# ---------------------------------------------------------------------------
# Attributes
# ---------------------------------------------------------------------------
ATTR_PV_POWER: Final = "pv_power"
ATTR_HOUSE_POWER: Final = "house_power"
ATTR_GRID_POWER: Final = "grid_power"
ATTR_BATTERY_POWER: Final = "battery_power"
ATTR_BATTERY_SOC: Final = "battery_soc"
ATTR_EV_POWER_TOTAL: Final = "ev_power_total"
ATTR_SURPLUS: Final = "surplus"
ATTR_RECOMMENDED_EV_POWER_TOTAL: Final = "recommended_ev_power_total"
ATTR_BATTERY_ALLOCATION: Final = "battery_allocation"
ATTR_MODE: Final = "mode"
ATTR_CHARGERS: Final = "chargers"
