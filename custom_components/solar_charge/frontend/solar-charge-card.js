/*!
 * Solar Charge Card — Lovelace custom card
 * Tesla-like energy flow visualisation with animated connection lines,
 * plus a compact tile row for multiple chargers.
 *
 * Registers: <solar-charge-card>
 * Also provides a visual editor: <solar-charge-card-editor>
 *
 * Drop this file into /config/www/solar-charge-card/ and add it as a resource:
 *   url: /local/solar-charge-card/solar-charge-card.js
 *   type: module
 */

const CARD_VERSION = "0.5.0";

console.info(
  `%c SOLAR-CHARGE-CARD %c v${CARD_VERSION} `,
  "color:white;background:#1f6feb;font-weight:700;padding:2px 6px;border-radius:3px 0 0 3px;",
  "color:#1f6feb;background:#0d1117;padding:2px 6px;border-radius:0 3px 3px 0;"
);

import {
  LitElement,
  html,
  css,
  svg,
  nothing,
} from "https://unpkg.com/lit-element@4.0.4/lit-element.js?module";

// ---------------------------------------------------------------------------
// Utility helpers
// ---------------------------------------------------------------------------
const fmtW = (v) => {
  if (v === null || v === undefined || isNaN(v)) return "—";
  const n = Number(v);
  if (Math.abs(n) >= 1000) return `${(n / 1000).toFixed(2)} kW`;
  return `${n.toFixed(0)} W`;
};

const fmtA = (v) => {
  if (v === null || v === undefined || isNaN(v)) return "—";
  return `${Number(v).toFixed(1)} A`;
};

const pct = (v) => (v === null || v === undefined || isNaN(v) ? "—" : `${Number(v).toFixed(0)}%`);

const stateNum = (hass, id) => {
  if (!id) return 0;
  const s = hass?.states?.[id];
  if (!s || s.state === "unavailable" || s.state === "unknown") return 0;
  const n = Number(s.state);
  return isNaN(n) ? 0 : n;
};

const stateStr = (hass, id) => {
  if (!id) return null;
  const s = hass?.states?.[id];
  if (!s) return null;
  return s.state;
};

// ---------------------------------------------------------------------------
// Card implementation
// ---------------------------------------------------------------------------
class SolarChargeCard extends LitElement {
  static properties = {
    hass: { attribute: false },
    _config: { state: true },
  };

  setConfig(config) {
    if (!config) throw new Error("Invalid configuration");
    this._config = {
      title: "Solar Charge",
      pv_entity: "sensor.solar_charge_pv_power",
      house_entity: "sensor.solar_charge_house_power",
      grid_entity: "sensor.solar_charge_grid_power",
      battery_entity: "sensor.solar_charge_battery_power",
      battery_soc_entity: "sensor.solar_charge_battery_soc",
      ev_entity: "sensor.solar_charge_ev_power_total",
      ev_recommended_entity: "sensor.solar_charge_recommended_ev_power_total",
      mode_entity: "select.solar_charge_balancing_mode",
      boost_battery_entity: "switch.solar_charge_boost_battery",
      chargers: [],
      ...config,
    };
  }

  getCardSize() {
    return 7;
  }

  static getConfigElement() {
    return document.createElement("solar-charge-card-editor");
  }

  static getStubConfig() {
    return {
      title: "Solar Charge",
      pv_entity: "sensor.solar_charge_pv_power",
      house_entity: "sensor.solar_charge_house_power",
      grid_entity: "sensor.solar_charge_grid_power",
      battery_entity: "sensor.solar_charge_battery_power",
      battery_soc_entity: "sensor.solar_charge_battery_soc",
      ev_entity: "sensor.solar_charge_ev_power_total",
      ev_recommended_entity: "sensor.solar_charge_recommended_ev_power_total",
      mode_entity: "select.solar_charge_balancing_mode",
      boost_battery_entity: "switch.solar_charge_boost_battery",
      chargers: [],
    };
  }

