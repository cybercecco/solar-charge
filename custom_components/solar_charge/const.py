"""Constants for the Solar Charge Balancer integration."""
from __future__ import annotations

from typing import Final

DOMAIN: Final = "solar_charge"
PLATFORMS: Final = ["sensor", "number", "switch", "select", "binary_sensor"]

# ---------------------------------------------------------------------------
# Config flow keys
# ---------------------------------------------------------------------------
# Step: PV production
CONF_PV_POWER_ENTITIES: Final = "pv_power_entities"          # list[str] W
CONF_PV_ENERGY_ENTITIES: Final = "pv_energy_entities"        # optional list[str] Wh/kWh
# Step: House consumption
CONF_HOUSE_POWER_ENTITY: Final = "house_power_entity"        # str W (active load)
CONF_GRID_POWER_ENTITY: Final = "grid_power_entity"          # str W (import + / export -)
CONF_GRID_IS_EXPORT_NEGATIVE: Final = "grid_export_negative" # bool
# Step: Home battery
CONF_BATTERY_POWER_ENTITY: Final = "battery_power_entity"    # str W (charge + / discharge -)
CONF_BATTERY_SOC_ENTITY: Final = "battery_soc_entity"        # str %
CONF_BATTERY_CHARGE_POSITIVE: Final = "battery_charge_positive"  # bool
CONF_BATTERY_CAPACITY_KWH: Final = "battery_capacity_kwh"    # float
CONF_BATTERY_MIN_SOC: Final = "battery_min_soc"              # int %
CONF_BATTERY_TARGET_SOC: Final = "battery_target_soc"        # int %
CONF_BATTERY_MAX_CHARGE_W: Final = "battery_max_charge_w"    # int W
# Step: EV wallbox
CONF_EV_CHARGER_POWER_ENTITY: Final = "ev_charger_power_entity"  # str W (current draw)
CONF_EV_CHARGER_STATUS_ENTITY: Final = "ev_charger_status_entity"  # str
CONF_EV_SET_CURRENT_ENTITY: Final = "ev_set_current_entity"  # number entity A
CONF_EV_SET_POWER_ENTITY: Final = "ev_set_power_entity"      # optional number entity W
CONF_EV_PHASES: Final = "ev_phases"                          # 1 or 3
CONF_EV_VOLTAGE: Final = "ev_voltage"                        # V (230)
CONF_EV_MIN_CURRENT: Final = "ev_min_current"                # A (6)
CONF_EV_MAX_CURRENT: Final = "ev_max_current"                # A (16/32)
CONF_EV_SWITCH_ENTITY: Final = "ev_switch_entity"            # optional switch to enable/disable charge
# Step: Behaviour / thresholds
CONF_OVERCONSUMPTION_THRESHOLD_W: Final = "overconsumption_threshold_w"
CONF_MIN_PV_SURPLUS_W: Final = "min_pv_surplus_w"
CONF_HYSTERESIS_W: Final = "hysteresis_w"
CONF_UPDATE_INTERVAL: Final = "update_interval"
CONF_DEFAULT_PRIORITY: Final = "default_priority"            # car | battery | balanced
# Step: Notifications
CONF_NOTIFY_TARGETS: Final = "notify_targets"                # list[str] notify service names
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

# ---------------------------------------------------------------------------
# Priority / operating modes
# ---------------------------------------------------------------------------
MODE_ECO: Final = "eco"                      # only PV surplus -> EV
MODE_BALANCED: Final = "balanced"            # split between battery and EV
MODE_BOOST_CAR: Final = "boost_car"          # EV first, battery second
MODE_BOOST_BATTERY: Final = "boost_battery"  # battery first, EV second
MODE_FAST: Final = "fast"                    # charge EV at max regardless of PV
MODE_OFF: Final = "off"                      # do not control EV

MODES: Final = [MODE_ECO, MODE_BALANCED, MODE_BOOST_CAR, MODE_BOOST_BATTERY, MODE_FAST, MODE_OFF]

# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------
SERVICE_SET_MODE: Final = "set_mode"
SERVICE_BOOST_CAR: Final = "boost_car"
SERVICE_BOOST_BATTERY: Final = "boost_battery"
SERVICE_RESET: Final = "reset"

# ---------------------------------------------------------------------------
# Dispatcher / signals
# ---------------------------------------------------------------------------
SIGNAL_UPDATE: Final = f"{DOMAIN}_update"

# ---------------------------------------------------------------------------
# Attributes / state keys
# ---------------------------------------------------------------------------
ATTR_PV_POWER: Final = "pv_power"
ATTR_HOUSE_POWER: Final = "house_power"
ATTR_GRID_POWER: Final = "grid_power"
ATTR_BATTERY_POWER: Final = "battery_power"
ATTR_BATTERY_SOC: Final = "battery_soc"
ATTR_EV_POWER: Final = "ev_power"
ATTR_SURPLUS: Final = "surplus"
ATTR_RECOMMENDED_EV_POWER: Final = "recommended_ev_power"
ATTR_RECOMMENDED_EV_CURRENT: Final = "recommended_ev_current"
ATTR_BATTERY_ALLOCATION: Final = "battery_allocation"
ATTR_MODE: Final = "mode"
