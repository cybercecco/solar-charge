/*!
 * Solar Charge Card — Lovelace custom card
 *
 * Graph-style visualisation inspired by Home Assistant's energy
 * dashboard: circular colored nodes connected to a central Home hub by
 * curved SVG lines with animated flow particles.
 *
 * Written in plain JS (no Lit / no CDN imports) for maximum reliability:
 * the script self-registers `solar-charge-card` and pushes an entry into
 * `window.customCards` the moment it loads.
 */

const CARD_VERSION = "0.12.12";

/** Escape text for safe interpolation into HTML bodies. */
function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/** Escape for double-quoted HTML attributes. */
function escapeAttr(value) {
  return escapeHtml(value).replace(/`/g, "&#96;");
}

// eslint-disable-next-line no-console
console.info(
  `%c SOLAR-CHARGE-CARD %c v${CARD_VERSION} `,
  "color:white;background:#1f6feb;font-weight:700;padding:2px 6px;border-radius:3px 0 0 3px;",
  "color:#1f6feb;background:#0d1117;padding:2px 6px;border-radius:0 3px 3px 0;"
);

// ---------------------------------------------------------------------------
// Push into the card picker immediately. Doing this BEFORE any class
// definitions means the picker will always list us, even if something later
// in the script were to fail. We still guard against duplicate pushes
// because the script may be loaded both via add_extra_js_url and as a
// Lovelace resource.
// ---------------------------------------------------------------------------
window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === "solar-charge-card")) {
  window.customCards.push({
    type: "solar-charge-card",
    name: "Solar Charge Card",
    description:
      "Tesla-like energy flow graph for the Solar Charge Balancer integration.",
    preview: true,
    documentationURL: "https://github.com/cybercecco/solar-charge",
  });
}
if (!window.customCards.some((c) => c.type === "solar-charge-mode-card")) {
  window.customCards.push({
    type: "solar-charge-mode-card",
    name: "Solar Charge Mode Selector",
    description:
      "Compact button strip to pick the Solar Charge operating mode (off/eco/balanced/boost_car/boost_battery/fast).",
    preview: true,
    documentationURL: "https://github.com/cybercecco/solar-charge",
  });
}

// ---------------------------------------------------------------------------
// Utility helpers
// ---------------------------------------------------------------------------
const NODE_COLORS = {
  solar: "#FFB300",
  grid: "#42A5F5",
  battery: "#EC407A",
  home: "#66BB6A",
  charger: "#26C6DA",
  muted: "#5a5a5a",
};

const ICONS = {
  solar:
    "M12 4V2m0 20v-2M4 12H2m20 0h-2M5.64 5.64L4.22 4.22m15.56 15.56l-1.42-1.42M5.64 18.36l-1.42 1.42M19.78 4.22l-1.42 1.42M12 6a6 6 0 100 12 6 6 0 000-12z",
  grid: "M6 2v4h4V2h4v4h4v4h-4v4h4v4h-4v-4h-4v4H6v-4H2v-4h4v-4H2V6h4V2h0z",
  battery:
    "M8 4h8v2h2v16H6V6h2V4zm1 3v13h6V7H9z",
  home: "M12 3l9 8h-3v10h-5v-6H11v6H6V11H3l9-8z",
  charger:
    "M14 7V4H5v18h9v-3h1a3 3 0 003-3V10a3 3 0 00-3-3h-1zm2 4h1v4h-1v-4z",
};

// Synchronised across both cards (the graph card header and the dedicated
// mode-selector card). Order matches the user-facing flow:
//   Off → Eco → Balanced → Fast → Battery Fast → Manual
// `value` MUST match the option exposed by `select.solar_charge_balancing_mode`
// in the integration. `boost_battery` is the on-disk id of the "Battery Fast"
// mode (kept for backward compatibility); `manual` is a soft state that tells
// the EV controller to step back and let the user drive the chargers.
//
// Kept at the very top of the file so it is fully initialised before any
// class declaration that references it (no temporal-dead-zone surprises).
const MODE_BUTTONS = [
  {
    value: "off",
    label: "Off",
    color: "#9aa0a6",
    icon: "M13 3h-2v10h2V3zM6.76 5.51l-1.42 1.42A7 7 0 0 0 12 19a7 7 0 0 0 6.66-12.07l-1.42-1.42A5 5 0 1 1 7 7a5 5 0 0 1-.24-1.49z",
  },
  {
    value: "eco",
    label: "Eco",
    color: "#66BB6A",
    icon: "M17 3c-6 0-10 4-10 10 0 3 1 5 2 6l-2 2 1 1 2-2c1 1 3 2 6 2 6 0 10-4 10-10 0-5-4-9-9-9zm-1 4c-3 1-6 3-7 7-1-3 1-6 5-7h2z",
  },
  {
    value: "balanced",
    label: "Bilanciato",
    color: "#42A5F5",
    icon: "M12 3a1 1 0 0 1 1 1v1h5a1 1 0 1 1 0 2h-1.1l2.6 6.2a3 3 0 0 1-5.8 1H13v7h4v2H7v-2h4v-7h-1.7a3 3 0 0 1-5.8-1L6.1 7H5a1 1 0 0 1 0-2h5V4a1 1 0 0 1 1-1zm5 5.4L15.3 13h3.4L17 8.4zM7 8.4L5.3 13h3.4L7 8.4z",
  },
  {
    value: "fast",
    label: "Fast",
    color: "#FFB300",
    icon: "M13 2L4.5 13h6l-1 9 8.5-11h-6l1-9z",
  },
  {
    value: "boost_battery",
    label: "Battery Fast",
    color: "#EC407A",
    icon: "M9 4h6v2h2v16H7V6h2V4zm2 5l-2 5h2v4l3-5h-2l1-4h-2z",
  },
  {
    value: "manual",
    label: "Manuale",
    color: "#B388FF",
    icon: "M9 11V5a1 1 0 0 1 2 0v6h1V3a1 1 0 0 1 2 0v8h1V4a1 1 0 0 1 2 0v9h1V7a1 1 0 0 1 2 0v9a5 5 0 0 1-5 5h-2.2a4 4 0 0 1-3.4-1.9l-3.7-6.2a1 1 0 0 1 1.5-1.3l1.8 1.7V11a1 1 0 1 1 2 0z",
  },
];

const stateObj = (hass, id) => (id && hass ? hass.states[id] : undefined);

const stateNum = (hass, id) => {
  const s = stateObj(hass, id);
  if (!s || ["unknown", "unavailable", ""].includes(s.state)) return 0;
  const n = Number(s.state);
  return Number.isFinite(n) ? n : 0;
};

const stateStr = (hass, id) => {
  const s = stateObj(hass, id);
  return s ? String(s.state) : "";
};

const fmtPower = (w) => {
  if (w === null || w === undefined || isNaN(w)) return "—";
  const a = Math.abs(w);
  if (a >= 1000) return `${(w / 1000).toFixed(a >= 10000 ? 1 : 2)} kW`;
  return `${Math.round(w)} W`;
};

const fmtPercent = (v) => {
  if (v === null || v === undefined || isNaN(v)) return "—";
  return `${Math.round(v)} %`;
};

// ---------------------------------------------------------------------------
// Auto-detect a card configuration from the running Solar Charge integration.
// Walks `hass.entities` for entries with `platform === "solar_charge"`,
// groups them by device, and produces a `{ pv_entity, house_entity, ...,
// chargers: [...], batteries: [...] }` object that mirrors the YAML.
// Used both by `getStubConfig` (when adding the card from the picker) and
// at runtime, so a manually-written YAML stub like `type: custom:solar-charge-card`
// gets fully populated as soon as `hass` lands.
// Returns `null` when no Solar Charge entities can be found.
// ---------------------------------------------------------------------------
function normalizeCardConfig(config) {
  if (config && typeof config === "object" && !Array.isArray(config)) {
    return config;
  }
  return {};
}

function entitiesRegistry(hass) {
  const raw = hass?.entities;
  if (!raw) return {};
  if (raw instanceof Map) return Object.fromEntries(raw);
  return raw;
}

function autoConfigFromHass(hass) {
  try {
    const registry = entitiesRegistry(hass);
    const devices = hass?.devices || {};
    const scEntries = Object.values(registry).filter(
      (e) => e && e.platform === "solar_charge"
    );
    if (!scEntries.length) return null;

    const byDevice = new Map();
    for (const e of scEntries) {
      if (!e.device_id) continue;
      if (!byDevice.has(e.device_id)) byDevice.set(e.device_id, []);
      byDevice.get(e.device_id).push(e);
    }

    const findByKey = (ents, suffix) => {
      const hit = ents.find((e) =>
        (e.unique_id || "").endsWith(`_${suffix}`)
      );
      return hit ? hit.entity_id : undefined;
    };
    const prettyName = (dev, fallbackName) => {
      const raw = dev?.name_by_user || dev?.name || fallbackName || "";
      const parts = raw.split("—");
      return (parts[parts.length - 1] || raw).trim();
    };
    const extractKind = (dev) => {
      const ids = dev?.identifiers || [];
      for (const pair of ids) {
        if (!Array.isArray(pair) || pair[0] !== "solar_charge") continue;
        const raw = String(pair[1] || "");
        const ci = raw.indexOf("_charger_");
        if (ci !== -1) return { kind: "charger", id: raw.slice(ci + 9) };
        const bi = raw.indexOf("_battery_");
        if (bi !== -1) return { kind: "battery", id: raw.slice(bi + 9) };
        return { kind: "main", id: raw };
      }
      return null;
    };

    let mainEnts = null;
    const chargerGroups = [];
    const batteryGroups = [];
    for (const [did, ents] of byDevice) {
      const dev = devices[did];
      const info = extractKind(dev);
      if (!info) continue;
      if (info.kind === "main") mainEnts = ents;
      else if (info.kind === "charger")
        chargerGroups.push({ cid: info.id, dev, ents });
      else if (info.kind === "battery")
        batteryGroups.push({ bid: info.id, dev, ents });
    }

    const cfg = {};
    if (mainEnts) {
      const globalMap = {
        pv_entity: "pv_power",
        house_entity: "house_power",
        grid_entity: "grid_power",
        battery_entity: "battery_power",
        battery_soc_entity: "battery_soc",
        ev_recommended_entity: "recommended_ev_power_total",
        mode_entity: "mode",
        boost_battery_entity: "boost_battery",
      };
      for (const [key, suffix] of Object.entries(globalMap)) {
        const found = findByKey(mainEnts, suffix);
        if (found) cfg[key] = found;
      }
    }
    if (chargerGroups.length) {
      cfg.chargers = chargerGroups
        .map(({ cid, dev, ents }) => {
          const c = {
            name: prettyName(dev, cid),
            power_entity: findByKey(ents, "power"),
            recommended_power_entity: findByKey(ents, "recommended_power"),
          };
          const recCurr = findByKey(ents, "recommended_current");
          if (recCurr) c.recommended_current_entity = recCurr;
          const charging = findByKey(ents, "charging");
          if (charging) c.charging_entity = charging;
          const boost = findByKey(ents, "boost");
          if (boost) c.boost_entity = boost;
          return c;
        })
        .filter((c) => c.power_entity);
    }
    if (batteryGroups.length) {
      cfg.batteries = batteryGroups
        .map(({ bid, dev, ents }) => {
          const b = {
            id: bid,
            name: prettyName(dev, bid),
            power_entity: findByKey(ents, "power"),
          };
          const soc = findByKey(ents, "soc");
          if (soc) b.soc_entity = soc;
          return b;
        })
        .filter((b) => b.power_entity);
    }

    if (!mainEnts && !(cfg.chargers || []).length && !(cfg.batteries || []).length) {
      return null;
    }
    return cfg;
  } catch (err) {
    // eslint-disable-next-line no-console
    console.warn("[solar-charge-card] autoConfigFromHass failed:", err);
    return null;
  }
}

// True when `entityId` looks like the integration's balancing-mode select
// (works with renamed ids such as select.solar_charge_balancer_modalita_di_bilanciamento).
function isSolarChargeModeSelect(hass, entityId) {
  if (!entityId || !hass?.states?.[entityId]) return false;
  const st = hass.states[entityId];
  if (!entityId.startsWith("select.")) return false;
  const ent = entitiesRegistry(hass)[entityId];
  if (ent?.platform === "solar_charge") {
    const uid = ent.unique_id || "";
    if (uid.endsWith("_mode")) return true;
  }
  const opts = st.attributes?.options;
  if (!Array.isArray(opts) || !opts.length) return false;
  return (
    opts.includes("eco") &&
    (opts.includes("balanced") || opts.includes("off")) &&
    (opts.includes("fast") || opts.includes("manual") || opts.includes("boost_battery"))
  );
}

// Resolve the mode `select.*` entity: explicit YAML → registry → heuristic scan.
function resolveModeSelectEntity(hass, preferred) {
  if (!hass) return null;
  const states = hass.states || {};
  if (preferred && states[preferred] && isSolarChargeModeSelect(hass, preferred)) {
    return preferred;
  }
  const detected = autoConfigFromHass(hass);
  if (
    detected?.mode_entity &&
    states[detected.mode_entity] &&
    isSolarChargeModeSelect(hass, detected.mode_entity)
  ) {
    return detected.mode_entity;
  }
  const registry = entitiesRegistry(hass);
  const regHit = Object.values(registry).find(
    (e) =>
      e?.platform === "solar_charge" && (e.unique_id || "").endsWith("_mode")
  );
  if (regHit?.entity_id && states[regHit.entity_id]) {
    return regHit.entity_id;
  }
  return (
    Object.keys(states).find((id) => isSolarChargeModeSelect(hass, id)) || null
  );
}

function configEntryForEntity(hass, entityId) {
  return entitiesRegistry(hass)[entityId]?.config_entry || null;
}

function currentModeFromEntity(hass, entityId) {
  const st = stateObj(hass, entityId);
  if (!st) return "";
  const raw = String(st.state ?? "");
  if (raw === "unknown" || raw === "unavailable") return "";
  const fromAttr = st.attributes?.current_option;
  if (fromAttr && fromAttr !== "unknown" && fromAttr !== "unavailable") {
    return String(fromAttr);
  }
  return raw;
}

function selectOptionsForEntity(hass, entityId) {
  const st = stateObj(hass, entityId);
  const opts = st?.attributes?.options;
  return Array.isArray(opts) ? opts : null;
}

async function applyBalancingMode(hass, entityId, value) {
  if (entityId) {
    try {
      await hass.callService("select", "select_option", {
        entity_id: entityId,
        option: value,
      });
      return `select.select_option(${entityId}, ${value})`;
    } catch (err) {
      // eslint-disable-next-line no-console
      console.warn(
        "[solar-charge-card] select.select_option failed, falling back to solar_charge.set_mode:",
        err
      );
    }
  }
  const data = { mode: value };
  const entryId = entityId ? configEntryForEntity(hass, entityId) : null;
  if (entryId) data.entry_id = entryId;
  await hass.callService("solar_charge", "set_mode", data);
  return entryId
    ? `solar_charge.set_mode(${value}, entry_id=${entryId})`
    : `solar_charge.set_mode(${value})`;
}

// Build a smooth cubic-bezier path between two points. Control points are
// offset along the dominant axis to produce an elegant S-curve.
const curvePath = (x1, y1, x2, y2) => {
  const dx = x2 - x1;
  const dy = y2 - y1;
  const absDx = Math.abs(dx);
  const absDy = Math.abs(dy);
  // Dominant axis determines curve bias
  if (absDx >= absDy) {
    const mx = (x1 + x2) / 2;
    return `M ${x1} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}`;
  }
  const my = (y1 + y2) / 2;
  return `M ${x1} ${y1} C ${x1} ${my}, ${x2} ${my}, ${x2} ${y2}`;
};

// ---------------------------------------------------------------------------
// Main card
// ---------------------------------------------------------------------------
class SolarChargeCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._mounted = false;
    this._config = null;
    this._hass = null;
    this._resizeObserver = null;
    // Physics simulation state. Map key → NodeState:
    //   { key, el, kind, pinned, dragging, r, pos:{x,y}, vel:{x,y}, rest:{x,y}, initialized }
    this._sim = {
      nodes: new Map(),
      raf: 0,
      running: false,
      idleFrames: 0,
      last: 0,
    };
    this._onResize = () => {
      if (this._animationsEnabled()) {
        this._recomputeRestPositions(true);
        this._applyAnimationGate();
      } else {
        this._applyStaticLayout(true);
      }
    };
    // Visibility tracking: pause every recurring animation (physics loop
    // AND the SVG `<animateMotion>` particles) whenever the card is not
    // actually on screen — out of viewport, in a hidden dashboard tab,
    // or with the browser tab in background. Critical on low-power
    // tablets where leaving multiple SolarCharge cards animating in the
    // background causes frame drops on neighbouring gauge cards.
    this._intersecting = true;
    this._pageVisible = !document.hidden;
    this._intersectionObserver = null;
    this._onVisibilityChange = () => {
      this._pageVisible = !document.hidden;
      this._applyAnimationGate();
    };
  }

  // ------------------------------------------------------------------
  // Lovelace card API
  // ------------------------------------------------------------------
  static getConfigElement() {
    return document.createElement("solar-charge-card-editor");
  }

  // Auto-fill the card config from the running Solar Charge integration.
  // Home Assistant calls this with (hass, entities, entitiesFallback) when
  // the user adds the card. We walk hass.entities for platform=solar_charge,
  // group by their device (via hass.devices identifiers) and build:
  //   - main hub sensors (pv, house, grid, battery*, ev_recommended, mode, boost)
  //   - chargers[] (one object per wallbox sub-device)
  //   - batteries[] (one object per battery sub-device)
  // Anything missing falls back to the previous hardcoded defaults, so the
  // card still works if the lookup fails.
  static async getStubConfig(hass /*, entities, entitiesFallback */) {
    const fallback = {
      title: "Solar Charge",
      pv_entity: "sensor.solar_charge_pv_power",
      house_entity: "sensor.solar_charge_house_power",
      grid_entity: "sensor.solar_charge_grid_power",
      battery_entity: "sensor.solar_charge_battery_power",
      battery_soc_entity: "sensor.solar_charge_battery_soc",
      ev_recommended_entity: "sensor.solar_charge_recommended_ev_power_total",
      mode_entity: "select.solar_charge_balancing_mode",
      boost_battery_entity: "switch.solar_charge_boost_battery",
      chargers: [],
    };
    try {
      const detected = autoConfigFromHass(hass);
      if (!detected) return fallback;
      return { title: "Solar Charge", ...detected };
    } catch (err) {
      // eslint-disable-next-line no-console
      console.warn("[solar-charge-card] getStubConfig failed:", err);
      return fallback;
    }
  }

  // Merge any auto-detected entities into the user-supplied config without
  // overwriting fields the user explicitly set. Returns true when at least
  // one new field landed (so the caller knows it should re-render).
  // This is what lets a minimal YAML stub like
  //   type: custom:solar-charge-card
  // turn into a fully populated card the moment hass arrives, mirroring
  // whatever the integration is exposing under Devices & Services.
  //
  // Note on retry: we only mark `_enriched = true` when we actually saw
  // a Solar Charge entity in the registry. If the integration entry has
  // not finished setting up (startup race) we leave the flag false so
  // every subsequent hass tick has another shot at populating the card.
  // Throttled to at most once per ENRICH_RETRY_MS to avoid spinning the
  // CPU on registries with thousands of entities.
  _enrichConfigFromHass() {
    if (!this._hass || !this._config || this._enriched) return false;
    const ENRICH_RETRY_MS = 2000;
    const now = Date.now();
    if (this._enrichLastTry && now - this._enrichLastTry < ENRICH_RETRY_MS) {
      return false;
    }
    this._enrichLastTry = now;

    const detected = autoConfigFromHass(this._hass);
    if (!detected) {
      // Integration entities not yet registered. Do NOT mark as
      // enriched: try again on the next state change.
      return false;
    }
    const target = { ...this._config };
    let changed = false;

    const SCALAR_KEYS = [
      "pv_entity",
      "house_entity",
      "grid_entity",
      "battery_entity",
      "battery_soc_entity",
      "ev_entity",
      "ev_recommended_entity",
      "mode_entity",
      "boost_battery_entity",
    ];
    for (const k of SCALAR_KEYS) {
      if (!target[k] && detected[k]) {
        target[k] = detected[k];
        changed = true;
      }
    }
    if (
      Array.isArray(detected.chargers) &&
      detected.chargers.length &&
      !(Array.isArray(target.chargers) && target.chargers.length)
    ) {
      target.chargers = detected.chargers;
      changed = true;
    }
    if (
      Array.isArray(detected.batteries) &&
      detected.batteries.length &&
      !(Array.isArray(target.batteries) && target.batteries.length)
    ) {
      target.batteries = detected.batteries;
      changed = true;
    }
    // We only stop retrying once we actually found Solar Charge entities
    // (detected !== null). A subsequent setConfig (user edited YAML)
    // clears this flag.
    const resolvedMode = resolveModeSelectEntity(this._hass, target.mode_entity);
    if (resolvedMode && target.mode_entity !== resolvedMode) {
      target.mode_entity = resolvedMode;
      changed = true;
    }
    this._enriched = true;
    if (changed) {
      this._config = target;
      // eslint-disable-next-line no-console
      console.info(
        "[solar-charge-card] auto-enriched config from running integration"
      );
    }
    return changed;
  }

  getCardSize() {
    return 6;
  }

  getGridOptions() {
    return {
      columns: 6,
      rows: 6,
      min_columns: 3,
      min_rows: 4,
    };
  }

  setConfig(config) {
    try {
      this._config = { ...normalizeCardConfig(config) };
      this._mounted = false;
      // Re-enable runtime enrichment: the user edited the YAML, give us a
      // fresh chance to fill in the gaps from the integration registry.
      this._enriched = false;
      // If hass is already available, top up the config with any entity
      // the user did not specify before doing the first paint.
      if (this._hass) this._enrichConfigFromHass();
      // Render even when hass is not yet available: the dashboard card
      // picker may call setConfig BEFORE handing us the hass object, and
      // an empty shadow root would make the tile look stuck on loading.
      // The graph will repopulate as soon as `set hass` arrives.
      this._render();
    } catch (err) {
      // Never let setConfig throw up to Lovelace — HA 2026+ shows a generic
      // "Configuration error" tile and hides the real message from users.
      // eslint-disable-next-line no-console
      console.error("[solar-charge-card] setConfig failed, using fallback:", err);
      this._config = { ...normalizeCardConfig(config) };
      this._renderFallback(err);
    }
  }

  set hass(hass) {
    this._hass = hass;
    try {
      // First time hass arrives: try to auto-fill any entity the user
      // didn't provide in the YAML. If anything new lands we MUST do a
      // full re-render (descriptors and DOM nodes change), otherwise a
      // simple _update is enough.
      const enriched = this._enrichConfigFromHass();
      if (!this._mounted || enriched) {
        this._render();
      } else {
        // Always run _update when hass changes (including the first
        // assignment after a setConfig-only render). Without this the
        // mode chips would stay un-highlighted until the next live
        // state change rolled in.
        this._update();
      }
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error("[solar-charge-card] update failed, using fallback:", err);
      this._renderFallback(err);
    }
  }

  // Minimal always-renderable fallback so the Lovelace card picker can
  // never get stuck on an unresolved preview, even if the main render
  // path throws for an unexpected reason.
  _renderFallback(err) {
    const msg = err && err.message ? String(err.message) : "";
    this.shadowRoot.innerHTML = `
      <style>
        ha-card { padding: 14px 16px;
                  background: var(--ha-card-background, #1c1f24);
                  color: var(--primary-text-color, #e8e8e8);
                  display: block; }
        .title { font-weight: 600; font-size: 0.95rem; }
        .version { opacity: 0.55; font-size: 0.75rem; margin-top: 4px; }
        .hint { opacity: 0.65; font-size: 0.78rem; margin-top: 8px; line-height: 1.35; }
        pre { margin: 8px 0 0; padding: 6px 8px; border-radius: 4px;
              background: rgba(0,0,0,0.25); font-size: 0.7rem;
              overflow: auto; max-height: 120px; }
      </style>
      <ha-card>
        <div class="title">Solar Charge Card</div>
        <div class="version">v${CARD_VERSION} — modalità compatibile</div>
        <div class="hint">Configura le entità nell'editor o in YAML (pv_entity, grid_entity, battery_entity, ecc.) per abilitare il grafo animato.</div>
        ${msg ? `<pre>${escapeHtml(msg)}</pre>` : ""}
      </ha-card>
    `;
    this._mounted = true;
  }

  connectedCallback() {
    // Re-arm visibility tracking on (re)mount, e.g. when the user
    // switches dashboards and comes back to this one.
    document.addEventListener("visibilitychange", this._onVisibilityChange);
    this._pageVisible = !document.hidden;
    this._observeIntersection();
    // If we were already mounted previously, restart the loops so the
    // graph is alive again. The gate decides if the loop should actually
    // tick or stay parked.
    if (this._mounted) this._applyAnimationGate();
  }

  disconnectedCallback() {
    if (this._resizeObserver) {
      this._resizeObserver.disconnect();
      this._resizeObserver = null;
    }
    if (this._intersectionObserver) {
      this._intersectionObserver.disconnect();
      this._intersectionObserver = null;
    }
    document.removeEventListener("visibilitychange", this._onVisibilityChange);
    window.removeEventListener("resize", this._onResize);
    this._stopSimLoop();
    // Pause the SVG animateMotion clocks too: when this element is
    // re-attached (e.g. dashboard switch) we resume them on demand.
    this._setSvgAnimationsPaused(true);
  }

  // User-facing toggle: `animations: false` keeps balloons at their
  // computed rest positions with static wires (no rAF loop, no flow dots).
  // Omitted or any value other than literal `false` → animations on.
  _animationsEnabled() {
    return this._config?.animations !== false;
  }

  // Place every balloon at its rest anchor and refresh wire paths once.
  // Used on first paint, on resize, and whenever animations are off.
  _applyStaticLayout(preserveDraggedRest = false) {
    this._recomputeRestPositions(preserveDraggedRest);
    this._sim.nodes.forEach((s) => this._positionNode(s));
    if (this._flowState) this._drawConnections();
  }

  // Combined gate: decides whether the rAF physics loop should run AND
  // whether the SVG flow particles should keep ticking. The card is
  // "live" only when it's both inside the viewport and on the active
  // browser tab — and only when the user has not disabled animations.
  _applyAnimationGate() {
    if (!this._animationsEnabled()) {
      this._stopSimLoop();
      this._setSvgAnimationsPaused(true);
      return;
    }
    const live = !!(this._intersecting && this._pageVisible);
    if (live) {
      this._setSvgAnimationsPaused(false);
      this._startSimLoop();
    } else {
      this._setSvgAnimationsPaused(true);
      this._stopSimLoop();
    }
  }

  _observeIntersection() {
    if (typeof IntersectionObserver === "undefined") return;
    if (this._intersectionObserver) this._intersectionObserver.disconnect();
    this._intersectionObserver = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          this._intersecting = entry.isIntersecting;
        }
        this._applyAnimationGate();
      },
      { threshold: 0 }
    );
    this._intersectionObserver.observe(this);
  }

  // Use the SVGSVGElement's internal animation clock so we don't have to
  // tear down / rebuild the wires when leaving the viewport. `pauseAnimations`
  // and `unpauseAnimations` are part of the SVG 1.1 DOM API and are
  // implemented by every browser HA targets (Chromium / WebKit / Gecko).
  _setSvgAnimationsPaused(paused) {
    try {
      const svg = this.shadowRoot?.querySelector("svg.wires");
      if (!svg) return;
      if (paused && typeof svg.pauseAnimations === "function") {
        svg.pauseAnimations();
      } else if (!paused && typeof svg.unpauseAnimations === "function") {
        svg.unpauseAnimations();
      }
    } catch (_) {
      /* ignore */
    }
  }

  // ------------------------------------------------------------------
  // Rendering
  // ------------------------------------------------------------------
  _render() {
    if (!this._config) return;
    const descriptors = this._collectNodeDescriptors();
    this.shadowRoot.innerHTML = `
      <style>${this._styles()}</style>
      <ha-card>
        <div class="header">
          ${
            this._config.title
              ? `<div class="title">${escapeHtml(this._config.title)}</div>`
              : '<div class="title"></div>'
          }
          ${this._modeChipsHTML()}
        </div>
        <div class="stage">
          <svg class="wires" preserveAspectRatio="none"></svg>
          <div class="nodes">
            ${descriptors.map((d) => this._nodeHTML(d)).join("")}
          </div>
          <div class="hint">${
            this._animationsEnabled()
              ? "Trascina i balloon per riposizionarli"
              : "Posizioni statiche — animazioni disattivate"
          }</div>
        </div>
        ${this._boostBarHTML()}
      </ha-card>
    `;

    this._mounted = true;
    if (this.shadowRoot.querySelector("ha-card")) {
      this.shadowRoot
        .querySelector("ha-card")
        .classList.toggle("animations-off", !this._animationsEnabled());
    }
    // Each step is independently guarded so a failure in any of them
    // never prevents the next one from running. The picker tile in
    // particular has very tight initial dimensions and timing, and we
    // can't afford to bail out of the whole render path on a transient
    // layout glitch.
    try { this._bindActions(); } catch (e) {
      // eslint-disable-next-line no-console
      console.warn("[solar-charge-card] _bindActions failed:", e);
    }
    try { this._initSimulationFromDescriptors(descriptors); } catch (e) {
      // eslint-disable-next-line no-console
      console.warn("[solar-charge-card] _initSimulationFromDescriptors failed:", e);
    }
    try { this._bindDragHandlers(); } catch (e) {
      // eslint-disable-next-line no-console
      console.warn("[solar-charge-card] _bindDragHandlers failed:", e);
    }
    try { this._observeResize(); } catch (e) {
      // eslint-disable-next-line no-console
      console.warn("[solar-charge-card] _observeResize failed:", e);
    }
    try { this._observeIntersection(); } catch (e) {
      // eslint-disable-next-line no-console
      console.warn("[solar-charge-card] _observeIntersection failed:", e);
    }
    try { this._applyAnimationGate(); } catch (_) { /* ignore */ }
    try { this._update(); } catch (e) {
      // eslint-disable-next-line no-console
      console.warn("[solar-charge-card] _update failed:", e);
    }
  }

  // Flat list of every balloon we want on the stage. Order doesn't matter
  // (positions are physics-driven), but it's stable for DOM diffing.
  _collectNodeDescriptors() {
    const descs = [
      { key: "solar", kind: "solar", label: "Solar", icon: ICONS.solar },
      { key: "grid", kind: "grid", label: "Grid", icon: ICONS.grid, bidirectional: true },
      { key: "home", kind: "home", label: "Home", icon: ICONS.home, large: true, pinned: true },
    ];
    const batteries = this._resolveBatteries();
    if (!batteries.length) {
      descs.push({
        key: "battery:_main",
        kind: "battery",
        label: "Battery",
        icon: ICONS.battery,
        bidirectional: true,
      });
    } else {
      batteries.forEach((b, i) =>
        descs.push({
          key: `battery:${b.id ?? i}`,
          kind: "battery",
          label: b.name || `Battery ${i + 1}`,
          icon: ICONS.battery,
          bidirectional: true,
        })
      );
    }
    const chargers = this._config.chargers || [];
    if (!chargers.length) {
      if (this._config.ev_entity || this._config.ev_recommended_entity) {
        descs.push({
          key: "charger:_main",
          kind: "charger",
          label: "Wallbox",
          icon: ICONS.charger,
        });
      }
    } else {
      chargers.forEach((ch, i) =>
        descs.push({
          key: `charger:${i}`,
          kind: "charger",
          label: ch.name || `EV ${i + 1}`,
          icon: ICONS.charger,
        })
      );
    }
    return descs;
  }

  _nodeHTML(d) {
    const classes = ["node", d.kind];
    if (d.large) classes.push("large");
    if (d.pinned) classes.push("pinned");
    return `
      <div class="${classes.join(" ")}"
           data-kind="${escapeAttr(d.kind)}" data-key="${escapeAttr(d.key)}">
        <div class="circle">
          <svg class="icon" viewBox="0 0 24 24" aria-hidden="true">
            <path d="${d.icon}"/>
          </svg>
          <div class="value"></div>
          ${d.bidirectional ? '<div class="flow"></div>' : ""}
        </div>
        <div class="label">${escapeHtml(d.label)}</div>
      </div>
    `;
  }

  _modeChipsHTML() {
    if (!this._config.mode_entity) return "";
    // Use the SAME 6-mode set as the standalone mode card so that whichever
    // card the user interacts with they see (and can switch to) the same
    // states. We keep the chips compact (no labels on small widths) so the
    // header doesn't crowd the graph below.
    return `
      <div class="modes">
        ${MODE_BUTTONS.map(
          (m) => `
          <button class="chip mode-chip" data-action="mode"
                  data-value="${escapeAttr(m.value)}"
                  style="--chip-color: ${escapeAttr(m.color)}"
                  title="${escapeAttr(m.label)}" aria-label="${escapeAttr(m.label)}">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="${m.icon}"/></svg>
            <span>${escapeHtml(m.label)}</span>
          </button>`
        ).join("")}
      </div>
    `;
  }

  _boostBarHTML() {
    const c = this._config;
    const chargers = c.chargers || [];
    const boostableCharges = chargers.filter((ch) => ch.boost_entity);
    const hasBattery = !!c.boost_battery_entity;
    if (!boostableCharges.length && !hasBattery) return "";

    const btn = (cls, action, attrs, icon, label) => `
      <button class="boost-btn ${cls}" data-action="${escapeAttr(action)}" ${attrs}>
        <svg viewBox="0 0 24 24"><path d="${icon}"/></svg>
        <span>${escapeHtml(label)}</span>
      </button>`;

    const boltIcon = "M13 2L4.5 13h6l-1 9 8.5-11h-6l1-9z";

    const chargerBtns = boostableCharges
      .map((ch, i) =>
        btn(
          "ev",
          "boost-charger",
          `data-idx="${chargers.indexOf(ch)}"`,
          boltIcon,
          `Boost ${ch.name || `EV ${i + 1}`}`
        )
      )
      .join("");
    const batteryBtn = hasBattery
      ? btn("bat", "boost-battery", "", boltIcon, "Boost Battery")
      : "";

    return `<div class="boost-bar">${chargerBtns}${batteryBtn}</div>`;
  }

  // ------------------------------------------------------------------
  // Physics simulation
  //
  // Each balloon is a point mass with a spring toward its "rest" position
  // and pairwise repulsion against every other node. The Home node is
  // pinned at the center. Drag disables forces on the grabbed node; on
  // release the drop location becomes the new rest ("magnetic" placement).
  // The integrator runs while any node has non-negligible velocity and
  // stops itself when the system settles (save CPU).
  // ------------------------------------------------------------------
  _initSimulationFromDescriptors(descriptors) {
    const next = new Map();
    descriptors.forEach((d) => {
      const el = this.shadowRoot.querySelector(
        `.node[data-key="${CSS.escape(d.key)}"]`
      );
      if (!el) return;
      const prior = this._sim.nodes.get(d.key);
      next.set(d.key, {
        key: d.key,
        kind: d.kind,
        el,
        pinned: !!d.pinned,
        dragging: false,
        r: d.large ? 46 : 36, // effective collision radius (CSS circle / 2)
        pos: prior ? { ...prior.pos } : { x: 0, y: 0 },
        vel: prior ? { ...prior.vel } : { x: 0, y: 0 },
        rest: prior ? { ...prior.rest } : { x: 0, y: 0 },
        initialized: !!prior?.initialized,
      });
    });
    this._sim.nodes = next;
    this._sim.idleFrames = 0;
    if (!this._animationsEnabled()) {
      this._applyStaticLayout(false);
      requestAnimationFrame(() => this._applyStaticLayout(true));
      return;
    }
    // Animated path: place balloons then run the physics integrator.
    this._recomputeRestPositions(false);
    requestAnimationFrame(() => {
      this._recomputeRestPositions(true);
      this._applyAnimationGate();
    });
  }

  _recomputeRestPositions(preservePos) {
    const stage = this.shadowRoot.querySelector(".stage");
    if (!stage) return;
    const rect = stage.getBoundingClientRect();
    // Fall back to a sensible default when the stage has not been sized
    // yet (e.g. the card-picker tile has not finished its first layout).
    // Without this, every balloon would sit at (0,0) and `overflow:
    // hidden` on the stage would clip them off-screen, making the tile
    // look empty and unresponsive.
    const W = rect.width >= 10 ? rect.width : 340;
    const H = rect.height >= 10 ? rect.height : 260;

    const home = this._sim.nodes.get("home");
    if (home) {
      home.rest = { x: W / 2, y: H / 2 };
      home.pos = { ...home.rest };
    }

    const satellites = [];
    this._sim.nodes.forEach((s) => {
      if (s.key !== "home") satellites.push(s);
    });

    // Anchor angle per "kind" (radians; 0 = right, -π/2 = top).
    const kindAnchor = {
      solar: -Math.PI / 2,
      grid: Math.PI,
      battery: (Math.PI * 3) / 4,
      charger: Math.PI / 4,
    };
    // Group satellites by kind to spread multiples around their anchor.
    const groups = new Map();
    satellites.forEach((s) => {
      if (!groups.has(s.kind)) groups.set(s.kind, []);
      groups.get(s.kind).push(s);
    });

    const cx = W / 2, cy = H / 2;
    const radius = Math.max(110, Math.min(W, H) * 0.38);
    const spread = Math.PI / 5;

    groups.forEach((items, kind) => {
      const anchor = kindAnchor[kind] ?? 0;
      items.forEach((s, i) => {
        const n = items.length;
        let angle;
        if (n === 1) angle = anchor;
        else {
          const step = spread / (n - 1);
          angle = anchor - spread / 2 + i * step;
        }
        const rx = cx + Math.cos(angle) * radius;
        const ry = cy + Math.sin(angle) * radius;
        s.rest = { x: rx, y: ry };
        if (!s.initialized) {
          s.pos = { x: rx, y: ry };
          s.initialized = true;
        } else if (!preservePos) {
          s.pos = { x: rx, y: ry };
        }
        this._positionNode(s);
      });
    });
    if (home) this._positionNode(home);
  }

  // Translate the node element so that its circle center sits at pos.
  _positionNode(s) {
    const circle = s.el.querySelector(".circle");
    if (!circle) return;
    // offsetLeft/offsetTop of circle = relative to node top-left.
    const cx = circle.offsetLeft + circle.offsetWidth / 2;
    const cy = circle.offsetTop + circle.offsetHeight / 2;
    s.el.style.transform = `translate3d(${s.pos.x - cx}px, ${s.pos.y - cy}px, 0)`;
  }

  _startSimLoop() {
    if (!this._animationsEnabled()) return;
    // Visibility gate: never spin the rAF loop while the card is off
    // screen / in a backgrounded tab, even if something asks for a
    // refresh (drag, resize, hass tick). Saves CPU on slow tablets and
    // prevents glitchy frame timing on neighbouring gauge cards.
    if (this._intersecting === false || this._pageVisible === false) return;
    if (this._sim.running) return;
    this._sim.running = true;
    this._sim.idleFrames = 0;
    this._sim.last = performance.now();
    const tick = (t) => {
      if (!this._sim.running) return;
      // Re-check the gate every frame so the loop self-stops when the
      // card scrolls out of view mid-animation.
      if (this._intersecting === false || this._pageVisible === false) {
        this._sim.running = false;
        return;
      }
      const dt = Math.min((t - this._sim.last) / 1000, 1 / 30);
      this._sim.last = t;
      this._stepSimulation(dt);
      this._updateWireGeometry();
      this._sim.raf = requestAnimationFrame(tick);
    };
    this._sim.raf = requestAnimationFrame(tick);
  }

  _stopSimLoop() {
    this._sim.running = false;
    if (this._sim.raf) cancelAnimationFrame(this._sim.raf);
    this._sim.raf = 0;
  }

  _anyDragging() {
    let any = false;
    this._sim.nodes.forEach((s) => {
      if (s.dragging) any = true;
    });
    return any;
  }

  _stepSimulation(dt) {
    const K_SPRING = 7;      // spring stiffness toward rest
    const K_REPULSE = 45000; // soft repulsion strength (r² falloff)
    const DAMPING = 0.82;
    const PADDING = 8;       // extra gap between balloons (px)

    const stage = this.shadowRoot.querySelector(".stage");
    if (!stage) return;
    const rect = stage.getBoundingClientRect();
    // Same fallback story as `_recomputeRestPositions`: keep simulating
    // with a reasonable default size rather than bailing, so the tile in
    // the picker paints something meaningful immediately.
    const W = rect.width >= 10 ? rect.width : 340;
    const H = rect.height >= 10 ? rect.height : 260;

    const states = Array.from(this._sim.nodes.values());

    // Zero accumulators
    states.forEach((s) => {
      s._fx = 0;
      s._fy = 0;
    });

    // Spring forces (not on pinned / dragging)
    states.forEach((s) => {
      if (s.pinned || s.dragging) return;
      s._fx += (s.rest.x - s.pos.x) * K_SPRING;
      s._fy += (s.rest.y - s.pos.y) * K_SPRING;
    });

    // Pairwise repulsion
    for (let i = 0; i < states.length; i++) {
      const a = states[i];
      for (let j = i + 1; j < states.length; j++) {
        const b = states[j];
        const dx = b.pos.x - a.pos.x;
        const dy = b.pos.y - a.pos.y;
        const dist2 = dx * dx + dy * dy + 0.01;
        const dist = Math.sqrt(dist2);
        const minSep = a.r + b.r + PADDING;
        const range = minSep * 2.4;
        if (dist > range) continue;
        const nx = dx / dist;
        const ny = dy / dist;
        let force;
        if (dist < minSep) {
          // Hard push: proportional to penetration depth
          force = (minSep - dist) * 900;
        } else {
          force = K_REPULSE / dist2;
        }
        a._fx -= nx * force;
        a._fy -= ny * force;
        b._fx += nx * force;
        b._fy += ny * force;
      }
    }

    // Integrate
    states.forEach((s) => {
      if (s.pinned || s.dragging) return;
      s.vel.x = (s.vel.x + s._fx * dt) * DAMPING;
      s.vel.y = (s.vel.y + s._fy * dt) * DAMPING;
      s.pos.x += s.vel.x * dt;
      s.pos.y += s.vel.y * dt;
      s.pos.x = Math.max(s.r, Math.min(W - s.r, s.pos.x));
      s.pos.y = Math.max(s.r, Math.min(H - s.r, s.pos.y));
    });

    // Hard overlap resolver (a few relaxation passes)
    for (let pass = 0; pass < 3; pass++) {
      for (let i = 0; i < states.length; i++) {
        const a = states[i];
        for (let j = i + 1; j < states.length; j++) {
          const b = states[j];
          const dx = b.pos.x - a.pos.x;
          const dy = b.pos.y - a.pos.y;
          const dist = Math.hypot(dx, dy) || 0.001;
          const minSep = a.r + b.r + PADDING;
          if (dist >= minSep) continue;
          const push = (minSep - dist) / 2;
          const nx = dx / dist;
          const ny = dy / dist;
          // Pinned nodes don't move; dragging nodes push others fully.
          const aMovable = !(a.pinned || a.dragging);
          const bMovable = !(b.pinned || b.dragging);
          if (aMovable && bMovable) {
            a.pos.x -= nx * push;
            a.pos.y -= ny * push;
            b.pos.x += nx * push;
            b.pos.y += ny * push;
          } else if (aMovable) {
            a.pos.x -= nx * push * 2;
            a.pos.y -= ny * push * 2;
          } else if (bMovable) {
            b.pos.x += nx * push * 2;
            b.pos.y += ny * push * 2;
          }
        }
      }
      states.forEach((s) => {
        if (s.pinned) return;
        s.pos.x = Math.max(s.r, Math.min(W - s.r, s.pos.x));
        s.pos.y = Math.max(s.r, Math.min(H - s.r, s.pos.y));
      });
    }

    // Paint & idle check
    let maxV = 0;
    states.forEach((s) => {
      this._positionNode(s);
      const v = Math.hypot(s.vel.x, s.vel.y);
      if (v > maxV) maxV = v;
    });
    if (maxV < 0.4 && !this._anyDragging()) {
      this._sim.idleFrames++;
      if (this._sim.idleFrames > 20) this._stopSimLoop();
    } else {
      this._sim.idleFrames = 0;
    }
  }

  _bindDragHandlers() {
    this.shadowRoot.querySelectorAll(".node").forEach((el) => {
      const key = el.dataset.key;
      const state = this._sim.nodes.get(key);
      if (!state || state.pinned) return;
      el.addEventListener("pointerdown", (ev) =>
        this._onDragStart(ev, state, el)
      );
    });
  }

  _onDragStart(ev, state, el) {
    // Only primary button / first touch
    if (ev.button !== undefined && ev.button !== 0) return;

    // DO NOT preventDefault here: calling preventDefault on pointerdown
    // would suppress the synthetic `click` event, which in turn would
    // break Lovelace's card picker (the tile click that adds the card to
    // the dashboard would never fire). Instead we arm a drag gesture and
    // only commit to it — capturing the pointer and calling
    // preventDefault — once the user has moved beyond a small threshold.
    const THRESHOLD = 5;
    const stage = this.shadowRoot.querySelector(".stage");
    if (!stage) return;
    const rect0 = stage.getBoundingClientRect();
    const startClientX = ev.clientX;
    const startClientY = ev.clientY;
    const grabOffsetX = state.pos.x - (ev.clientX - rect0.left);
    const grabOffsetY = state.pos.y - (ev.clientY - rect0.top);

    let dragStarted = false;
    let captured = false;

    const beginDrag = () => {
      dragStarted = true;
      try {
        el.setPointerCapture(ev.pointerId);
        captured = true;
      } catch (_) {
        /* ignore */
      }
      el.classList.add("dragging");
      state.dragging = true;
      state.vel.x = 0;
      state.vel.y = 0;
    };

    const onMove = (e) => {
      if (!dragStarted) {
        const dx = e.clientX - startClientX;
        const dy = e.clientY - startClientY;
        if (Math.hypot(dx, dy) < THRESHOLD) return;
        beginDrag();
      }
      e.preventDefault();
      const r = stage.getBoundingClientRect();
      let x = e.clientX - r.left + grabOffsetX;
      let y = e.clientY - r.top + grabOffsetY;
      x = Math.max(state.r, Math.min(r.width - state.r, x));
      y = Math.max(state.r, Math.min(r.height - state.r, y));
      state.pos.x = x;
      state.pos.y = y;
      this._positionNode(state);
      if (this._animationsEnabled()) {
        this._startSimLoop();
      } else {
        this._updateWireGeometry();
      }
    };
    const cleanup = () => {
      el.removeEventListener("pointermove", onMove);
      el.removeEventListener("pointerup", onUp);
      el.removeEventListener("pointercancel", onUp);
    };
    const onUp = () => {
      if (dragStarted) {
        state.dragging = false;
        state.rest.x = state.pos.x;
        state.rest.y = state.pos.y;
        el.classList.remove("dragging");
        if (captured) {
          try {
            el.releasePointerCapture(ev.pointerId);
          } catch (_) {
            /* ignore */
          }
        }
        if (this._animationsEnabled()) {
          this._startSimLoop();
        } else {
          this._updateWireGeometry();
        }
      }
      cleanup();
    };
    el.addEventListener("pointermove", onMove);
    el.addEventListener("pointerup", onUp);
    el.addEventListener("pointercancel", onUp);
  }

  // ------------------------------------------------------------------
  // State → DOM updates (cheap; runs every hass tick)
  // ------------------------------------------------------------------
  _update() {
    if (!this._mounted || !this._hass) return;
    const c = this._config;

    const pv = Math.max(0, stateNum(this._hass, c.pv_entity));
    // invert_grid: flip the sign if the user's grid sensor is positive when exporting.
    // Internal convention used by the animation: grid > 0 = importing (grid→home),
    //                                           grid < 0 = exporting  (home→grid).
    const gridRaw = stateNum(this._hass, c.grid_entity);
    const grid = c.invert_grid ? -gridRaw : gridRaw;
    const house = Math.max(0, stateNum(this._hass, c.house_entity));
    const soc = stateNum(this._hass, c.battery_soc_entity);

    this._setNode("solar", { value: fmtPower(pv), active: pv > 10 });

    const gridArrow = grid > 5 ? "←" : grid < -5 ? "→" : "·";
    this._setNode("grid", {
      value: `${gridArrow} ${fmtPower(Math.abs(grid))}`,
      active: Math.abs(grid) > 5,
      subClass: grid < -5 ? "export" : grid > 5 ? "import" : "",
    });

    this._setNode("home", { value: fmtPower(house), active: house > 10 });

    // Batteries
    const batteries = this._resolveBatteries();
    if (!batteries.length) {
      const bPw = stateNum(this._hass, c.battery_entity);
      const arrow = bPw > 5 ? "↓" : bPw < -5 ? "↑" : "·";
      this._setNode("battery:_main", {
        value: `${arrow} ${fmtPower(Math.abs(bPw))}`,
        active: Math.abs(bPw) > 5,
        subClass: bPw > 5 ? "charging" : bPw < -5 ? "discharging" : "",
        extra: c.battery_soc_entity ? fmtPercent(soc) : "",
      });
    } else {
      batteries.forEach((b) => {
        const bPw = stateNum(this._hass, b.power_entity);
        const bSoc = b.soc_entity ? stateNum(this._hass, b.soc_entity) : null;
        const arrow = bPw > 5 ? "↓" : bPw < -5 ? "↑" : "·";
        this._setNode(`battery:${b.id}`, {
          value: `${arrow} ${fmtPower(Math.abs(bPw))}`,
          active: Math.abs(bPw) > 5,
          subClass: bPw > 5 ? "charging" : bPw < -5 ? "discharging" : "",
          extra: bSoc !== null ? fmtPercent(bSoc) : "",
        });
      });
    }

    // Chargers
    const chargers = c.chargers || [];
    if (!chargers.length && (c.ev_entity || c.ev_recommended_entity)) {
      const p = stateNum(this._hass, c.ev_entity);
      const rec = stateNum(this._hass, c.ev_recommended_entity);
      this._setNode("charger:_main", {
        value: fmtPower(p),
        active: p > 50 || rec > 50,
        extra: rec > 0 ? `→ ${fmtPower(rec)}` : "",
      });
    } else {
      chargers.forEach((ch, i) => {
        const p = stateNum(this._hass, ch.power_entity);
        const rec = stateNum(this._hass, ch.recommended_power_entity);
        const charging = stateStr(this._hass, ch.charging_entity) === "on" || p > 50;
        const boost = stateStr(this._hass, ch.boost_entity) === "on";
        this._setNode(`charger:${i}`, {
          value: fmtPower(p),
          active: charging || rec > 50,
          subClass: boost ? "boost" : "",
          extra: rec > 0 ? `→ ${fmtPower(rec)}` : "",
        });
      });
    }

    // Mode chips in the header — synced with both this card's chips and
    // the standalone `solar-charge-mode-card`. We toggle a global `manual`
    // class on the host so the rest of the UI can dim itself out.
    let currentMode = "";
    const modeEntity = resolveModeSelectEntity(this._hass, c.mode_entity);
    if (modeEntity) {
      currentMode = currentModeFromEntity(this._hass, modeEntity);
      this.shadowRoot.querySelectorAll(".modes .mode-chip").forEach((btn) => {
        btn.classList.toggle("active", btn.dataset.value === currentMode);
      });
    }
    const haCard = this.shadowRoot.querySelector("ha-card");
    if (haCard) haCard.classList.toggle("manual-mode", currentMode === "manual");
    // Per-balloon boost buttons
    if (c.boost_battery_entity) {
      const on = stateStr(this._hass, c.boost_battery_entity) === "on";
      const btn = this.shadowRoot.querySelector('[data-action="boost-battery"]');
      if (btn) btn.classList.toggle("active", on);
    }
    (c.chargers || []).forEach((ch, i) => {
      if (!ch.boost_entity) return;
      const on = stateStr(this._hass, ch.boost_entity) === "on";
      const btn = this.shadowRoot.querySelector(
        `[data-action="boost-charger"][data-idx="${i}"]`
      );
      if (btn) btn.classList.toggle("active", on);
      const node = this.shadowRoot.querySelector(
        `.node[data-key="${CSS.escape(`charger:${i}`)}"]`
      );
      if (node) node.classList.toggle("boost", on);
    });

    // Derive flow directions and redraw wires
    this._flowState = this._computeFlowState({ pv, grid, house, batteries, chargers });
    this._drawConnections();
  }

  _setNode(dataKey, { value, active, subClass = "", extra = "" }) {
    const el = this.shadowRoot.querySelector(`.node[data-key="${CSS.escape(dataKey)}"]`);
    if (!el) return;
    el.classList.toggle("active", !!active);
    el.classList.remove("charging", "discharging", "import", "export", "boost");
    if (subClass) el.classList.add(subClass);
    const v = el.querySelector(".value");
    if (v) v.textContent = value;
    const fl = el.querySelector(".flow");
    if (fl) fl.textContent = extra;
    else if (extra) {
      // Append a small subscript for SOC/recommended
      let s = el.querySelector(".sub");
      if (!s) {
        s = document.createElement("div");
        s.className = "sub";
        el.querySelector(".circle").appendChild(s);
      }
      s.textContent = extra;
    }
  }

  _resolveBatteries() {
    const cfg = this._config.batteries;
    if (Array.isArray(cfg) && cfg.length) {
      return cfg.map((b, i) => ({
        id: b.id ?? i,
        name: b.name,
        power_entity: b.power_entity,
        soc_entity: b.soc_entity,
      }));
    }
    return [];
  }

  _computeFlowState({ pv, grid, house, batteries, chargers }) {
    // Each returned entry says whether a given connection is flowing and
    // in which direction (1 = source→home, -1 = home→source).
    const flows = {};
    flows.solar = pv > 10 ? 1 : 0;
    flows.grid = grid > 5 ? 1 : grid < -5 ? -1 : 0;

    if (!batteries.length) {
      const bPw = stateNum(this._hass, this._config.battery_entity);
      flows["battery:_main"] = bPw > 5 ? -1 : bPw < -5 ? 1 : 0;
    } else {
      batteries.forEach((b) => {
        const bPw = stateNum(this._hass, b.power_entity);
        flows[`battery:${b.id}`] = bPw > 5 ? -1 : bPw < -5 ? 1 : 0;
      });
    }

    chargers.forEach((ch, i) => {
      const p = stateNum(this._hass, ch.power_entity);
      flows[`charger:${i}`] = p > 50 ? -1 : 0;
    });
    if (!chargers.length && this._config.ev_entity) {
      const p = stateNum(this._hass, this._config.ev_entity);
      flows["charger:_main"] = p > 50 ? -1 : 0;
    }
    return flows;
  }

  // ------------------------------------------------------------------
  // SVG wires
  //
  // The stage redraws at 60 fps during the physics simulation, so we
  // split the work in two:
  //  _drawConnections()   rebuilds the SVG tree (paths + particles +
  //                       defs) when flow state or topology changes.
  //  _updateWireGeometry() updates only the <path d=…> of existing wires
  //                       during simulation. This keeps <animateMotion>
  //                       particles alive instead of restarting them.
  // ------------------------------------------------------------------
  _collectWires() {
    const svg = this.shadowRoot.querySelector(".wires");
    const home = this.shadowRoot.querySelector('.node[data-kind="home"]');
    const stage = this.shadowRoot.querySelector(".stage");
    if (!svg || !home || !stage) return null;
    const rect = stage.getBoundingClientRect();
    if (rect.width < 2 || rect.height < 2) return null;

    const circleGeom = (nodeEl) => {
      const c = nodeEl.querySelector(".circle");
      const r = c.getBoundingClientRect();
      return {
        cx: r.left - rect.left + r.width / 2,
        cy: r.top - rect.top + r.height / 2,
        r: r.width / 2,
      };
    };
    const edgePoint = (fromX, fromY, toX, toY, r) => {
      const dx = toX - fromX;
      const dy = toY - fromY;
      const len = Math.hypot(dx, dy) || 1;
      return { x: toX - (dx / len) * r, y: toY - (dy / len) * r };
    };

    const homeG = circleGeom(home);
    const wires = [];
    this.shadowRoot
      .querySelectorAll(".node:not([data-kind='home'])")
      .forEach((node) => {
        const key = node.dataset.key;
        const kind = node.dataset.kind;
        const src = circleGeom(node);
        const srcEdge = edgePoint(homeG.cx, homeG.cy, src.cx, src.cy, src.r);
        const homeEdge = edgePoint(src.cx, src.cy, homeG.cx, homeG.cy, homeG.r);
        const d = curvePath(srcEdge.x, srcEdge.y, homeEdge.x, homeEdge.y);
        const color = NODE_COLORS[kind] || NODE_COLORS.muted;
        const flow = this._flowState?.[key] || 0;
        wires.push({ key, d, color, flow, active: flow !== 0, kind });
      });

    return { svg, rect, wires };
  }

  // Lightweight per-frame path refresh used by the physics loop.
  _updateWireGeometry() {
    const pack = this._collectWires();
    if (!pack) return;
    const { svg, rect, wires } = pack;
    svg.setAttribute("viewBox", `0 0 ${rect.width} ${rect.height}`);
    // If topology or flow-state mismatched the cached DOM, fall back to rebuild.
    if (!this._wirePaths || this._wirePaths.size !== wires.length) {
      this._drawConnections();
      return;
    }
    for (const w of wires) {
      const p = this._wirePaths.get(w.key);
      if (!p) {
        this._drawConnections();
        return;
      }
      if (p._active !== w.active) {
        // Flow state changed → rebuild to add/remove particle
        this._drawConnections();
        return;
      }
      if (p._d !== w.d) {
        p.setAttribute("d", w.d);
        p._d = w.d;
      }
    }
  }

  _drawConnections() {
    const pack = this._collectWires();
    if (!pack) return;
    const { svg, rect, wires } = pack;
    svg.setAttribute("viewBox", `0 0 ${rect.width} ${rect.height}`);
    svg.removeAttribute("width");
    svg.removeAttribute("height");

    const ns = "http://www.w3.org/2000/svg";
    svg.replaceChildren();
    this._wirePaths = new Map();

    // Static background paths (always visible, muted)
    wires.forEach((w) => {
      const base = document.createElementNS(ns, "path");
      base.setAttribute("d", w.d);
      base.setAttribute("fill", "none");
      base.setAttribute("stroke", w.color);
      base.setAttribute("stroke-width", w.active ? "2.5" : "1.25");
      base.setAttribute("stroke-linecap", "round");
      base.setAttribute("opacity", w.active ? "0.85" : "0.22");
      base.setAttribute("id", `wire-${w.key.replace(/[^\w-]/g, "_")}`);
      base._d = w.d;
      base._active = w.active;
      this._wirePaths.set(w.key, base);
      svg.appendChild(base);
    });

    // Animated flow particles on active wires (skipped when animations: false)
    if (!this._animationsEnabled()) return;

    wires.forEach((w) => {
      if (!w.active) return;
      const circle = document.createElementNS(ns, "circle");
      circle.setAttribute("r", "4");
      circle.setAttribute("fill", w.color);
      circle.setAttribute("filter", "url(#glow)");
      const motion = document.createElementNS(ns, "animateMotion");
      motion.setAttribute("dur", "2.2s");
      motion.setAttribute("repeatCount", "indefinite");
      motion.setAttribute("rotate", "auto");
      if (w.flow < 0) {
        // Reverse direction: home → source
        motion.setAttribute("keyPoints", "1;0");
        motion.setAttribute("keyTimes", "0;1");
        motion.setAttribute("calcMode", "linear");
      }
      const mpath = document.createElementNS(ns, "mpath");
      mpath.setAttributeNS(
        "http://www.w3.org/1999/xlink",
        "href",
        `#wire-${w.key.replace(/[^\w-]/g, "_")}`
      );
      motion.appendChild(mpath);
      circle.appendChild(motion);
      svg.appendChild(circle);
    });

    // SVG filter for glow (added once)
    const defs = document.createElementNS(ns, "defs");
    defs.innerHTML = `
      <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
        <feGaussianBlur stdDeviation="2.5" result="blur"/>
        <feMerge>
          <feMergeNode in="blur"/>
          <feMergeNode in="SourceGraphic"/>
        </feMerge>
      </filter>`;
    svg.appendChild(defs);
  }

  _observeResize() {
    if (this._resizeObserver) this._resizeObserver.disconnect();
    const stage = this.shadowRoot.querySelector(".stage");
    if (!stage) return;
    this._resizeObserver = new ResizeObserver(() => {
      if (this._animationsEnabled()) {
        this._recomputeRestPositions(true);
        this._applyAnimationGate();
      } else {
        this._applyStaticLayout(true);
      }
    });
    this._resizeObserver.observe(stage);
    window.addEventListener("resize", this._onResize);
  }

  // ------------------------------------------------------------------
  // Actions
  // ------------------------------------------------------------------
  _bindActions() {
    this.shadowRoot.querySelectorAll("[data-action]").forEach((btn) => {
      btn.addEventListener("click", (ev) => this._onAction(ev));
    });
  }

  async _onAction(ev) {
    if (!this._hass) return;
    const btn = ev.currentTarget;
    const action = btn.dataset.action;
    const c = this._config;
    try {
      if (action === "mode") {
        const value = btn.dataset.value;
        const modeEntity = resolveModeSelectEntity(this._hass, c.mode_entity);
        await applyBalancingMode(this._hass, modeEntity, value);
      } else if (action === "boost-battery" && c.boost_battery_entity) {
        await this._hass.callService("switch", "toggle", {
          entity_id: c.boost_battery_entity,
        });
      } else if (action === "boost-charger") {
        const i = Number(btn.dataset.idx);
        const ch = (c.chargers || [])[i];
        if (ch?.boost_entity) {
          await this._hass.callService("switch", "toggle", {
            entity_id: ch.boost_entity,
          });
        }
      }
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error("solar-charge-card action failed", err);
    }
  }

  // ------------------------------------------------------------------
  _styles() {
    return `
      :host { display: block; }
      ha-card {
        position: relative;
        padding: 12px 14px 14px;
        background:
          radial-gradient(ellipse at top, rgba(120,140,180,0.08), transparent 70%),
          var(--ha-card-background, var(--card-background-color, #1c1f24));
        color: var(--primary-text-color, #e8e8e8);
        overflow: hidden;
        display: flex;
        flex-direction: column;
        min-height: 460px;
      }
      /* Visual cue when the integration is bypassed: dim the live flows
         and display a small "manuale" badge in the corner of the stage. */
      ha-card.manual-mode .stage { opacity: 0.55; filter: saturate(0.6); }
      ha-card.manual-mode::after {
        content: "MANUALE — bypass attivo";
        position: absolute;
        top: 10px;
        right: 14px;
        font-size: 0.62rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        padding: 3px 8px;
        border-radius: 999px;
        background: rgba(179, 136, 255, 0.18);
        border: 1px solid #B388FF;
        color: #B388FF;
        pointer-events: none;
        z-index: 5;
      }

      /* Header: title + compact mode chips (always takes minimal vertical
         space; does NOT count in the 3:1 stage/boost ratio). */
      .header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 10px;
        margin-bottom: 6px;
        padding: 0 2px;
        flex-wrap: wrap;
      }
      .title {
        font-size: 1rem;
        font-weight: 600;
        letter-spacing: 0.02em;
        opacity: 0.9;
      }
      .modes {
        display: flex;
        gap: 5px;
        flex-wrap: wrap;
      }
      .mode-chip {
        --chip-color: #9aa0a6;
        font-family: inherit;
        font-size: 0.7rem;
        font-weight: 600;
        color: var(--chip-color);
        background: rgba(255,255,255,0.03);
        border: 1.4px solid var(--chip-color);
        border-radius: 999px;
        padding: 4px 9px 4px 7px;
        cursor: pointer;
        display: inline-flex;
        align-items: center;
        gap: 4px;
        opacity: 0.55;
        transition: background 180ms ease, color 180ms ease,
                    box-shadow 180ms ease, opacity 180ms ease;
      }
      .mode-chip svg { width: 13px; height: 13px; fill: currentColor; }
      .mode-chip:hover { opacity: 0.85; background: rgba(255,255,255,0.06); }
      .mode-chip.active {
        opacity: 1;
        color: #0b0d12;
        background: var(--chip-color);
        box-shadow: 0 0 10px -2px var(--chip-color);
      }
      .mode-chip.active svg { filter: none; }
      /* Compact view: drop the label on narrow headers (icons only). */
      @media (max-width: 700px) {
        .mode-chip span { display: none; }
        .mode-chip { padding: 5px; }
      }

      /* Stage (graph area): gets 3 parts of the vertical space. */
      .stage {
        position: relative;
        width: 100%;
        flex: 3;
        min-height: 280px;
        overflow: hidden;
      }
      .wires {
        position: absolute;
        inset: 0;
        width: 100%;
        height: 100%;
        pointer-events: none;
      }
      .nodes {
        position: absolute;
        inset: 0;
      }
      .hint {
        position: absolute;
        right: 8px;
        bottom: 4px;
        font-size: 0.62rem;
        letter-spacing: 0.02em;
        opacity: 0.35;
        pointer-events: none;
        user-select: none;
      }

      .node {
        position: absolute;
        left: 0;
        top: 0;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 4px;
        opacity: 0.78;
        will-change: transform;
        touch-action: none;
        cursor: grab;
        user-select: none;
        transition: opacity 260ms ease, filter 200ms ease;
      }
      .node.pinned { cursor: default; }
      .node.dragging {
        cursor: grabbing;
        z-index: 10;
        filter: drop-shadow(0 10px 16px rgba(0,0,0,0.45));
      }
      .node.active { opacity: 1; }
      .circle {
        position: relative;
        width: 72px;
        height: 72px;
        border-radius: 50%;
        border: 2px solid var(--node-color, #555);
        background:
          radial-gradient(circle at 50% 30%, rgba(255,255,255,0.06), transparent 70%),
          rgba(0,0,0,0.25);
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        box-shadow: 0 0 0 0 var(--node-color);
        transition: box-shadow 260ms ease;
      }
      .node.active .circle {
        box-shadow: 0 0 18px -4px var(--node-color);
      }
      .node.large .circle {
        width: 92px;
        height: 92px;
        border-width: 2.5px;
      }
      .icon {
        width: 20px;
        height: 20px;
        fill: var(--node-color);
        filter: drop-shadow(0 0 4px rgba(0,0,0,0.4));
      }
      .node.large .icon { width: 26px; height: 26px; }
      .value {
        margin-top: 2px;
        font-size: 0.7rem;
        font-weight: 600;
        letter-spacing: 0.01em;
        color: var(--node-color);
        text-shadow: 0 1px 2px rgba(0,0,0,0.5);
        white-space: nowrap;
      }
      .node.large .value { font-size: 0.82rem; }
      .sub {
        position: absolute;
        top: 4px;
        left: 50%;
        transform: translateX(-50%);
        font-size: 0.62rem;
        opacity: 0.75;
        color: var(--node-color);
      }
      .label {
        font-size: 0.7rem;
        opacity: 0.75;
        letter-spacing: 0.02em;
        margin-top: 1px;
      }

      .node.solar  { --node-color: ${NODE_COLORS.solar}; }
      .node.grid   { --node-color: ${NODE_COLORS.grid}; }
      .node.battery{ --node-color: ${NODE_COLORS.battery}; }
      .node.home   { --node-color: ${NODE_COLORS.home}; }
      .node.charger{ --node-color: ${NODE_COLORS.charger}; }

      /* Boost bar (bottom 1/4): dedicated, exclusive, prominent. */
      .boost-bar {
        flex: 1;
        min-height: 80px;
        margin-top: 10px;
        padding-top: 12px;
        border-top: 1px solid rgba(255,255,255,0.07);
        display: flex;
        gap: 10px;
        align-items: center;
        justify-content: center;
        flex-wrap: wrap;
      }
      .boost-btn {
        --btn-color: #888;
        font-family: inherit;
        font-size: 0.82rem;
        font-weight: 600;
        letter-spacing: 0.01em;
        color: var(--btn-color);
        background: rgba(255,255,255,0.03);
        border: 1.5px solid var(--btn-color);
        border-radius: 999px;
        padding: 9px 18px;
        cursor: pointer;
        display: inline-flex;
        align-items: center;
        gap: 8px;
        transition: background 180ms ease, color 180ms ease,
                    box-shadow 200ms ease, transform 150ms ease;
      }
      .boost-btn svg { width: 14px; height: 14px; fill: currentColor; }
      .boost-btn:hover { background: rgba(255,255,255,0.08); transform: translateY(-1px); }
      .boost-btn.ev  { --btn-color: ${NODE_COLORS.charger}; }
      .boost-btn.bat { --btn-color: ${NODE_COLORS.battery}; }
      .boost-btn.active {
        color: #0b0d12;
        background: var(--btn-color);
        box-shadow: 0 0 18px -2px var(--btn-color);
      }

      @media (max-width: 520px) {
        .circle { width: 58px; height: 58px; }
        .node.large .circle { width: 74px; height: 74px; }
        .icon { width: 17px; height: 17px; }
        .node.large .icon { width: 22px; height: 22px; }
        .value { font-size: 0.64rem; }
        .node.large .value { font-size: 0.72rem; }
        .label { font-size: 0.64rem; }
        .boost-btn { font-size: 0.74rem; padding: 7px 13px; }
      }
    `;
  }
}

