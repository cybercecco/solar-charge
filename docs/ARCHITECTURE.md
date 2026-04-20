# Architettura

```
┌─────────────────────────────────────────────────────────────────┐
│                       Config Flow (wizard)                      │
│   PV → House/Grid → Battery → Wallbox → Thresholds → Notify     │
└───────────────────────────────┬─────────────────────────────────┘
                                │ (ConfigEntry.data + options)
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     SolarChargeCoordinator                      │
│  • Legge stati: PV[n], house, grid, batt, soc, ev               │
│  • Normalizza segni (import/export, charge/discharge)           │
│  • Calcola "available" = PV - (house - ev)                      │
│  • Applica la modalità (eco/balanced/boost_*/fast/off)          │
│  • Isteresi, soglie min, limiti corrente wallbox                │
│  • Emette FlowSnapshot → listeners                              │
└──────┬──────────────────┬─────────────────────┬─────────────────┘
       │                  │                     │
       ▼                  ▼                     ▼
┌──────────────┐   ┌───────────────┐   ┌─────────────────────┐
│ EvController │   │ Notification  │   │   Entità Platforms  │
│ set_value A  │   │ Dispatcher    │   │  sensor / binary    │
│ turn_on/off  │   │ notify.*      │   │  number / switch    │
│              │   │ persistent_*  │   │  select             │
└──────────────┘   └───────────────┘   └──────────┬──────────┘
                                                  │
                                                  ▼
                                      ┌───────────────────────┐
                                      │  Lovelace Custom Card │
                                      │   solar-charge-card   │
                                      └───────────────────────┘
```

## FlowSnapshot

Il cuore del sistema è il `FlowSnapshot` prodotto dal coordinator:

```python
FlowSnapshot(
    pv_power, house_power, grid_power, battery_power, battery_soc,
    ev_power, surplus,
    recommended_ev_power, recommended_ev_current, battery_allocation,
    mode, overconsumption, charge_complete
)
```

Tutte le entità (sensor/binary/number/select/switch) sono derivate dallo stesso snapshot, garantendo coerenza atomica tra numeri e card.

## Sign conventions (normalizzate)

| Grandezza | Segno | Significato |
|---|---|---|
| `grid_power` | > 0 | import dalla rete |
| `grid_power` | < 0 | export verso la rete |
| `battery_power` | > 0 | batteria in carica |
| `battery_power` | < 0 | batteria in scarica |

La configurazione permette di invertire i segni in ingresso in base al tuo inverter.

## Estendibilità

- Nuova modalità: aggiungi la costante in `const.py`, branch in `Coordinator._compute_recommendation`, opzione in `strings.json`.
- Nuovo canale notifica: aggiungi il servizio notify al flow `notify_targets`.
- Nuova lingua: copia `translations/en.json` in `<lang>.json`.