  // ---------- Rendering ----------
  render() {
    if (!this.hass || !this._config) return html``;
    const c = this._config;

    const pv = stateNum(this.hass, c.pv_entity);
    const house = stateNum(this.hass, c.house_entity);
    const grid = stateNum(this.hass, c.grid_entity);
    const batt = stateNum(this.hass, c.battery_entity);
    const soc = stateNum(this.hass, c.battery_soc_entity);
    const ev = stateNum(this.hass, c.ev_entity);
    const evRec = stateNum(this.hass, c.ev_recommended_entity);
    const mode = stateStr(this.hass, c.mode_entity);
    const boostBattery = stateStr(this.hass, c.boost_battery_entity) === "on";
    const chargers = Array.isArray(c.chargers) ? c.chargers : [];

    const flows = {
      pvHouse: Math.max(0, Math.min(pv, house)),
      pvBattery: batt > 0 ? Math.min(batt, pv) : 0,
      pvEv: Math.max(0, Math.min(pv - house, ev)),
      pvGrid: grid < 0 ? Math.abs(grid) : 0,
      gridHouse: grid > 0 ? grid : 0,
      batteryHouse: batt < 0 ? Math.abs(batt) : 0,
      batteryEv: batt < 0 && ev > pv ? Math.min(Math.abs(batt), ev - pv) : 0,
    };

    return html`
      <ha-card>
        <div class="header">
          <div class="title">${c.title}</div>
          ${mode
            ? html`<div class="mode-pill" title=${`Modalità: ${mode}`}>
                <ha-icon icon=${this._modeIcon(mode)}></ha-icon>
                <span>${mode}</span>
              </div>`
            : nothing}
        </div>

        <div class="stage">
          ${this._renderSvg(flows)}
          ${this._renderBalloon("pv", "mdi:solar-power-variant", "FV", pv, "sun")}
          ${this._renderBalloon("grid", "mdi:transmission-tower", "Rete", grid, grid < 0 ? "export" : "grid")}
          ${this._renderBalloon("battery", "mdi:home-battery", "Batteria", batt, "battery", soc)}
          ${this._renderBalloon("house", "mdi:home-lightning-bolt", "Casa", house, "house")}
          ${this._renderBalloon(
            "ev",
            "mdi:car-electric",
            chargers.length > 1 ? `Auto (${chargers.length})` : "Auto",
            ev,
            "ev",
            null,
            evRec
          )}
        </div>

        ${chargers.length
          ? html`<div class="chargers">
              ${chargers.map((ch) => this._renderChargerTile(ch))}
            </div>`
          : nothing}

        <div class="controls">
          <button
            class=${`boost ${boostBattery ? "active battery" : ""}`}
            @click=${() => this._toggleBoost(c.boost_battery_entity)}
            title="Priorità alla batteria di casa"
          >
            <ha-icon icon="mdi:home-battery"></ha-icon>
            Boost batteria
          </button>
          <button
            class="boost reset"
            @click=${() =>
              this._callService("select", "select_option", {
                entity_id: c.mode_entity,
                option: "balanced",
              })}
            title="Ripristina bilanciato"
          >
            <ha-icon icon="mdi:scale-balance"></ha-icon>
            Bilanciato
          </button>
        </div>
      </ha-card>
    `;
  }

