# Solar Charge Balancer

Integrazione **custom per Home Assistant** (2024.4+) per bilanciare in tempo reale la ricarica di una colonnina EV con produzione fotovoltaica, batteria di casa e consumi domestici — con card Lovelace "Tesla-like" animata e notifiche multicanale.

![badge](https://img.shields.io/badge/HA-2024.4%2B-41bdf5)
![badge](https://img.shields.io/badge/HACS-Custom-41bdf5)
![badge](https://img.shields.io/badge/status-beta-orange)

## Caratteristiche

- **Algoritmo di bilanciamento** con 6 modalità: `eco`, `balanced`, `boost_car`, `boost_battery`, `fast`, `off`.
- **Multi-inverter**: somma di più entità di produzione PV.
- **Batteria di casa**: priorità sotto il SOC minimo, target configurabile, potenza massima di carica.
- **Controllo wallbox**: regola corrente (A) o potenza (W) tramite le entità `number.*` della tua wallbox.
- **Boost auto / boost batteria** con un click (switch + servizi).
- **Notifiche** su canali a scelta (`mobile_app_*`, `telegram`, `email`, `persistent_notification`, ecc.):
  - fine ricarica;
  - allarme sovraconsumo (soglia impostabile);
  - cambio modalità (opzionale).
- **Card Lovelace** custom con balloon stile Tesla, linee di flusso animate e pulsanti di boost.
- **Config flow multi-step** con tooltip in ogni campo e **traduzioni IT/EN** (facile aggiungerne altre).
- **Servizi**: `solar_charge.set_mode`, `solar_charge.boost_car`, `solar_charge.boost_battery`, `solar_charge.reset`.

## Installazione

### 1. HACS (consigliato)

1. HACS → Integrations → menu `⋮` → *Custom repositories*
2. Aggiungi `https://github.com/cybercecco/solar-charge` come `Integration`.
3. Installa **Solar Charge Balancer**.
4. Riavvia Home Assistant.

### 2. Manuale

```bash
cd /config
git clone https://github.com/cybercecco/solar-charge.git
cp -r solar-charge/custom_components/solar_charge custom_components/
cp -r solar-charge/www/solar-charge-card www/
```

### 3. Card Lovelace

Aggiungi la risorsa in *Impostazioni → Dashboards → Risorse*:

```yaml
url: /local/solar-charge-card/solar-charge-card.js
type: module
```

(Se usi HACS Frontend category la risorsa viene registrata automaticamente.)

## Configurazione

*Impostazioni → Dispositivi & Servizi → Aggiungi integrazione → Solar Charge Balancer*.

Il wizard ti guiderà in 6 step:

| Step | Cosa imposti |
|---|---|
| **1 — Fotovoltaico** | Una o più entità di potenza (W) della produzione PV |
| **2 — Casa & Rete** | Consumo casa, scambio rete, segno dell'export |
| **3 — Batteria** | Entità potenza/SOC, capacità, SOC min/target, max carica |
| **4 — Colonnina** | Potenza wallbox, number A/W, switch enable, fasi, tensione, I min/max |
| **5 — Parametri** | Modalità default, surplus minimo, isteresi, soglia sovraconsumo, intervallo |
| **6 — Notifiche** | Servizi notify.* e quali eventi notificare |

Ogni campo mostra un **tooltip descrittivo** (la descrizione è tradotta).

## Card Lovelace

```yaml
type: custom:solar-charge-card
title: Casa & Auto
pv_entity: sensor.solar_charge_balancer_pv_power
house_entity: sensor.solar_charge_balancer_house_load
grid_entity: sensor.solar_charge_balancer_grid_exchange
battery_entity: sensor.solar_charge_balancer_battery_power
battery_soc_entity: sensor.solar_charge_balancer_battery_soc
ev_entity: sensor.solar_charge_balancer_wallbox_power
ev_recommended_entity: sensor.solar_charge_balancer_recommended_ev_power
mode_entity: select.solar_charge_balancer_balancing_mode
boost_car_entity: switch.solar_charge_balancer_boost_car
boost_battery_entity: switch.solar_charge_balancer_boost_battery
```

## Algoritmo (sintesi)

Ad ogni intervallo di update (default 10 s):

```
available = PV - (house_load - current_ev_power)
```

A seconda della modalità:

- **eco** → l'auto prende solo ciò che resta dopo aver riempito la batteria, mai dalla rete.
- **balanced** → se il SOC è sotto il minimo → batteria prima; altrimenti 50/50.
- **boost_car** → auto prima (con un po' di import se serve), batteria dopo.
- **boost_battery** → batteria prima, auto solo se resta surplus.
- **fast** → auto al massimo (accetta import dalla rete).
- **off** → auto spenta; l'integrazione non scrive sulla wallbox.

L'isteresi evita che la corrente oscilli: la nuova potenza viene applicata solo se cambia di più di `hysteresis_w` rispetto alla precedente.

## Servizi

```yaml
service: solar_charge.boost_car
data:
  entry_id: <opzionale>
```

Stessa forma per `boost_battery`, `reset`, e `set_mode` che accetta `mode: eco|balanced|boost_car|boost_battery|fast|off`.

## Traduzioni

I testi del config flow e dei nomi di entità sono localizzati. I file sono in
`custom_components/solar_charge/translations/*.json`. Per aggiungere una nuova lingua, copia `en.json` in `<codice_lingua>.json` e traduci.

## Compatibilità

- Home Assistant **>= 2024.4**.
- Testato con wallbox che espongono `number.*` per la corrente (Wallbox, go-e, OpenEVSE, Easee via integrazione) e batterie con sensori `power` + `battery`.

## Licenza

MIT — vedi `LICENSE`.