// Register the main card eagerly, before any subsequent class declaration
// so a later parse/runtime failure cannot prevent this registration.
if (!customElements.get("solar-charge-card")) {
  customElements.define("solar-charge-card", SolarChargeCard);
}

// ---------------------------------------------------------------------------
// Visual editor (simple HTML form — no Lit dependency either)
// ---------------------------------------------------------------------------
class SolarChargeCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
  }

  setConfig(config) {
    try {
      this._config = { ...normalizeCardConfig(config) };
      this._render();
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error("[solar-charge-card-editor] setConfig failed:", err);
      this._config = {};
    }
  }

  set hass(hass) {
    this._hass = hass;
  }

  _render() {
    const fields = [
      ["title", "Title"],
      ["pv_entity", "PV power entity"],
      ["house_entity", "House power entity"],
      ["grid_entity", "Grid power entity"],
      ["battery_entity", "Battery power entity (single-battery fallback)"],
      ["battery_soc_entity", "Battery SOC entity"],
      ["ev_recommended_entity", "EV recommended power total (legacy)"],
      ["mode_entity", "Mode select entity"],
      ["boost_battery_entity", "Boost battery switch"],
    ];
    const booleans = [
      [
        "invert_grid",
        "Invert grid sign",
        "Enable if your grid sensor is positive when exporting / negative when importing.",
        false,
      ],
      [
        "animations",
        "Balloon physics and energy-flow animation",
        "Disable for static balloon positions and wires only (less CPU on tablets).",
        true,
      ],
    ];
    this.shadowRoot.innerHTML = `
      <style>
        .editor { display: flex; flex-direction: column; gap: 10px; padding: 8px 0; }
        label { display: flex; flex-direction: column; font-size: 0.85rem; gap: 4px; }
        input { padding: 6px 8px; font-size: 0.9rem;
                background: var(--secondary-background-color, #2a2a2a);
                color: var(--primary-text-color, #eee);
                border: 1px solid rgba(255,255,255,0.15);
                border-radius: 6px; }
        .hint { font-size: 0.75rem; opacity: 0.65; }
        pre { background: rgba(0,0,0,0.25); padding: 8px; border-radius: 6px;
              font-size: 0.75rem; white-space: pre-wrap; }
      </style>
      <div class="editor">
        ${fields
          .map(
            ([k, lbl]) => `
          <label>
            <span>${lbl}</span>
            <input data-key="${escapeAttr(k)}" value="${escapeAttr(
              this._config[k] ?? ""
            )}" />
          </label>`
          )
          .join("")}
        ${booleans
          .map(
            ([k, lbl, hint, defaultOn]) => `
          <label style="flex-direction: row; align-items: center; gap: 8px;">
            <input type="checkbox" data-key="${escapeAttr(k)}" data-type="bool" data-default-on="${
              defaultOn ? "true" : ""
            }" ${
              (defaultOn ? this._config[k] !== false : !!this._config[k])
                ? "checked"
                : ""
            } />
            <span>${escapeHtml(lbl)}</span>
          </label>
          <div class="hint" style="margin-top:-6px;">${escapeHtml(hint)}</div>`
          )
          .join("")}
        <div class="hint">
          Lists (<code>chargers</code>, <code>batteries</code>) must be edited in YAML.
          Example:
          <pre>
chargers:
  - name: Garage
    power_entity: sensor.solar_charge_garage_power
    recommended_power_entity: sensor.solar_charge_garage_recommended_power
    charging_entity: binary_sensor.solar_charge_garage_charging
    boost_entity: switch.solar_charge_garage_boost
batteries:
  - id: main
    name: Main
    power_entity: sensor.solar_charge_main_power
    soc_entity: sensor.solar_charge_main_soc</pre>
        </div>
      </div>
    `;
    this.shadowRoot.querySelectorAll("input[data-key]").forEach((inp) => {
      inp.addEventListener("change", (ev) => {
        const key = ev.target.dataset.key;
        const isBool = ev.target.dataset.type === "bool";
        const next = { ...this._config };
        if (isBool) {
          const defaultOn = ev.target.dataset.defaultOn === "true";
          if (defaultOn) {
            if (ev.target.checked) delete next[key];
            else next[key] = false;
          } else if (ev.target.checked) {
            next[key] = true;
          } else {
            delete next[key];
          }
        } else {
          const value = ev.target.value;
          if (value === "") delete next[key];
          else next[key] = value;
        }
        this._config = next;
        this.dispatchEvent(
          new CustomEvent("config-changed", { detail: { config: next } })
        );
      });
    });
  }
}