  // ---------- Charger tile (multi-wallbox) ----------
  _renderChargerTile(ch) {
    const power = stateNum(this.hass, ch.power_entity);
    const recPow = stateNum(this.hass, ch.recommended_power_entity);
    const recA = stateNum(this.hass, ch.recommended_current_entity);
    const boost = stateStr(this.hass, ch.boost_entity) === "on";
    const charging = stateStr(this.hass, ch.charging_entity) === "on" || power > 200;

    return html`
      <div class=${`tile ${charging ? "charging" : ""}`}>
        <div class="tile-head">
          <ha-icon icon="mdi:ev-station"></ha-icon>
          <span class="tile-name">${ch.name || "Colonnina"}</span>
          ${boost
            ? html`<span class="boost-pill"><ha-icon icon="mdi:rocket-launch"></ha-icon></span>`
            : nothing}
        </div>
        <div class="tile-main">
          <div class="tile-power">${fmtW(power)}</div>
          <div class="tile-sub">
            <span title="Potenza consigliata">→ ${fmtW(recPow)}</span>
            ${ch.recommended_current_entity
              ? html`<span title="Corrente consigliata"> · ${fmtA(recA)}</span>`
              : nothing}
          </div>
        </div>
        ${ch.boost_entity
          ? html`<button
              class=${`mini-btn ${boost ? "on" : ""}`}
              @click=${() => this._toggleBoost(ch.boost_entity)}
              title="Boost questa colonnina"
            >
              <ha-icon icon="mdi:rocket-launch-outline"></ha-icon>
              Boost
            </button>`
          : nothing}
      </div>
    `;
  }

  // ---------- SVG ----------
  _renderSvg(flows) {
    const nodes = {
      pv: { x: 50, y: 15 },
      grid: { x: 15, y: 50 },
      battery: { x: 85, y: 50 },
      house: { x: 35, y: 85 },
      ev: { x: 70, y: 85 },
    };

    const maxFlow = Math.max(
      1,
      flows.pvHouse,
      flows.pvBattery,
      flows.pvEv,
      flows.pvGrid,
      flows.gridHouse,
      flows.batteryHouse,
      flows.batteryEv
    );

    const edge = (from, to, active, rev = false) => {
      const a = nodes[from];
      const b = nodes[to];
      const thick = 1 + 5 * (active / maxFlow);
      const opacity = active > 0 ? 0.9 : 0.15;
      const dur = active > 0 ? Math.max(1.2, 4 - (active / maxFlow) * 3) : 0;
      return svg`
        <path
          id=${`p-${from}-${to}`}
          d="M ${a.x} ${a.y} Q ${(a.x + b.x) / 2} ${(a.y + b.y) / 2 + 5} ${b.x} ${b.y}"
          fill="none"
          stroke="url(#grad-${from})"
          stroke-width=${thick}
          opacity=${opacity}
          stroke-linecap="round"
        />
        ${
          dur > 0
            ? svg`
          <circle r="1.1" fill="white" opacity="0.95">
            <animateMotion dur=${`${dur}s`} repeatCount="indefinite" keyPoints=${rev ? "1;0" : "0;1"} keyTimes="0;1">
              <mpath href=${`#p-${from}-${to}`} />
            </animateMotion>
          </circle>
        `
            : nothing
        }
      `;
    };

    return svg`
      <svg class="flow" viewBox="0 0 100 100" preserveAspectRatio="none">
        <defs>
          <linearGradient id="grad-pv" x1="0" x2="1" y1="0" y2="1">
            <stop offset="0" stop-color="#f2b900" />
            <stop offset="1" stop-color="#ffd85c" />
          </linearGradient>
          <linearGradient id="grad-grid" x1="0" x2="1" y1="0" y2="1">
            <stop offset="0" stop-color="#888" />
            <stop offset="1" stop-color="#bbb" />
          </linearGradient>
          <linearGradient id="grad-battery" x1="0" x2="1" y1="0" y2="1">
            <stop offset="0" stop-color="#28c76f" />
            <stop offset="1" stop-color="#6be6a3" />
          </linearGradient>
        </defs>

        ${edge("pv", "house", flows.pvHouse)}
        ${edge("pv", "battery", flows.pvBattery)}
        ${edge("pv", "ev", flows.pvEv)}
        ${edge("pv", "grid", flows.pvGrid, true)}
        ${edge("grid", "house", flows.gridHouse)}
        ${edge("battery", "house", flows.batteryHouse, true)}
        ${edge("battery", "ev", flows.batteryEv, true)}
      </svg>
    `;
  }

