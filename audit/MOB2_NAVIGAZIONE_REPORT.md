# MOB-2 — Navigazione mobile

**Data:** 2026-07-30  
**Esito:** COMPLETATO  
**Gate precedente:** MOB-0 confermato; MOB-1 verde  
**Push:** nessuno

## Esito

La navigazione desktop riversata su smartphone è stata sostituita, fino a
768px, da un sistema mobile dedicato:

- header sticky compatto con titolo pagina, profilo 44×44px e una sola azione
  contestuale;
- bottom navigation fissa, safe-area aware, con cinque destinazioni;
- “Altro” full-screen con ricerca, focus iniziale/intrappolato, Escape,
  ripristino focus e scroll del contenuto;
- voci prodotte esclusivamente dalla matrice RBAC frontend condivisa;
- URL canonico per tutte le 21 sezioni, navigazione SPA con `push`, filtri con
  `replace` conservativo e ripristino tramite Back/Forward;
- layer critici (Altro, Area personale, presenza, dettaglio proposta agente)
  dismissibili con Back/gesture prima di cambiare pagina.

## Destinazioni confermate

| Ruolo | Bottom navigation |
|---|---|
| Admin | Home · Calendario · Presenze · Proposte · Altro |
| Operatore | Home · Calendario · Presenze · Proposte · Altro |
| Consultazione | Home · Calendario · Persone · Archivio · Altro |

“Presenze” è una destinazione virtuale `/presenze`: riusa `Calendar`, le API e
lo stato esistenti in modalità operativa, con riepilogo odierno e azione
“Registra presenza”. Non duplica la logica del calendario.

## Routing e deep-link

`navigation/sections.json` contiene ora il path canonico di ogni sezione.
Il resolver centrale gestisce inoltre:

- `/presenze` → Calendario in modalità operativa;
- `/collaborators/:id` → scheda collaboratore;
- `/collaborators/:id/documents` → documenti collaboratore;
- alias storico `/collaboratori/:id/documenti`.

I link nei solleciti documentali e nelle proposte agente usano ora percorsi
risolvibili. Una route sconosciuta o vietata viene autorizzata prima del mount
e sostituita con la home del ruolo: il componente vietato non avvia effect/API.
Questo chiude `NEW-045`.

## Verifiche automatiche

### Suite e build

- Frontend completa: **33 suite, 311 test, 3 snapshot, 0 failure**.
- Build produzione: verde.
- Gate MOB-1 rieseguito dopo MOB-2:
  **4 profili × 21 sezioni + 4 flussi pubblici**, verde.
- Backend completo: riportato nel checkpoint/commit MOB-2 al termine
  dell'esecuzione in container.

### Gate browser MOB-2

Comando: `scripts/run_mobile_navigation_gate.sh`.

| Ruolo | Sezioni consentite coperte | Diagnostica browser/API |
|---|---:|---:|
| Admin | 21/21 | 0 |
| Operatore | 19/19 | 0 |
| Consultazione | 18/18 | 0 |

Il gate verifica a 375×812:

- cinque destinazioni esatte per ruolo;
- unione bottom navigation + Altro uguale al set RBAC completo, senza extra;
- raggiungibilità di ogni sezione consentita;
- Altro full-screen, ricerca e chiusura con Back;
- Home → Calendario → terza destinazione → Back → Back;
- target bottom ≥44×44px, barra fissa e nessun overflow orizzontale.

Per non trasformare il crawl di routing in un denial-of-service contro il
limite reale di 120 richieste/minuto, ogni ruolo esegue un bootstrap/API reale
senza errori; durante il solo giro esaustivo delle route le chiamate dati sono
congelate dal browser. I contenuti/API completi delle 21 sezioni restano
coperti dal gate MOB-1 rieseguito separatamente.

Regressione desktop nello stesso browser e DOM:

- 1280px: menu desktop visibile, navigazione mobile non montata;
- 1440px: menu desktop visibile, navigazione mobile non montata;
- 1920px: menu desktop visibile, navigazione mobile non montata.

Artefatti locali ignorati da git:

- `frontend/test-results/mobile-navigation/report.json`;
- screenshot Home per admin, operatore e consultazione;
- `frontend/test-results/responsive-layout/report.json`.

## Limiti onesti / seguito

- MOB-2 risolve l’architettura della navigazione, non converte ancora le
  tabelle in card: è MOB-3.
- I form e tutti i dialog desktop non sono ancora uniformemente full-screen:
  è MOB-4; qui sono stati coperti Back e i layer critici al Livello 1.
- La misurazione e il contenimento del bundle sono MOB-6. Il bundle attuale è
  567.3 kB gzip JS e 36.96 kB gzip CSS; non viene dichiarato ottimizzato.
- Nessun cambiamento infrastrutturale/TLS applicato: MOB-7 resta un gate.

**Dichiarazione MOB-2:** navigazione mobile utilizzabile e coerente sui tre
ruoli: **SÌ**, con contenuti complessi ancora da trasformare nelle fasi MOB-3
e MOB-4.
