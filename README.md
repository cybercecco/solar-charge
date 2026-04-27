# Solar Charge Balancer

Integrazione **custom per Home Assistant** (2024.4+) per bilanciare in tempo reale la ricarica di una colonnina EV con produzione fotovoltaica, batteria di casa e consumi domestici — con card Lovelace "Tesla-like" animata e notifiche multicanale.

![badge](https://img.shields.io/badge/HA-2024.4%2B-41bdf5)
![badge](https://img.shields.io/badge/HACS-Custom-41bdf5)
![badge](https://img.shields.io/badge/status-beta-orange)

## Caratteristiche

- **Installazione lineare**: l'integrazione si crea con un solo click (solo un nome). Entità, batteria, colonnine, soglie e notifiche si configurano **dopo**, dal pulsante "Configura", in qualsiasi momento.
- **Algoritmo di bilanciamento** con 6 modalità sincronizzate tra entrambe le card:

  | Modalità | Cosa fa |
  |---|---|
  | **off** | Colonnina spenta. PV in eccesso continua a caricare la batteria di casa. |
  | **eco** | EV riceve **solo** il surplus PV rispetto al consumo casalingo. |
  | **balanced** | EV riceve la **stessa potenza** che va alla batteria di casa, solo da PV. |
  | **fast** | EV riceve **tutto il PV** disponibile + un budget configurabile dalla rete (default **3 kW**). |
  | **battery_fast** | PV viene **prima** dirottato alla batteria; l'EV riceve PV solo al raggiungimento del SOC configurato (default **98 %**). |
  | **manual** | L'integrazione **bypassa** i comandi della colonnina: l'utente regola corrente/potenza a mano. Uscendo da manuale, il controllo torna **immediato** (nessuna isteresi). |

  Configurabili in **Parametri di bilanciamento**: cap massimo casa, **tolleranza di pre-allarme (default 10%)**, budget grid in Fast, SOC della Battery Fast.

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
```

### 3. Card Lovelace — nessuna configurazione richiesta

Dalla **v0.4.0** la card viene registrata automaticamente dall'integrazione:
il file viene servito da `/solar_charge_static/solar-charge-card.js` e
aggiunto come risorsa "extra JS" del frontend. Dopo il riavvio la
trovi direttamente in **Modifica dashboard → Aggiungi card → Custom: Solar Charge Card**.

> Se avevi fatto un'installazione manuale della card precedente e hai una
> risorsa YAML puntata a `/local/solar-charge-card/...`, puoi rimuoverla:
> ora è ridondante.

## Configurazione

*Impostazioni → Dispositivi & Servizi → Aggiungi integrazione → Solar Charge Balancer*.

Al primo step ti viene chiesto solo il **nome** dell'istanza. Premi "Invia" e l'integrazione è attiva.

Subito dopo (o in qualsiasi momento, dal pulsante **Configura**) apri il menu Options con queste sezioni indipendenti:

| Sezione | Cosa imposti |
|---|---|
| **Preset impianto** | Auto-rilevamento per Huawei (SUN2000 + LUNA 2000), SolarEdge, Fronius, SMA, Enphase, Tesla Powerwall. Riempie PV, consumi, rete, batteria in un colpo solo; puoi ritoccare tutto a mano dopo. |
| **Produzione fotovoltaica** | Una o più entità di potenza (W). Più inverter/stringhe vengono sommati. |
| **Consumi di casa e rete** | Consumo casa, scambio rete, segno dell'export. |
| **Batterie di casa** | Lista di pacchi: aggiungi, modifica, elimina singolarmente (capacità in kWh per il calcolo della media SOC pesata). Soglie globali (SOC min/target, max carica totale) in sotto-sezione dedicata. |
| **Colonnine di ricarica** | Lista di wallbox: aggiungi, modifica, elimina singolarmente. Ogni colonnina ha nome, entità, fasi, tensione, I min/max e **priorità**. |
| **Parametri di bilanciamento** | Modalità default, strategia di distribuzione (`priority`/`equal`/`roundrobin`), surplus minimo, isteresi, soglia sovraconsumo, intervallo. |
| **Notifiche** | Servizi `notify.*` e quali eventi notificare. |

### Preset supportati (auto-rilevamento)

Ogni preset cerca nell'entity registry le entità standard dell'integrazione corrispondente e le propone come preconfigurazione. Conferma con l'apposito pulsante nella schermata di preview.

| Preset | Integrazione attesa | Batteria di default |
|---|---|---|
| Huawei SUN2000 + LUNA 2000 | [huawei_solar](https://github.com/wlcrs/huawei_solar) (HACS) | 10 kWh (2 moduli da 5 kWh) |
| SolarEdge | `solaredge` ufficiale | StorEdge 9.7 kWh |
| Fronius GEN24/Symo | `fronius` ufficiale | 10 kWh |
| SMA Sunny Boy/Tripower | `sma` / `sbfspot` | 7.7 kWh |
| Enphase Envoy + Encharge | `enphase_envoy` ufficiale | 10.5 kWh |
| Tesla Powerwall | `powerwall` ufficiale | 13.5 kWh |
| Generico / manuale | — | — |

Ogni campo mostra un **tooltip descrittivo** (la descrizione è tradotta).

## Card Lovelace

Quando aggiungi **Solar Charge Card** dalla picker delle dashboard, la configurazione YAML viene **compilata automaticamente** leggendo tutte le entità registrate dall'integrazione: hub principale (PV, casa, rete, batteria, SOC, modalità, boost), tutte le colonnine e tutte le batterie di casa. Devi solo compilare ciò che l'auto-rilevamento non trova (p. es. se hai aggiunto la card prima di configurare una wallbox). Esempio di output equivalente:

### Layout magnetico, drag & drop

I balloon sono disposti su un grafo attorno a **Home** (fissa al centro) usando una simulazione fisica: ogni nodo ha una molla verso la sua posizione naturale (Solar in alto, Grid a sinistra, batterie a sud-ovest, wallbox a sud-est) e tutti si respingono reciprocamente per non sovrapporsi mai. Puoi **trascinare** qualsiasi balloon con il mouse o il tocco: gli altri si spostano per fargli spazio, e quando lo rilasci quella diventa la sua nuova posizione "magnetica". Home resta sempre al centro. Il loop si ferma da solo quando il sistema si stabilizza, quindi niente CPU sprecata.

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

### Card di selezione modalità

Oltre alla card principale, il pacchetto registra anche **Solar Charge Mode Selector** (`custom:solar-charge-mode-card`): una striscia compatta di pulsanti con icone per scegliere al volo la modalità dell'integrazione. Solo il pulsante corrispondente alla modalità corrente è acceso; un tap chiama `select.select_option` sull'entità `select.solar_charge_balancing_mode`.

```yaml
type: custom:solar-charge-mode-card
title: Modalità di carica
mode_entity: select.solar_charge_balancing_mode
# opzionale: mostra solo un sottoinsieme delle modalità
# modes: [off, eco, balanced, boost_car, boost_battery, fast]
```

Le modalità disponibili sono `off`, `eco`, `balanced`, `boost_car`, `boost_battery`, `fast`. Quando aggiungi la card dal picker, `mode_entity` viene rilevata automaticamente dall'entità `select` dell'integrazione.

### Convenzione del segno grid nella card

La card assume la convenzione interna dell'integrazione: **Grid > 0 = import (rete → casa)**, **Grid < 0 = export (casa → rete)**. Se punti `grid_entity` al sensore normalizzato `sensor.solar_charge_grid_power` e hai configurato correttamente il flag *"Rete: export negativo"* nelle opzioni dell'integrazione, l'animazione andrà nel verso giusto.

Se invece punti la card direttamente al contatore grezzo e non puoi riconfigurare l'integrazione, abilita il flag della card:

```yaml
type: custom:solar-charge-card
grid_entity: sensor.mio_contatore_grid
invert_grid: true  # abilita se il sensore è positivo quando esporti
```

## Derivazione automatica dei dati mancanti

L'integrazione applica a ogni ciclo il **bilancio energetico istantaneo**:

```
House = PV + Grid − Battery
```

con la convenzione: `Grid > 0` = import, `Battery > 0` = in carica. Se **una** sola delle quattro grandezze (PV, consumo casa, scambio rete, potenza batteria) non è configurata o l'entità restituisce `unavailable`, viene **calcolata automaticamente** dalle altre tre.

Tipico caso d'uso: hai il meter di rete ma nessun sensore esplicito per "consumi casa" → l'integrazione deriva il consumo in tempo reale sapendo produzione, export/import e carica/scarica batteria. Il sensore `sensor.solar_charge_house_power` espone nell'attributo `source` se il valore è `measured` o `derived`, così puoi distinguerli in una card o in un template.

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

## Sviluppo

### Validazione locale

Lancia le stesse verifiche della CI direttamente sulla tua macchina:

```bash
./scripts/validate.sh             # JSON + Python compile + hassfest
GITHUB_TOKEN=ghp_xxx ./scripts/validate.sh --hacs   # include HACS action
```

Richiede `python3` e `docker` (solo per i passi hassfest / HACS).

### CI hardening

- Tutte le action in `.github/workflows/validate.yml` sono **pinnate al commit SHA** (con il tag di riferimento nel commento) per resistenza supply-chain.
- `dependabot.yml` ruota le SHA ogni lunedì alle 06:00 Europe/Rome in un unico PR raggruppato.

## Traduzioni

I testi del config flow e dei nomi di entità sono localizzati. I file sono in
`custom_components/solar_charge/translations/*.json`. Per aggiungere una nuova lingua, copia `en.json` in `<codice_lingua>.json` e traduci.

## Compatibilità

- Home Assistant **>= 2024.4**.
- Testato con wallbox che espongono `number.*` per la corrente (Wallbox, go-e, OpenEVSE, Easee via integrazione) e batterie con sensori `power` + `battery`.

## Licenza

MIT — vedi `LICENSE`.