  _renderBalloon(key, icon, label, value, kind, soc = null, hint = null) {
    const gridArea = {
      pv: "pv",
      grid: "grid",
      battery: "battery",
      house: "house",
      ev: "ev",
    }[key];

    const val =
      key === "battery" && soc !== null
        ? html`<div class="sub">${pct(soc)}</div>`
        : nothing;

    const hintEl =
      hint !== null && hint !== undefined
        ? html`<div class="hint" title="Potenza consigliata">→ ${fmtW(hint)}</div>`
        : nothing;

    return html`
      <div class=${`balloon ${kind}`} style=${`grid-area:${gridArea}`}>
        <div class="bubble">
          <ha-icon icon=${icon}></ha-icon>
        </div>
        <div class="label">${label}</div>
        <div class="value">${fmtW(value)}</div>
        ${val} ${hintEl}
      </div>
    `;
  }

  _modeIcon(mode) {
    switch (mode) {
      case "eco":
        return "mdi:leaf";
      case "boost_car":
        return "mdi:car-electric";
      case "boost_battery":
        return "mdi:home-battery";
      case "fast":
        return "mdi:flash";
      case "off":
        return "mdi:power";
      default:
        return "mdi:scale-balance";
    }
  }

  async _toggleBoost(entityId) {
    if (!entityId) return;
    const domain = entityId.split(".")[0];
    const state = stateStr(this.hass, entityId);
    const service = state === "on" ? "turn_off" : "turn_on";
    await this.hass.callService(domain, service, { entity_id: entityId });
  }

  async _callService(domain, service, data) {
    await this.hass.callService(domain, service, data);
  }

