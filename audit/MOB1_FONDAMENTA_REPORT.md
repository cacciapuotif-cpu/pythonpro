# MOB-1 — Report fondamenta responsive

**Data:** 2026-07-30

**Esito:** completato e verificato sul runtime locale

**Ambito:** fondamenta responsive; la navigazione mobile definitiva è MOB-2

**Commit applicativo:** `24b5ae5`

## Risultato

- Meta viewport: `width=device-width, initial-scale=1, viewport-fit=cover`.
- `box-sizing: border-box` globale, radice e contenitori principali senza
  `min-width` implicito, media fluidi e controlli form limitati alla viewport.
- Safe area iOS centralizzata con `env(safe-area-inset-*)` e applicata a
  header, contenuto, footer e pagine di accesso.
- Testo base esplicito a 16px; su mobile input testuali, select e textarea non
  possono scendere sotto 16px, evitando lo zoom automatico iOS.
- Breakpoint unici in `frontend/src/styles/_breakpoints.scss`:
  telefono `<=480`, mobile `<=768`, tablet `<=1024`, desktop `>=1025`.
  Le 23 stylesheet con query di larghezza sono state migrate a Sass; due
  soglie locali di layout (1120/1180) sono state eliminate con griglie
  intrinseche. Un test statico impedisce la reintroduzione di breakpoint
  locali.
- Il menu desktop riversato non forza più la larghezza del documento a 375px.
  Resta volutamente alto: viene sostituito dal pattern mobile vero in MOB-2.

## Gate browser reale

Harness: Playwright 1.59.1 nell'immagine ufficiale
`mcr.microsoft.com/playwright:v1.59.1-noble`, autenticazione read-only tramite
JWT dell'utente test esistente, senza password né scritture DB.

| Profilo | Viewport | Sezioni autenticate | Flussi pubblici | Scroll documento | Esito |
|---|---:|---:|---:|---:|---|
| iPhone SE | 375×812 | 21/21 | 4/4 | 375px su tutte | PASS |
| Desktop | 1280×900 | 21/21 | 4/4 | 1280px su tutte | PASS |
| Desktop | 1440×900 | 21/21 | 4/4 | 1440px su tutte | PASS |
| Desktop | 1920×1080 | 21/21 | 4/4 | 1920px su tutte | PASS |

Flussi pubblici verificati: login, recupero password, reset password e portale
allievi. Per ogni misura vale:

```text
document.documentElement.scrollWidth <= document.documentElement.clientWidth
document.body.scrollWidth <= window.innerWidth
```

Su mobile sono inoltre verificati meta viewport, applicazione delle safe area
simulate e font dei controlli form `>=16px`.

Evidenze locali rigenerabili:

- `frontend/test-results/responsive-layout/report.json`
- screenshot Home, Calendario e Login per i profili chiave nella stessa
  directory
- comando: `./scripts/run_mobile_layout_gate.sh`

Il gate carica i dati una sola volta per sezione e rimisura lo stesso DOM alle
quattro viewport, per non quadruplicare le API e rispettare il rate limit reale
di 120 richieste/minuto.

## Non regressione e suite

- Frontend: **31 suite, 274 test, 3 snapshot — tutti verdi**.
- Backend: **984 passed, 8 skipped, 0 failed**.
- Build produzione: verde.
- Bundle gzip corrente, utile come baseline provvisoria per MOB-6:
  JavaScript **560.51 kB**, CSS **36.25 kB**.
- Runtime: frontend ricostruito e ricreato; frontend `/` e backend `/health`
  rispondono 200.

## Correzioni baseline emerse

Prima del gate sono stati eliminati i fallimenti ereditati che rendevano la
suite inattendibile: lifecycle globale nei TestClient, percorso ARQ hardcoded,
fixture backup non portabile, riconoscimento SQLite, serializzazione Decimal,
enforcement RBAC nel test e collisione dei dati attendance.

Durante la correzione è stata mitigata `NEW-044`: i nuovi sidecar backup non
salvano più user/password PostgreSQL. Restano da bonificare i sidecar storici e
da valutare la rotazione delle credenziali, quindi il finding non è ancora
chiuso.

## Limiti onesti / prossimo punto

MOB-1 garantisce fondamenta e assenza di scroll orizzontale del documento; non
dichiara ancora PythonPro usabile da smartphone. La navigazione attuale occupa
molto spazio verticale e numerosi contenuti conservano ancora una resa
desktop. Prossimo punto: **MOB-2 — bottom navigation, menu completo,
header compatto, RBAC e back/gesture coerente**.