if (!customElements.get("solar-charge-card-editor")) {
  customElements.define("solar-charge-card-editor", SolarChargeCardEditor);
}

// ---------------------------------------------------------------------------
// Mode selector card — compact pill strip that drives the integration's
// `select.solar_charge_balancing_mode` entity. Only the active mode lights
// up; tapping any other one calls `select.select_option`. Icons are
// inline SVG paths so there's no dependency on Material icons.
// ---------------------------------------------------------------------------
class SolarChargeModeCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = null;
    this._hass = null;
    this._mounted = false;
  }

  static getConfigElement() {
    return document.createElement("solar-charge-mode-card-editor");
  }

  static async getStubConfig(hass /* , entities, entitiesFallback */) {
    const fallback = { title: "Modalità di carica" };
    try {
      const resolved = resolveModeSelectEntity(hass, null);
      if (resolved) fallback.mode_entity = resolved;
    } catch (err) {
      // eslint-disable-next-line no-console
      console.warn("[solar-charge-mode-card] getStubConfig failed:", err);
    }
    return fallback;
  }

  getCardSize() {
    return 2;
  }

  getGridOptions() {
    return {
      columns: 6,
      rows: 2,
      min_columns: 3,
      min_rows: 1,
    };
  }

  setConfig(config) {
    try {
      this._config = { ...normalizeCardConfig(config) };
      this._enriched = false;
      this._enrichLastTry = 0;
      this._mounted = false;
      if (this._hass) this._enrichConfigFromHass();
      this._render();
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error("[solar-charge-mode-card] setConfig failed:", err);
      this._config = { ...normalizeCardConfig(config) };
      this._renderFallback();
    }
  }

  // Points `mode_entity` at the integration's mode select (registry or
  // renamed entity id such as select.solar_charge_balancer_modalita_di_bilanciamento).
  _enrichConfigFromHass() {
    if (!this._hass || !this._config) return false;
    if (this._enriched) return false;
    if (!this._enrichRetryAllowed()) return false;
    const resolved = resolveModeSelectEntity(
      this._hass,
      this._config.mode_entity
    );
    if (!resolved) return false;
    const changed = this._config.mode_entity !== resolved;
    if (changed) {
      this._config = { ...this._config, mode_entity: resolved };
      // eslint-disable-next-line no-console
      console.info(
        "[solar-charge-mode-card] mode_entity resolved to",
        resolved
      );
    }
    this._enriched = true;
    return changed;
  }

  _resolveModeEntity() {
    if (!this._hass) return this._config?.mode_entity || null;
    const resolved = resolveModeSelectEntity(
      this._hass,
      this._config?.mode_entity
    );
    if (resolved && resolved !== this._config?.mode_entity) {
      this._config = { ...this._config, mode_entity: resolved };
    }
    return resolved;
  }

  set hass(hass) {
    this._hass = hass;
    try {
      // Top up the config the first time hass arrives, just like the
      // big graph card does. If anything changed we MUST re-render so
      // _update can pick up the new mode_entity.
      const enriched = this._enrichConfigFromHass();
      if (!this._mounted || enriched) {
        this._render();
      } else {
        // Always re-evaluate which chip should be highlighted whenever
        // hass changes, including the very first assignment that comes
        // after a setConfig-only render (when _mounted was already true
        // but no hass was available yet to drive _update).
        this._update();
      }
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error("[solar-charge-mode-card] update failed:", err);
      this._renderFallback();
    }
  }

  // Mode card has no continuous animation, but `_enrichConfigFromHass`
  // performs a registry walk on every hass tick when not yet enriched.
  // Throttle the same way the graph card does, also resetting the
  // throttle when setConfig is called.
  _enrichRetryAllowed() {
    const ENRICH_RETRY_MS = 2000;
    const now = Date.now();
    if (this._enrichLastTry && now - this._enrichLastTry < ENRICH_RETRY_MS) {
      return false;
    }
    this._enrichLastTry = now;
    return true;
  }

  _renderFallback() {
    this.shadowRoot.innerHTML = `
      <style>
        ha-card { padding: 12px 14px; display:block; }
        .t { font-weight: 600; font-size: 0.95rem; }
        .h { font-size: 0.78rem; opacity: 0.7; margin-top: 6px; }
      </style>
      <ha-card>
        <div class="t">Solar Charge Mode Selector</div>
        <div class="h">Configura <code>mode_entity</code> (es. <code>select.solar_charge_balancer_modalita_di_bilanciamento</code>) oppure attendi il rilevamento automatico.</div>
      </ha-card>
    `;
    this._mounted = true;
  }

  _visibleModes() {
    const entityId = this._resolveModeEntity();
    const opts =
      entityId && this._hass
        ? selectOptionsForEntity(this._hass, entityId)
        : null;
    const list = this._config?.modes;
    let buttons =
      Array.isArray(list) && list.length
        ? MODE_BUTTONS.filter((m) => list.includes(m.value))
        : MODE_BUTTONS;
    if (opts?.length) {
      buttons = buttons.filter((m) => opts.includes(m.value));
    }
    return buttons;
  }

  _render() {
    if (!this._config) return;
    const modes = this._visibleModes();
    const title = this._config.title ?? "Modalità di carica";
    this.shadowRoot.innerHTML = `
      <style>${this._styles()}</style>
      <ha-card>
        ${title ? `<div class="title">${escapeHtml(title)}</div>` : ""}
        <div class="strip">
          ${modes
            .map(
              (m) => `
            <button class="chip" data-value="${escapeAttr(m.value)}"
              style="--chip-color: ${escapeAttr(m.color)}" aria-label="${escapeAttr(m.label)}">
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="${m.icon}"/></svg>
              <span>${escapeHtml(m.label)}</span>
            </button>`
            )
            .join("")}
        </div>
      </ha-card>
    `;
    this._mounted = true;
    this.shadowRoot.querySelectorAll(".chip").forEach((btn) => {
      btn.addEventListener("click", (ev) => this._onClick(ev));
    });
    this._update();
  }

  _update() {
    if (!this._mounted || !this._hass) return;
    const entityId = this._resolveModeEntity();
    const current = entityId ? currentModeFromEntity(this._hass, entityId) : "";
    this.shadowRoot.querySelectorAll(".chip").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.value === current);
      btn.disabled = !entityId;
    });
    const card = this.shadowRoot.querySelector("ha-card");
    if (card) card.classList.toggle("no-entity", !entityId);
  }

  async _onClick(ev) {
    const btn = ev.currentTarget;
    const value = btn.dataset.value;
    if (!this._hass || !value) return;

    const entityId = this._resolveModeEntity();
    if (!entityId) {
      // eslint-disable-next-line no-console
      console.error(
        "[solar-charge-mode-card] mode select entity not found; set mode_entity in YAML"
      );
      return;
    }

    try {
      const via = await applyBalancingMode(this._hass, entityId, value);
      // eslint-disable-next-line no-console
      console.info(`[solar-charge-mode-card] mode change OK via ${via}`);
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error("[solar-charge-mode-card] mode change failed:", err);
      this._update();
      return;
    }
    this._update();
  }

  _styles() {
    return `
      :host { display: block; }
      ha-card {
        padding: 12px 14px 14px;
        background: var(--ha-card-background, var(--card-background-color, #1c1f24));
        color: var(--primary-text-color, #e8e8e8);
      }
      .title {
        font-size: 0.95rem;
        font-weight: 600;
        opacity: 0.85;
        margin-bottom: 10px;
        letter-spacing: 0.02em;
      }
      .strip {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }
      .chip {
        --chip-color: #9aa0a6;
        flex: 1 1 80px;
        min-width: 72px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 6px;
        padding: 10px 12px;
        font-family: inherit;
        font-size: 0.78rem;
        font-weight: 600;
        letter-spacing: 0.02em;
        color: var(--chip-color);
        background: rgba(255, 255, 255, 0.035);
        border: 1.5px solid var(--chip-color);
        border-radius: 14px;
        cursor: pointer;
        transition:
          background 180ms ease,
          color 180ms ease,
          transform 150ms ease,
          box-shadow 200ms ease,
          border-color 180ms ease;
        opacity: 0.55;
      }
      .chip:hover {
        opacity: 0.85;
        background: rgba(255, 255, 255, 0.07);
        transform: translateY(-1px);
      }
      .chip svg {
        width: 18px;
        height: 18px;
        fill: currentColor;
        filter: drop-shadow(0 0 3px rgba(0,0,0,0.35));
      }
      .chip.active {
        opacity: 1;
        color: #0b0d12;
        background: var(--chip-color);
        border-color: var(--chip-color);
        box-shadow: 0 0 14px -2px var(--chip-color);
      }
      .chip.active svg { filter: none; }
      .chip:disabled { opacity: 0.45; cursor: not-allowed; }
      ha-card.no-entity .strip { opacity: 0.5; }
      @media (max-width: 420px) {
        .chip span { display: none; }
        .chip { flex: 0 0 auto; padding: 10px; }
      }
    `;
  }
}

