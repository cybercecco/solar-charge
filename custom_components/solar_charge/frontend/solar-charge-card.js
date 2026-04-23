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

const CARD_VERSION = "0.9.3";

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
    this._onResize = () => this._drawConnections();
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
      const registry = hass?.entities || {};
      const devices = hass?.devices || {};
      const scEntries = Object.values(registry).filter(
        (e) => e && e.platform === "solar_charge"
      );
      if (!scEntries.length) return fallback;

      // Group entities by their device_id, and each device by its
      // solar_charge identifier (entry_id / entry_id_charger_X / entry_id_battery_X).
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
        // charger/battery sub-devices are named "<entry title> — <slug>"
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

      const cfg = { title: "Solar Charge" };
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
        return fallback;
      }
      return cfg;
    } catch (err) {
      console.warn("[solar-charge-card] getStubConfig fallback:", err);
      return fallback;
    }
  }

  getCardSize() {
    return 6;
  }

  setConfig(config) {
    if (!config) throw new Error("Invalid configuration");
    this._config = { ...config };
    // Reset mount state → full rebuild on next hass assignment
    this._mounted = false;
    if (this._hass) this._render();
  }

  set hass(hass) {
    const firstRun = !this._hass;
    this._hass = hass;
    if (!this._mounted) this._render();
    else if (!firstRun) this._update();
  }

  disconnectedCallback() {
    if (this._resizeObserver) {
      this._resizeObserver.disconnect();
      this._resizeObserver = null;
    }
    window.removeEventListener("resize", this._onResize);
  }

  // ------------------------------------------------------------------
  // Rendering
  // ------------------------------------------------------------------
  _render() {
    if (!this._config) return;
    this.shadowRoot.innerHTML = `
      <style>${this._styles()}</style>
      <ha-card>
        <div class="header">
          ${this._config.title ? `<div class="title">${this._config.title}</div>` : '<div class="title"></div>'}
          ${this._modeChipsHTML()}
        </div>
        <div class="stage">
          <svg class="wires" preserveAspectRatio="none"></svg>
          <div class="nodes">
            <div class="row top">
              ${this._nodeHTML("solar", "Solar", ICONS.solar)}
            </div>
            <div class="row middle">
              ${this._nodeHTML("grid", "Grid", ICONS.grid, { bidirectional: true })}
              <div class="spacer"></div>
              ${this._nodeHTML("home", "Home", ICONS.home, { large: true })}
            </div>
            <div class="row bottom">
              <div class="group batteries">${this._batteriesHTML()}</div>
              <div class="group chargers">${this._chargersHTML()}</div>
            </div>
          </div>
        </div>
        ${this._boostBarHTML()}
      </ha-card>
    `;

    this._mounted = true;
    this._bindActions();
    this._observeResize();
    this._update();
  }

  _nodeHTML(kind, label, iconPath, opts = {}) {
    const { large = false, bidirectional = false, dataKey = kind } = opts;
    return `
      <div class="node ${kind} ${large ? "large" : ""}"
           data-kind="${kind}" data-key="${dataKey}">
        <div class="circle">
          <svg class="icon" viewBox="0 0 24 24" aria-hidden="true">
            <path d="${iconPath}"/>
          </svg>
          <div class="value"></div>
          ${bidirectional ? '<div class="flow"></div>' : ""}
        </div>
        <div class="label">${label}</div>
      </div>
    `;
  }

  _batteriesHTML() {
    const list = this._resolveBatteries();
    if (!list.length) {
      return this._nodeHTML("battery", "Battery", ICONS.battery, {
        bidirectional: true,
        dataKey: "battery:_main",
      });
    }
    return list
      .map((b, i) =>
        this._nodeHTML("battery", b.name || `Battery ${i + 1}`, ICONS.battery, {
          bidirectional: true,
          dataKey: `battery:${b.id ?? i}`,
        })
      )
      .join("");
  }

  _chargersHTML() {
    const chargers = this._config.chargers || [];
    if (!chargers.length) {
      if (this._config.ev_entity || this._config.ev_recommended_entity) {
        return this._nodeHTML("charger", "Wallbox", ICONS.charger, {
          dataKey: "charger:_main",
        });
      }
      return "";
    }
    return chargers
      .map((ch, i) =>
        this._nodeHTML("charger", ch.name || `EV ${i + 1}`, ICONS.charger, {
          dataKey: `charger:${i}`,
        })
      )
      .join("");
  }

  _modeChipsHTML() {
    if (!this._config.mode_entity) return "";
    const modes = ["off", "balanced", "fast"];
    return `
      <div class="modes">
        ${modes
          .map(
            (m) =>
              `<button class="chip" data-action="mode" data-value="${m}">${m}</button>`
          )
          .join("")}
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
      <button class="boost-btn ${cls}" data-action="${action}" ${attrs}>
        <svg viewBox="0 0 24 24"><path d="${icon}"/></svg>
        <span>${label}</span>
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

    // Mode chips in the footer
    if (c.mode_entity) {
      const m = stateStr(this._hass, c.mode_entity);
      this.shadowRoot.querySelectorAll(".modes .chip").forEach((btn) => {
        btn.classList.toggle("active", btn.dataset.value === m);
      });
    }
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
  // ------------------------------------------------------------------
  _drawConnections() {
    const svg = this.shadowRoot.querySelector(".wires");
    const home = this.shadowRoot.querySelector('.node[data-kind="home"]');
    if (!svg || !home) return;
    const stage = this.shadowRoot.querySelector(".stage");
    if (!stage) return;

    const rect = stage.getBoundingClientRect();
    if (rect.width < 2 || rect.height < 2) return; // not laid out yet
    svg.setAttribute("viewBox", `0 0 ${rect.width} ${rect.height}`);
    svg.removeAttribute("width");
    svg.removeAttribute("height");

    // Geometry is computed on the `.circle` element (not `.node`, which
    // includes the label underneath and would shift the center down).
    const circleGeom = (nodeEl) => {
      const c = nodeEl.querySelector(".circle");
      const r = c.getBoundingClientRect();
      return {
        cx: r.left - rect.left + r.width / 2,
        cy: r.top - rect.top + r.height / 2,
        r: r.width / 2,
      };
    };

    const homeG = circleGeom(home);

    const edgePoint = (fromX, fromY, toX, toY, r) => {
      const dx = toX - fromX;
      const dy = toY - fromY;
      const len = Math.hypot(dx, dy) || 1;
      return { x: toX - (dx / len) * r, y: toY - (dy / len) * r };
    };

    const wires = [];
    const sources = this.shadowRoot.querySelectorAll(".node:not([data-kind='home'])");
    sources.forEach((node) => {
      const key = node.dataset.key;
      const kind = node.dataset.kind;
      const src = circleGeom(node);
      // Edge of the source circle pointing toward home.
      const srcEdge = edgePoint(homeG.cx, homeG.cy, src.cx, src.cy, src.r);
      // Edge of the home circle pointing toward this source.
      const homeEdge = edgePoint(src.cx, src.cy, homeG.cx, homeG.cy, homeG.r);

      const d = curvePath(srcEdge.x, srcEdge.y, homeEdge.x, homeEdge.y);
      const color = NODE_COLORS[kind] || NODE_COLORS.muted;
      const flow = this._flowState?.[key] || 0;
      const active = flow !== 0;

      wires.push({ key, d, color, flow, active, kind });
    });

    // Build SVG content in one shot
    const ns = "http://www.w3.org/2000/svg";
    svg.replaceChildren();

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
      svg.appendChild(base);
    });

    // Animated flow particles on active wires
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
    this._resizeObserver = new ResizeObserver(() => this._drawConnections());
    this._resizeObserver.observe(stage);
    window.addEventListener("resize", this._onResize);
    // Defer once to let layout settle
    requestAnimationFrame(() => this._drawConnections());
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
      if (action === "mode" && c.mode_entity) {
        await this._hass.callService("select", "select_option", {
          entity_id: c.mode_entity,
          option: btn.dataset.value,
        });
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
      .chip {
        font-family: inherit;
        font-size: 0.7rem;
        color: var(--primary-text-color, #ddd);
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.12);
        border-radius: 999px;
        padding: 4px 11px;
        cursor: pointer;
        text-transform: capitalize;
        transition: background 180ms ease, border-color 180ms ease, color 180ms ease;
      }
      .chip:hover { background: rgba(255,255,255,0.09); }
      .chip.active {
        background: rgba(102,187,106,0.18);
        border-color: ${NODE_COLORS.home};
        color: #e6ffe9;
      }

      /* Stage (graph area): gets 3 parts of the vertical space. */
      .stage {
        position: relative;
        width: 100%;
        flex: 3;
        min-height: 260px;
      }
      .wires {
        position: absolute;
        inset: 0;
        width: 100%;
        height: 100%;
        pointer-events: none;
      }
      .nodes {
        position: relative;
        width: 100%;
        height: 100%;
        display: grid;
        grid-template-rows: 1fr 1.2fr 1fr;
        gap: 4px;
        padding: 2px 4px;
        box-sizing: border-box;
      }
      .row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
        min-width: 0;
      }
      .row.top { justify-content: center; }
      .row.middle { align-items: center; }
      .row.bottom { align-items: flex-end; }
      .spacer { flex: 1; }
      .group {
        display: flex;
        gap: 10px;
        align-items: flex-end;
        flex-wrap: wrap;
      }
      .group.batteries { justify-content: flex-start; flex: 1; }
      .group.chargers { justify-content: flex-end; flex: 1; }

      .node {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 4px;
        opacity: 0.78;
        transition: opacity 260ms ease, transform 260ms ease;
        flex-shrink: 0;
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
    this._config = { ...config };
    this._render();
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
            <input data-key="${k}" value="${this._config[k] ?? ""}" />
          </label>`
          )
          .join("")}
        ${booleans
          .map(
            ([k, lbl, hint]) => `
          <label style="flex-direction: row; align-items: center; gap: 8px;">
            <input type="checkbox" data-key="${k}" data-type="bool" ${
              this._config[k] ? "checked" : ""
            } />
            <span>${lbl}</span>
          </label>
          <div class="hint" style="margin-top:-6px;">${hint}</div>`
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
          if (ev.target.checked) next[key] = true;
          else delete next[key];
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

// ---------------------------------------------------------------------------
// Safe registration (idempotent: script may load twice)
// ---------------------------------------------------------------------------
if (!customElements.get("solar-charge-card")) {
  customElements.define("solar-charge-card", SolarChargeCard);
}
if (!customElements.get("solar-charge-card-editor")) {
  customElements.define("solar-charge-card-editor", SolarChargeCardEditor);
}
