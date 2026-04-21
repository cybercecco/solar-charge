# Solar Charge Balancer

Integrazione **custom per Home Assistant** (2024.4+) per bilanciare in tempo reale la ricarica di una colonnina EV con produzione fotovoltaica, batteria di casa e consumi domestici — con card Lovelace "Tesla-like" animata e notifiche multicanale.

![badge](https://img.shields.io/badge/HA-2024.4%2B-41bdf5)
![badge](https://img.shields.io/badge/HACS-Custom-41bdf5)
![badge](https://img.shields.io/badge/status-beta-orange)

## Caratteristiche

- **Installazione lineare**: l'integrazione si crea con un solo click (solo un nome). Entità, batteria, colonnine, soglie e notifiche si configurano **dopo**, dal pulsante "Configura", in qualsiasi momento.
- **Algoritmo di bilanciamento** con 6 modalità: `eco`, `balanced`, `boost_car`, `boost_battery`, `fast`, `off`.
- **Multi-inverter**: somma di più entità di produzione PV.
- **Colonnine multiple**: supporta N wallbox, ognuna con entità e **priorità** proprie. Strategia di distribuzione selezionabile (`priority`, `equal`, `roundrobin`).
- **Boost per colonnina**: ogni wallbox ha il proprio `switch` di boost che la porta in priorità massima.
- **Batteria di casa**: priorità sotto il SOC minimo, target configurabile, potenza massima di carica.
- **Controllo wallbox**: regola corrente (A) o potenza (W) tramite le entità `number.*` della tua wallbox.
- **Notifiche per-colonnina** su canali a scelta (`mobile_app_*`, `telegram`, `email`, `persistent_notification`, ecc.):
  - fine ricarica **per ciascuna wallbox**;
  - allarme sovraconsumo (soglia impostabile);
  - cambio modalità (opzionale).
- **Card Lovelace** custom con balloon stile Tesla, linee di flusso animate e tile per ogni colonnina.
- **Options flow a menu** con tooltip e **traduzioni IT/EN**.
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

Al primo step ti viene chiesto solo il **nome** dell'istanza. Premi "Invia" e l'integrazione è attiva.

Subito dopo (o in qualsiasi momento, dal pulsante **Configura**) apri il menu Options con queste sezioni indipendenti:

| Sezione | Cosa imposti |
|---|---|
| **Produzione fotovoltaica** | Una o più entità di potenza (W). Più inverter/stringhe vengono sommati. |
| **Consumi di casa e rete** | Consumo casa, scambio rete, segno dell'export. |
| **Batteria di casa** | Entità potenza/SOC, capacità, SOC min/target, max carica. |
| **Colonnine di ricarica** | Lista di wallbox: aggiungi, modifica, elimina singolarmente. Ogni colonnina ha nome, entità, fasi, tensione, I min/max e **priorità**. |
| **Parametri di bilanciamento** | Modalità default, strategia di distribuzione (`priority`/`equal`/`roundrobin`), surplus minimo, isteresi, soglia sovraconsumo, intervallo. |
| **Notifiche** | Servizi `notify.*` e quali eventi notificare. |

Ogni campo mostra un **tooltip descrittivo** (la descrizione è tradotta).

## Card Lovelace

```yaml
type: custom:solar-charge-card
title: Casa & Auto
pv_entity: sensor.solar_charge_pv_power
house_entity: sensor.solar_charge_house_power
grid_entity: sensor.solar_charge_grid_power
battery_entity: sensor.solar_charge_battery_power
battery_soc_entity: sensor.solar_charge_battery_soc
ev_entity: sensor.solar_charge_ev_power_total
ev_recommended_entity: sensor.solar_charge_recommended_ev_power_total
mode_entity: select.solar_charge_balancing_mode
boost_battery_entity: switch.solar_charge_boost_battery
chargers:
  - name: Garage
    power_entity: sensor.solar_charge_garage_power
    recommended_power_entity: sensor.solar_charge_garage_recommended_power
    recommended_current_entity: sensor.solar_charge_garage_recommended_current
    charging_entity: binary_sensor.solar_charge_garage_charging
    boost_entity: switch.solar_charge_garage_boost
  - name: Officina
    power_entity: sensor.solar_charge_officina_power
    recommended_power_entity: sensor.solar_charge_officina_recommended_power
    recommended_current_entity: sensor.solar_charge_officina_recommended_current
    charging_entity: binary_sensor.solar_charge_officina_charging
    boost_entity: switch.solar_charge_officina_boost
```

*Suggerimento*: le entità per-colonnina usano lo slug del nome che hai dato alla wallbox. Dopo aver configurato le colonnine, controlla in **Sviluppatore → Stati** per trovare gli ID esatti.

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