  // ---------- Styles ----------
  static styles = css`
    :host {
      --sc-bg: var(--card-background-color, #14161a);
      --sc-fg: var(--primary-text-color, #eaeaea);
      --sc-fg-dim: var(--secondary-text-color, #9ba0a6);
      --sc-accent: #1f6feb;
      --sc-sun: #ffbe0b;
      --sc-battery: #28c76f;
      --sc-grid: #a0a4ab;
      --sc-house: #5ac8fa;
      --sc-ev: #ef476f;
    }

    ha-card {
      padding: 16px 20px 20px;
      background: radial-gradient(ellipse at top, rgba(31, 111, 235, 0.15), transparent 55%),
        var(--sc-bg);
      overflow: hidden;
      color: var(--sc-fg);
    }

    .header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 8px;
    }
    .title {
      font-size: 1.15rem;
      font-weight: 600;
      letter-spacing: 0.2px;
    }
    .mode-pill {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 10px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.06);
      border: 1px solid rgba(255, 255, 255, 0.08);
      font-size: 0.8rem;
      color: var(--sc-fg-dim);
      text-transform: capitalize;
    }
    .mode-pill ha-icon {
      --mdc-icon-size: 16px;
      color: var(--sc-accent);
    }

    .stage {
      position: relative;
      display: grid;
      grid-template-areas:
        ".    pv   ."
        "grid  .  battery"
        "house .   ev";
      grid-template-columns: 1fr 1fr 1fr;
      grid-template-rows: 1fr 1fr 1fr;
      aspect-ratio: 5 / 3;
      min-height: 280px;
    }

    svg.flow {
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      z-index: 0;
      pointer-events: none;
    }

    .balloon {
      position: relative;
      z-index: 1;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 2px;
      text-align: center;
    }
    .bubble {
      width: 64px;
      height: 64px;
      border-radius: 50%;
      display: grid;
      place-items: center;
      background: linear-gradient(145deg, rgba(255, 255, 255, 0.08), rgba(0, 0, 0, 0.25));
      border: 1px solid rgba(255, 255, 255, 0.12);
      box-shadow: 0 6px 20px rgba(0, 0, 0, 0.45), inset 0 1px 0 rgba(255, 255, 255, 0.15);
      transition: transform 0.25s ease, box-shadow 0.25s ease;
    }
    .balloon:hover .bubble {
      transform: translateY(-2px) scale(1.04);
    }
    .bubble ha-icon {
      --mdc-icon-size: 30px;
      filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.5));
    }
    .balloon.sun .bubble {
      box-shadow: 0 0 28px rgba(255, 190, 11, 0.35), 0 6px 20px rgba(0, 0, 0, 0.45);
    }
    .balloon.sun ha-icon { color: var(--sc-sun); }
    .balloon.battery ha-icon { color: var(--sc-battery); }
    .balloon.grid ha-icon { color: var(--sc-grid); }
    .balloon.export ha-icon { color: #7ed957; }
    .balloon.house ha-icon { color: var(--sc-house); }
    .balloon.ev ha-icon { color: var(--sc-ev); }

    .label {
      font-size: 0.75rem;
      color: var(--sc-fg-dim);
      text-transform: uppercase;
      letter-spacing: 0.8px;
      margin-top: 4px;
    }
    .value {
      font-size: 0.95rem;
      font-weight: 600;
    }
    .sub {
      font-size: 0.75rem;
      color: var(--sc-fg-dim);
    }
    .hint {
      font-size: 0.7rem;
      color: var(--sc-accent);
      margin-top: 2px;
    }

    /* --- multi-charger tiles --- */
    .chargers {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 10px;
      margin-top: 14px;
    }
    .tile {
      position: relative;
      padding: 10px 12px;
      border-radius: 12px;
      background: linear-gradient(145deg, rgba(255, 255, 255, 0.04), rgba(0, 0, 0, 0.15));
      border: 1px solid rgba(255, 255, 255, 0.08);
      transition: border-color 0.2s ease, box-shadow 0.2s ease;
    }
    .tile.charging {
      border-color: rgba(239, 71, 111, 0.6);
      box-shadow: 0 0 18px rgba(239, 71, 111, 0.25);
    }
    .tile-head {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 0.8rem;
      color: var(--sc-fg-dim);
    }
    .tile-head ha-icon {
      --mdc-icon-size: 16px;
      color: var(--sc-ev);
    }
    .tile-name {
      font-weight: 600;
      color: var(--sc-fg);
      flex: 1;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .boost-pill {
      color: var(--sc-accent);
      --mdc-icon-size: 14px;
    }
    .tile-main {
      margin-top: 4px;
    }
    .tile-power {
      font-size: 1.1rem;
      font-weight: 700;
    }
    .tile-sub {
      font-size: 0.75rem;
      color: var(--sc-fg-dim);
      margin-top: 2px;
    }
    .mini-btn {
      margin-top: 8px;
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 4px 10px;
      font-size: 0.75rem;
      border-radius: 999px;
      border: 1px solid rgba(255, 255, 255, 0.12);
      background: rgba(255, 255, 255, 0.03);
      color: var(--sc-fg);
      cursor: pointer;
    }
    .mini-btn ha-icon { --mdc-icon-size: 14px; }
    .mini-btn.on {
      background: linear-gradient(135deg, #ef476f, #ff6b9a);
      border-color: transparent;
      color: #fff;
    }

    .controls {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 14px;
      justify-content: center;
    }
    .boost {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 8px 14px;
      border-radius: 999px;
      border: 1px solid rgba(255, 255, 255, 0.12);
      background: rgba(255, 255, 255, 0.04);
      color: var(--sc-fg);
      cursor: pointer;
      font-size: 0.85rem;
      transition: all 0.2s ease;
    }
    .boost ha-icon { --mdc-icon-size: 18px; }
    .boost:hover { background: rgba(255, 255, 255, 0.08); }
    .boost.active { border-color: transparent; color: #fff; }
    .boost.active.battery {
      background: linear-gradient(135deg, #28c76f, #6be6a3);
      box-shadow: 0 4px 16px rgba(40, 199, 111, 0.4);
    }
    .boost.reset { opacity: 0.85; }
  `;
}

