"""Constants for the Solar Charge Balancer integration."""
from __future__ import annotations

from typing import Final

DOMAIN: Final = "solar_charge"
PLATFORMS: Final = ["sensor", "number", "switch", "select", "binary_sensor"]

# ---------------------------------------------------------------------------
# Configuration schema version (bump together with async_migrate_entry)
# ---------------------------------------------------------------------------
CONFIG_VERSION: Final = 2

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

# Home battery
CONF_BATTERY_POWER_ENTITY: Final = "battery_power_entity"
CONF_BATTERY_SOC_ENTITY: Final = "battery_soc_entity"
CONF_BATTERY_CHARGE_POSITIVE: Final = "battery_charge_positive"
CONF_BATTERY_CAPACITY_KWH: Final = "battery_capacity_kwh"
CONF_BATTERY_MIN_SOC: Final = "battery_min_soc"
CONF_BATTERY_TARGET_SOC: Final = "battery_target_soc"
CONF_BATTERY_MAX_CHARGE_W: Final = "battery_max_charge_w"

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
DEFAULT_UPDATE_INTERVAL: Final = 10  # seconds
DEFAULT_CHARGER_DISTRIBUTION: Final = "priority"

# ---------------------------------------------------------------------------
# Priority / operating modes
# ---------------------------------------------------------------------------
MODE_ECO: Final = "eco"
MODE_BALANCED: Final = "balanced"
MODE_BOOST_CAR: Final = "boost_car"
MODE_BOOST_BATTERY: Final = "boost_battery"
MODE_FAST: Final = "fast"
MODE_OFF: Final = "off"

MODES: Final = [MODE_ECO, MODE_BALANCED, MODE_BOOST_CAR, MODE_BOOST_BATTERY, MODE_FAST, MODE_OFF]

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
