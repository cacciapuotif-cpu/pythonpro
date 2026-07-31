# MOB-4 — Form, wizard e modali full-screen

**Data:** 2026-07-31
**Stato:** completato
**Base:** matrice Livelli 1/2/3 già confermata dall'utente in `audit/MOB0_PERIMETRO_MOBILE.md`

## Architettura

Nessun componente React "modal" condiviso: ogni manager mantiene il proprio
markup home-grown, per non riscrivere ~20 file. Due primitive nuove, single
source:

- `frontend/src/styles/_modal-fullscreen.scss` → mixin `fullscreen-shell`,
  incluso in tre punti (`index.scss` per la classe condivisa `.modal-overlay`
  usata da una decina di manager, `AttendanceModal.scss` per
  `.attendance-modal-overlay`, `App.scss` per `.personal-area-overlay`):
  overlay edge-to-edge, box a `width/height: 100%`, `border-radius: 0`,
  padding safe-area. Un solo punto per selettore, nessuna copia del CSS.
- `frontend/src/components/common/DesktopOnlyNotice.js` → guscio per i
  flussi Livello 3: icona, messaggio esplicito, slot `children` per un
  riepilogo read-only opzionale (nome ente, username, titolo progetto...).

## Classificazione applicata (matrice MOB-0)

### Livello 1 — full-screen mobile funzionante
| Flusso | File | Trattamento |
|---|---|---|
| Presenze | `AttendanceModal.js/.scss` | full-screen via mixin, flusso invariato |

### Livello 2 — full-screen mobile funzionante (guscio automatico)
| Flusso | File |
|---|---|
| Area personale | `App.scss` (`.personal-area-overlay`) |
| Assegnazioni | `AssignmentModal.scss` |
| Agenzie, Consulenti, Catalogo, Listini | `*Manager.js` (overlay condiviso) |
| Allievi, Aziende clienti, Collaboratori, Progetti, Ordini, Preventivi | `*Manager.js` (overlay condiviso) |
| Distacco allievo/azienda (percorso normale) | `GestioneAssociati.js` |

Fix locale: `ConsulentiManager.css` aveva `.modal-grid-2` a due colonne fisse
senza collasso mobile — aggiunta media query dedicata (unico file plain CSS
con questo gap reale; gli altri grid-rule trovati usavano `auto-fill`
(già responsive) o `bp.tablet-down` (collasso già presente, mancato dal primo
grep perché cercava solo `bp.mobile`).

### Livello 3 — desktop-only dichiarato (DesktopOnlyNotice)
| Flusso | File | Cosa sparisce su mobile |
|---|---|---|
| Profilo ente attuatore (form completo, sedi, conti, IBAN, logo/carta) | `ImplementingEntityModal.js` | intero form, resta riepilogo ragione sociale |
| Gestione utenti e ruoli | `UserManagement.js` | crea/modifica/elimina; elenco read-only resta, azioni per riga nascoste |
| Piano finanziario progetto (righe, massimali) | `ProgettoMansioneEnteManager.js` | bottone crea + azioni riga nascosti, tabella resta leggibile |
| Wizard piano da template | `PianoTemplateWizard.js` | intero wizard, header/chiusura restano |
| Generazione contratto/template DOCX | `ContractTemplateModal.js` | intero form |
| Upload convenzione/atto, parsing FAPI/Fondimpresa, piano XLSX (7 modal interni) | `FapiUpload.js` | tutti i trigger di upload; `DocumentiProgetto` (elenco già caricato) resta visibile |
| Dissociazione forzata (override admin) | `GestioneAssociati.js` | solo il ramo `forza`; il distacco normale resta L2 |

`FapiUpload.js`: `autoOpenConvenzione` (bivio 409 da `ProjectManager.js`) è
gated anche nell'inizializzatore dello state, non solo nei bottoni — non
si apre da solo su mobile.

## Verifiche

- Frontend completo: **40 suite / 325 test**, 0 falliti (nessuna regressione;
  `isMobile` di default `false` in Jest/JSDOM senza mock `matchMedia`, quindi
  tutti i path desktop pre-esistenti restano gli stessi esercitati prima).
- 4 test nuovi dedicati (`DesktopOnlyNotice.test.js`).
- Build produzione: verde (`main.86c9f3c1.js` locale, +834 B).
- `index.scss` compilato standalone con `sass` CLI: nessun errore di sintassi.

## Confutatore — un difetto reale trovato e corretto in questa sessione

Il primo tentativo di ricostruire il runtime (`docker compose up -d
--force-recreate --no-deps frontend`) **non ha rebuildato l'immagine**:
`--force-recreate` ricrea il container dall'immagine già in cache, non la
ribuilda dal sorgente. Il bundle servito dopo quel comando aveva lo stesso
hash di prima delle modifiche MOB-4 (`main.61d7625e.js`/`main.eab03e3a.css`),
segnale che ha insospettito ed è stato verificato via `docker compose build
frontend` esplicito seguito da `up -d --force-recreate`: solo allora l'hash è
cambiato (`main.5e63a4d8.js`) e il bundle conteneva i marker MOB-4
("Disponibile solo da desktop", "Creazione utenti disponibile da desktop").

**Correzione al record MOB-3**: la chiusura gate MOB-3 (`STATUS.md`,
2026-07-31 mattina) ha usato lo stesso comando senza `build` esplicito.
Non è quindi da escludere che quella verifica runtime abbia servito
un'immagine più vecchia della cache, non il commit `1abafbd`. Il rebuild
reale fatto ora per MOB-4 include comunque tutto lo storico fino a HEAD
(quindi anche MOB-3): il bundle attuale conferma la presenza dei marker
MOB-3 (`"Carica altri"`, `--breakpoint-mobile-max`) **e** MOB-4 nello stesso
artefatto reale. MOB-3 resta quindi confermato live, ma retroattivamente
tramite questo rebuild, non tramite la verifica originale che si è rivelata
inaffidabile.

**Da ricordare per le prossime sessioni**: dopo modifiche al frontend,
il gate runtime deve usare `docker compose build frontend && docker compose
up -d --force-recreate --no-deps frontend`, non `--force-recreate` da solo —
altrimenti si verifica un'immagine stantia senza errori visibili.

- Diff avversariale su `UserManagement.js`/`GestioneAssociati.js`: le guardie
  RBAC (`disabled`, `puoForzare`, `disableDangerousActions`) sono rimaste
  identiche, solo re-indentate dentro il nuovo ramo condizionale — nessuna
  guardia rimossa.
- Runtime post-rebuild reale: `/health` 200 backend e frontend, log container
  puliti, backend non riavviato (zero file backend nel commit MOB-4).

## Limite dichiarato

Nessuna verifica Playwright reale (stesso limite ambientale di MOB-3:
`libatk-1.0.so.0` assente). Copertura sostituita da Jest + grep sul bundle
servito dal container realmente ricostruito.

## Esito

MOB-4 superato. Le tre categorie (full-screen L1/L2 via guscio condiviso,
desktop-only L3 via DesktopOnlyNotice) coprono tutti i modal/wizard censiti
nel repo. Nessuna regressione sui 40/40 suite esistenti.