if (!customElements.get("solar-charge-mode-card")) {
  customElements.define("solar-charge-mode-card", SolarChargeModeCard);
}

class SolarChargeModeCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
  }

  setConfig(config) {
    try {
      this._config = { ...normalizeCardConfig(config) };
      this._render();
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error("[solar-charge-mode-card-editor] setConfig failed:", err);
      this._config = {};
    }
  }

  set hass(hass) {
    this._hass = hass;
  }

  _render() {
    const fields = [
      ["title", "Title (empty to hide)"],
      ["mode_entity", "Mode select entity"],
    ];
    this.shadowRoot.innerHTML = `
      <style>
        .editor { display: flex; flex-direction: column; gap: 10px; padding: 8px 0; }
        label { display: flex; flex-direction: column; font-size: 0.85rem; gap: 4px; }
        input { padding: 6px 8px; font-size: 0.9rem;
                background: var(--secondary-background-color, #2a2a2a);
                color: var(--primary-text-color, #eee);
                border: 1px solid rgba(255,255,255,0.15);
                border-radius: 6px; }
        .hint { font-size: 0.75rem; opacity: 0.65; }
      </style>
      <div class="editor">
        ${fields
          .map(
            ([k, lbl]) => `
          <label>
            <span>${lbl}</span>
            <input data-key="${k}" value="${this._config[k] ?? ""}" />
          </label>`
          )
          .join("")}
        <div class="hint">
          To show only a subset of modes, edit the YAML and add
          <code>modes: [off, eco, balanced, boost_car, boost_battery, fast]</code>
          with the values you want displayed.
        </div>
      </div>
    `;
    this.shadowRoot.querySelectorAll("input[data-key]").forEach((inp) => {
      inp.addEventListener("change", (ev) => {
        const key = ev.target.dataset.key;
        const value = ev.target.value;
        const next = { ...this._config };
        if (value === "") delete next[key];
        else next[key] = value;
        this._config = next;
        this.dispatchEvent(
          new CustomEvent("config-changed", { detail: { config: next } })
        );
      });
    });
  }
}

// ---------------------------------------------------------------------------
// Safe registration (idempotent: script may load twice)
// ---------------------------------------------------------------------------
if (!customElements.get("solar-charge-card")) {
  customElements.define("solar-charge-card", SolarChargeCard);
}
if (!customElements.get("solar-charge-card-editor")) {
  customElements.define("solar-charge-card-editor", SolarChargeCardEditor);
}
if (!customElements.get("solar-charge-mode-card")) {
  customElements.define("solar-charge-mode-card", SolarChargeModeCard);
}
if (!customElements.get("solar-charge-mode-card-editor")) {
  customElements.define(
    "solar-charge-mode-card-editor",
    SolarChargeModeCardEditor
  );
}
