"""Solar-system presets for auto-detection of common sensor entities.

A preset is a bundle of regular expressions matched against the entity
registry (or the live state machine) to propose a ready-to-use
configuration for a specific brand / integration.

Design principles:
- presets are *best-effort*: matches are used to prefill the options form,
  the user can always tweak them or add/remove entities manually.
- we never override an already-configured field unless the user asks for it
  explicitly (the preset wizard has a dedicated 'apply' button).
- each preset lists multiple patterns per field to cover slightly different
  naming conventions across integration versions and user customisations.

Currently supported systems:
- Huawei (huawei_solar custom component): SUN2000 inverters + LUNA 2000.
- SolarEdge (solaredge integration).
- Fronius (fronius integration / Gen24, Symo, Primo).
- SMA (sma, sbfspot): Sunny Boy / Tripower + Sunny Boy Storage.
- Enphase Envoy (enphase_envoy): IQ8 + Encharge.
- Tesla Powerwall (powerwall integration, gen 2/3).
- Generic: fallback, no auto-match.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


@dataclass(frozen=True)
class Preset:
    """Descriptor for a solar/battery system.

    Each list is a sequence of regular expressions that match **entity_id**
    strings (case-insensitive). Order matters: the first matching pattern is
    considered the strongest candidate.
    """

    id: str
    label: str
    # Matching patterns (case-insensitive, full match via re.search)
    pv_power_patterns: tuple[str, ...] = ()
    house_power_patterns: tuple[str, ...] = ()
    grid_power_patterns: tuple[str, ...] = ()
    battery_power_patterns: tuple[str, ...] = ()
    battery_soc_patterns: tuple[str, ...] = ()
    charger_power_patterns: tuple[str, ...] = ()
    charger_set_current_patterns: tuple[str, ...] = ()
    charger_set_power_patterns: tuple[str, ...] = ()
    charger_switch_patterns: tuple[str, ...] = ()
    # Conventions used by the integration (can always be flipped in the form)
    grid_export_negative: bool = True
    battery_charge_positive: bool = True
    default_battery_capacity_kwh: float = 0.0
    battery_default_name: str = "Batteria"
    notes: str = ""


# ---------------------------------------------------------------------------
# Preset catalogue
# ---------------------------------------------------------------------------
PRESETS: tuple[Preset, ...] = (
    Preset(
        id="huawei",
        label="Huawei SUN2000 + LUNA 2000",
        pv_power_patterns=(
            r"^sensor\..*inverter.*input_power$",
            r"^sensor\..*inverter.*_pv_power$",
            r"^sensor\..*sun2000.*input_power$",
        ),
        # huawei_solar exposes a computed "house_consumption" sensor.
        house_power_patterns=(
            r"^sensor\..*house_consumption$",
            r"^sensor\..*load_power$",
        ),
        grid_power_patterns=(
            r"^sensor\..*power_meter_active_power$",
            r"^sensor\..*grid_exported_power$",
            r"^sensor\..*meter_active_power$",
        ),
        battery_power_patterns=(
            r"^sensor\..*battery.*charge_discharge_power$",
            r"^sensor\..*luna.*charge_discharge_power$",
            r"^sensor\..*battery_power$",
        ),
        battery_soc_patterns=(
            r"^sensor\..*battery.*state_of_capacity$",
            r"^sensor\..*battery.*soc$",
        ),
        grid_export_negative=True,
        battery_charge_positive=True,
        default_battery_capacity_kwh=10.0,
        battery_default_name="LUNA 2000",
        notes=(
            "Integrazione consigliata: huawei_solar (HACS). "
            "LUNA 2000: ogni modulo = 5 kWh utili; 2 moduli = 10 kWh totali."
        ),
    ),
    Preset(
        id="solaredge",
        label="SolarEdge (inverter + StorEdge)",
        pv_power_patterns=(
            r"^sensor\.solaredge_current_power$",
            r"^sensor\.solaredge_ac_power$",
            r"^sensor\..*solaredge.*_current_power$",
        ),
        house_power_patterns=(
            r"^sensor\.solaredge_power_consumption$",
            r"^sensor\..*solaredge.*consumption$",
        ),
        grid_power_patterns=(
            r"^sensor\.solaredge_power_to_grid$",
            r"^sensor\..*solaredge.*meter.*power$",
        ),
        battery_power_patterns=(
            r"^sensor\.solaredge_storage_power$",
            r"^sensor\..*solaredge.*battery.*power$",
        ),
        battery_soc_patterns=(
            r"^sensor\.solaredge_storage_level$",
            r"^sensor\..*solaredge.*battery.*level$",
        ),
        grid_export_negative=False,
        battery_charge_positive=False,
        default_battery_capacity_kwh=9.7,
        battery_default_name="StorEdge",
    ),
    Preset(
        id="fronius",
        label="Fronius (GEN24 / Symo + BYD / LG)",
        pv_power_patterns=(
            r"^sensor\.fronius_.*_pv_power$",
            r"^sensor\.fronius_.*photovoltaics$",
            r"^sensor\.fronius_.*power_photovoltaics$",
        ),
        house_power_patterns=(
            r"^sensor\.fronius_.*power_load$",
            r"^sensor\.fronius_.*_load$",
        ),
        grid_power_patterns=(
            r"^sensor\.fronius_.*power_grid$",
            r"^sensor\.fronius_.*meter_active_power$",
        ),
        battery_power_patterns=(
            r"^sensor\.fronius_.*power_battery$",
            r"^sensor\.fronius_.*battery_power$",
        ),
        battery_soc_patterns=(
            r"^sensor\.fronius_.*state_of_charge$",
            r"^sensor\.fronius_.*battery_soc$",
        ),
        grid_export_negative=True,
        battery_charge_positive=False,
        default_battery_capacity_kwh=10.0,
        battery_default_name="Batteria Fronius",
    ),
    Preset(
        id="sma",
        label="SMA Sunny Boy/Tripower (+ Storage)",
        pv_power_patterns=(
            r"^sensor\..*sma.*pv_power$",
            r"^sensor\..*sma.*_power_ac_total$",
            r"^sensor\..*sunny.*power$",
        ),
        house_power_patterns=(
            r"^sensor\..*sma.*grid_power_total_consumed$",
            r"^sensor\..*sma.*house_consumption$",
        ),
        grid_power_patterns=(
            r"^sensor\..*sma.*metering_power_absorbed$",
            r"^sensor\..*sma.*grid_feed_in_power$",
        ),
        battery_power_patterns=(
            r"^sensor\..*sma.*battery_power$",
            r"^sensor\..*sunny.*storage.*power$",
        ),
        battery_soc_patterns=(
            r"^sensor\..*sma.*battery_soc$",
            r"^sensor\..*sunny.*storage.*soc$",
        ),
        grid_export_negative=True,
        battery_charge_positive=True,
        default_battery_capacity_kwh=7.7,
        battery_default_name="SMA Storage",
    ),
    Preset(
        id="enphase",
        label="Enphase Envoy + Encharge (IQ Battery)",
        pv_power_patterns=(
            r"^sensor\.envoy_.*_current_power_production$",
            r"^sensor\..*envoy.*production$",
        ),
        house_power_patterns=(
            r"^sensor\.envoy_.*_current_power_consumption$",
            r"^sensor\..*envoy.*consumption$",
        ),
        grid_power_patterns=(
            r"^sensor\.envoy_.*_grid_power$",
            r"^sensor\..*envoy.*_net_power_consumption$",
        ),
        battery_power_patterns=(
            r"^sensor\.envoy_.*_battery_power$",
            r"^sensor\..*encharge.*power$",
        ),
        battery_soc_patterns=(
            r"^sensor\.envoy_.*_battery_soc$",
            r"^sensor\..*encharge.*_soc$",
            r"^sensor\..*encharge.*_state_of_charge$",
        ),
        grid_export_negative=True,
        battery_charge_positive=True,
        default_battery_capacity_kwh=10.5,
        battery_default_name="Encharge",
    ),
    Preset(
        id="powerwall",
        label="Tesla Powerwall (gen 2/3)",
        pv_power_patterns=(
            r"^sensor\.powerwall_solar_now$",
            r"^sensor\..*powerwall.*solar_power$",
        ),
        house_power_patterns=(
            r"^sensor\.powerwall_load_now$",
            r"^sensor\..*powerwall.*load_power$",
        ),
        grid_power_patterns=(
            r"^sensor\.powerwall_site_now$",
            r"^sensor\..*powerwall.*grid_power$",
        ),
        battery_power_patterns=(
            r"^sensor\.powerwall_battery_now$",
            r"^sensor\..*powerwall.*battery_power$",
        ),
        battery_soc_patterns=(
            r"^sensor\.powerwall_charge$",
            r"^sensor\..*powerwall.*battery_level$",
        ),
        grid_export_negative=True,
        battery_charge_positive=False,
        default_battery_capacity_kwh=13.5,
        battery_default_name="Powerwall",
    ),
    Preset(
        id="generic",
        label="Generico / configurazione manuale",
        notes=(
            "Nessun auto-rilevamento: configura i campi a mano nelle sezioni "
            "dedicate (produzione, consumi, batterie, colonnine)."
        ),
    ),
)


PRESET_BY_ID: dict[str, Preset] = {p.id: p for p in PRESETS}


# ---------------------------------------------------------------------------
# Matching helpers
# ---------------------------------------------------------------------------
@dataclass
class PresetMatch:
    """Result of matching a preset against the running Home Assistant."""

    preset: Preset
    pv_power: list[str] = field(default_factory=list)
    house_power: str | None = None
    grid_power: str | None = None
    battery_power: str | None = None
    battery_soc: str | None = None

    @property
    def has_any_match(self) -> bool:
        return any(
            [
                self.pv_power,
                self.house_power,
                self.grid_power,
                self.battery_power,
                self.battery_soc,
            ]
        )


def _first_match(entity_ids: list[str], patterns: tuple[str, ...]) -> str | None:
    for pat in patterns:
        regex = re.compile(pat, re.IGNORECASE)
        for eid in entity_ids:
            if regex.search(eid):
                return eid
    return None


def _all_matches(entity_ids: list[str], patterns: tuple[str, ...]) -> list[str]:
    """Return every entity matching *any* of the patterns, preserving order."""
    seen: set[str] = set()
    result: list[str] = []
    for pat in patterns:
        regex = re.compile(pat, re.IGNORECASE)
        for eid in entity_ids:
            if regex.search(eid) and eid not in seen:
                seen.add(eid)
                result.append(eid)
    return result


def match_preset(hass: "HomeAssistant", preset: Preset) -> PresetMatch:
    """Scan HA state machine and collect entity_ids matching the preset.

    We look at *sensor* domain only, since every field we care about is a
    numeric reading. PV is multi-match (common to have several inverters
    or strings), the others pick the first/best candidate.
    """
    entity_ids = sorted(
        eid for eid in hass.states.async_entity_ids("sensor")
    )
    return PresetMatch(
        preset=preset,
        pv_power=_all_matches(entity_ids, preset.pv_power_patterns),
        house_power=_first_match(entity_ids, preset.house_power_patterns),
        grid_power=_first_match(entity_ids, preset.grid_power_patterns),
        battery_power=_first_match(entity_ids, preset.battery_power_patterns),
        battery_soc=_first_match(entity_ids, preset.battery_soc_patterns),
    )


# ---------------------------------------------------------------------------
# Auto-detect: pick the best preset across all known systems
# ---------------------------------------------------------------------------
def _score_match(m: PresetMatch) -> int:
    """Heuristic score of how well a preset fits the current HA.

    Brand-specific fields (PV and battery) weigh more because their naming
    conventions are the most distinctive. House/grid readings are common
    to many integrations and are worth less per match.
    """
    score = 0
    if m.pv_power:
        score += 3 + min(len(m.pv_power) - 1, 3)  # multi-inverter bonus, capped
    if m.battery_power:
        score += 3
    if m.battery_soc:
        score += 3
    if m.house_power:
        score += 1
    if m.grid_power:
        score += 1
    return score


@dataclass
class AutoDetectResult:
    match: PresetMatch
    score: int
    ranking: list[tuple[str, int]]  # list of (preset_id, score) sorted desc


def auto_detect(hass: "HomeAssistant") -> AutoDetectResult | None:
    """Run every preset against HA and return the best scoring one.

    Returns None if no preset matches anything (i.e. the user has no
    supported inverter integration installed). The 'generic' preset is
    always skipped because it matches nothing by definition.
    """
    ranked: list[tuple[PresetMatch, int]] = []
    for preset in PRESETS:
        if preset.id == "generic":
            continue
        m = match_preset(hass, preset)
        score = _score_match(m)
        if score > 0:
            ranked.append((m, score))

    if not ranked:
        return None

    ranked.sort(key=lambda p: p[1], reverse=True)
    best_match, best_score = ranked[0]
    return AutoDetectResult(
        match=best_match,
        score=best_score,
        ranking=[(m.preset.id, s) for m, s in ranked],
    )