// ---------------------------------------------------------------------------
// Editor (visual editor)
// ---------------------------------------------------------------------------
class SolarChargeCardEditor extends LitElement {
  static properties = {
    hass: { attribute: false },
    _config: { state: true },
  };

  setConfig(config) {
    this._config = config;
  }

  _schema() {
    return [
      { name: "title", selector: { text: {} } },
      { name: "pv_entity", selector: { entity: { domain: "sensor" } } },
      { name: "house_entity", selector: { entity: { domain: "sensor" } } },
      { name: "grid_entity", selector: { entity: { domain: "sensor" } } },
      { name: "battery_entity", selector: { entity: { domain: "sensor" } } },
      { name: "battery_soc_entity", selector: { entity: { domain: "sensor" } } },
      { name: "ev_entity", selector: { entity: { domain: "sensor" } } },
      { name: "ev_recommended_entity", selector: { entity: { domain: "sensor" } } },
      { name: "mode_entity", selector: { entity: { domain: "select" } } },
      { name: "boost_battery_entity", selector: { entity: { domain: "switch" } } },
    ];
  }

  _labels = {
    title: "Titolo",
    pv_entity: "Potenza fotovoltaica",
    house_entity: "Consumo casa",
    grid_entity: "Scambio rete",
    battery_entity: "Potenza batteria",
    battery_soc_entity: "SOC batteria",
    ev_entity: "Potenza EV totale",
    ev_recommended_entity: "Potenza EV consigliata totale",
    mode_entity: "Modalità (select)",
    boost_battery_entity: "Boost batteria (switch)",
  };

  render() {
    if (!this.hass || !this._config) return html``;
    const main = Object.fromEntries(
      Object.entries(this._config).filter(([k]) => k !== "chargers")
    );
    return html`
      <ha-form
        .hass=${this.hass}
        .data=${main}
        .schema=${this._schema()}
        .computeLabel=${(s) => this._labels[s.name] ?? s.name}
        @value-changed=${this._valueChanged}
      ></ha-form>
      <div class="note">
        La lista <code>chargers:</code> (una entry per wallbox) va scritta in YAML.
        Esempio:<br />
        <pre>
chargers:
  - name: Garage
    power_entity: sensor.solar_charge_garage_power
    recommended_power_entity: sensor.solar_charge_garage_recommended_power
    recommended_current_entity: sensor.solar_charge_garage_recommended_current
    charging_entity: binary_sensor.solar_charge_garage_charging
    boost_entity: switch.solar_charge_garage_boost</pre>
      </div>
    `;
  }

  _valueChanged(ev) {
    const newMain = ev.detail.value;
    this._config = { ...this._config, ...newMain };
    this.dispatchEvent(
      new CustomEvent("config-changed", { detail: { config: this._config } })
    );
  }

  static styles = css`
    .note {
      margin-top: 10px;
      font-size: 0.8rem;
      color: var(--secondary-text-color);
    }
    pre {
      background: rgba(0, 0, 0, 0.2);
      padding: 8px;
      border-radius: 6px;
      overflow-x: auto;
    }
  `;
}

// Defensive: the script may be loaded twice (once via add_extra_js_url,
// once via a Lovelace resource entry). Without this guard
// customElements.define would throw on the second run and nothing after
// it (including the customCards registration) would execute.
if (!customElements.get("solar-charge-card")) {
  customElements.define("solar-charge-card", SolarChargeCard);
}
if (!customElements.get("solar-charge-card-editor")) {
  customElements.define("solar-charge-card-editor", SolarChargeCardEditor);
}

window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === "solar-charge-card")) {
  window.customCards.push({
    type: "solar-charge-card",
    name: "Solar Charge Card",
    description:
      "Tesla-like energy flow card for the Solar Charge Balancer integration. Supports multiple wallboxes.",
    preview: true,
    documentationURL: "https://github.com/cybercecco/solar-charge",
  });
}
