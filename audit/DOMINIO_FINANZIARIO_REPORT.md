# AUDIT DOMINIO FINANZIARIO — REPORT FINALE

> Le analisi intermedie D1–D5 sono conservate nell'archivio locale protetto `/DATA/progetti/pythonpro-local-archive/2026-07-17_audit_raw`; Git mantiene questo report conclusivo e le decisioni applicative risultanti.

Data: 2026-07-15 · Perimetro: catena Piani Finanziari → Progetti → Collaboratori → Assegnazioni → Presenze → Timesheet → Contratti/Reporting.
Metodo: D1 mappa dominio (statico) · D2 audit dati DB reale (16 query, sola lettura) · D3 verifica logica (codice + prove di calcolo) · D4 scenari E2E via API su DB copia · D5 completezza funzionale.
Dettagli e prove: `DOMINIO_FINANZIARIO_D1_mappa.md` … `D5_completezza.md` (stessa cartella). Nessuna modifica applicata: solo audit.

---

# 1. VERDETTO

### a) La logica della catena è corretta?

**Il motore di calcolo sì, il perimetro di controllo no.**

Dove SÌ — verificato al centesimo (D4 S1): il flusso lineare presenza → ore assignment → voce piano → riepilogo produce numeri esatti (14h×60 = 840,00; totali, percentuali, ore frazionarie corrette). Aggancio automatico assignment→voce, ricalcoli su correzione/cancellazione presenza, multi-tariffa: funzionano.

Dove NO — tre categorie di difetto logico:
1. **Un errore di calcolo sistematico:** il budget utilizzato memorizzato è SEMPRE indietro dell'ultima presenza registrata (bug autoflush, riprodotto deterministicamente 3 volte). Il residuo budget che il sistema mostra non è mai giusto mentre si lavora.
2. **Contraddizioni interne:** due regole percentuali incompatibili tra loro (A≤20% come alert, A≥70% come blocco) applicate a tutti i fondi indistintamente — nessun piano può rispettarle entrambe, e il blocco per giunta non blocca (valida DOPO il salvataggio: errore al client, dato salvato).
3. **Assenza di perimetro:** nessun vincolo lega presenze e assegnazioni alle date e allo stato del progetto (il 100% delle presenze nel DB è fuori dal periodo del proprio progetto); modifiche retroattive (ore, tariffe, cancellazione collaboratori) riscrivono i consuntivi passati senza avviso; nessuno stato congela niente.

### b) I numeri prodotti sono affidabili per la rendicontazione ai fondi OGGI?

**NO.** Non per un difetto di aritmetica, ma perché nessun numero è stabile:

- Il timesheet "bloccato" si rigenera con `?rigenera=true` producendo un secondo PDF ufficiale con totali diversi dal primo (provato: 14h → 12h); le presenze sottostanti restano modificabili; i totali del timesheet non sono nemmeno salvati in DB (solo il file PDF).
- Il consuntivo di un piano rendicontato cambia se dopo l'invio qualcuno: modifica una tariffa (ricalcolo retroattivo), disattiva un collaboratore (le sue ore spariscono dal riepilogo), registra una presenza su progetto persino annullato (accettata, provato).
- L'`importo_presentato` — ciò che è stato dichiarato al fondo — viene sovrascritto ad ogni ricalcolo: il valore storico presentato non esiste da nessuna parte.
- Aritmetica in float con arrotondamento bancario: divergenze da 1 centesimo rispetto ai fogli di verifica dei fondi sono matematicamente attese (dimostrato: 10,5h×33,33 → 349,96 vs 349,97).
- Il sistema massimali è di fatto spento (tassonomia fondi mai corretta nei dati, nessun controllo sulla tariffa dell'assignment: 900 €/h di docenza accettati senza obiezioni).

In sede di verifica del fondo, ognuno di questi punti è una decurtazione potenziale. Usabile oggi SOLO con procedura organizzativa esterna: congelare manualmente (export + archiviazione) al momento dell'invio e vietare per policy ogni modifica successiva — il software non lo garantisce.

### c) Le operazioni d'ufficio sono tutte eseguibili?

**NO.** Cinque mancanze, una delle quali blocca l'operatività quotidiana:

1. **Stesso docente su 2 progetti nello stesso periodo: impossibile** (rifiutato dal sistema). È il caso più comune di un ente di formazione. Il blocco è sul periodo contrattuale invece che sull'orario effettivo.
2. Chiudere/congelare un progetto o piano: lo stato cambia, gli effetti non esistono.
3. Duplicare piano/progetto per la nuova annualità: nessuna funzione.
4. Pacchetto di rendicontazione per il fondo: il generatore esiste (`rendicontazione_generator.py`) ma è codice morto, non collegato a nulla.
5. Storico modifiche: l'audit esiste solo per i piani, non è consultabile da nessuna interfaccia, e presenze/assegnazioni non sono tracciate affatto.

---

# 2. REGISTRO FINDING

Severità: 🔴 errore di logica/calcolo · 🟠 buco funzionale · 🟡 fragilità · 🟢 migliorabile.
Prove: riferimenti file:riga e fasi (D2 = dato reale, D4 = provato live).

| ID | Sev | Finding | Prova | Impatto operativo/economico |
|----|----|---------|-------|------------------------------|
| DOM-01 | 🔴 | `budget_utilizzato`/`budget_rimanente` sempre indietro dell'ultima presenza: sessione `autoflush=False` (database.py:122) + SUM SQL prima del flush (crud.py:4340-4346) | D4 S1 riprodotto 3× (960/1020, 1020/1320, 900/1050); D2 A8 (Δ 3.100 € nei dati) | Ogni decisione presa sul residuo budget è presa su un numero sbagliato |
| DOM-02 | 🔴 | Nessun vincolo presenze/assignment ⊂ date progetto; nessun blocco su stato progetto (presenze accettate su progetto annullato o finito da mesi) | D2 A4 (7/7 presenze fuori range), D4 S3.2b, S5.3; crud.py:1359-1490, 845-860 | Ore fuori periodo autorizzato = spesa non riconosciuta in verifica → decurtazione |
| DOM-03 | 🔴 | Modifiche retroattive senza guardie: riduzione ore assignment non ricontrolla presenze; cambio `hourly_rate` ricalcola il consuntivo passato | D2 A1 (20h su 10h nei dati), D4 S2; crud.py:1932-1990, 4258-4282 | Consuntivi già rendicontati cambiano silenziosamente |
| DOM-04 | 🔴 | Stesso collaboratore su 2 progetti con periodi sovrapposti: vietato (blocco su periodo, non su orario) | D4 S4.3; crud.py:1261-1312 | Operatività quotidiana bloccata; workaround = falsificare date contrattuali |
| DOM-05 | 🔴 | Regole percentuali contraddittorie: `MACROVOCE_LIMITS` A≤20/B≤50/C≤30 (alert) vs `validate_sezioni_percentuali` A≥70/C≤20/D≤10 (blocco), identiche per ogni fondo | piano_finanziario_config.py:5-10 vs 84-102; D2 A10 (entrambe violate nei dati); D4 S3.4 | Piani reali non modificabili via API; regole di fondi diversi mescolate |
| DOM-06 | 🔴 | Validazione DOPO il commit: 422 al client con voce già persistita (create/update/delete voce) | routers/piani_finanziari.py:296-297,343,382 + crud.py:4374; D4 S3.4 (voce 264 nel DB dopo errore) | Il piano risulta "protetto" ma è corrotto; l'operatore crede che il salvataggio sia fallito |
| DOM-07 | 🔴 | Timesheet non è uno snapshot affidabile: `?rigenera=true` bypassa il blocco; totali non persistiti in DB (solo PDF su file); presenze incluse modificabili; `sbloccato_da` stringa client | routers/timesheet.py:106-125, 158-177; D4 S3.5, S3.7 (due PDF "bloccati": 14h e 12h) | Documento consegnato al fondo ≠ dati interni; contestazione in verifica |
| DOM-08 | 🔴 | Nessuna macchina a stati: `rendicontato`/`chiuso`/`cancelled` non congelano nulla; transizioni libere (chiuso→bozza) | models.py:854-876; D4 S5.3 | I dati inviati al fondo restano modificabili per sempre |
| DOM-09 | 🔴 | Soft-delete collaboratore disattiva le sue assignment (senza controllo presenze) e i filtri `is_active` fanno sparire le sue ore dal consuntivo live | crud.py:445-465, 4588-4591, 4820-4822 | Cancellare una persona riscrive la rendicontazione passata |
| DOM-10 | 🔴 | Massimali strutturalmente spenti: lookup per `tipo_fondo` mai valorizzato correttamente (4/4 piani 'altro'), nessun check su `hourly_rate` assignment né sul percorso automatico, `categoria` NULL esente | routers/piani_finanziari.py:26-44; D2 A11/A16; D4 S3.6 (900 €/h accettati) | Tariffe oltre massimale → taglio integrale della voce in verifica |
| DOM-11 | 🔴 | Ore e importi in `Float` su tutta la catena; arrotondamento bancario; `completed_hours` NULL manda in TypeError la property `remaining_hours` | models.py:813-816, 935-943, 445; prove D3 (round(2.675,2)=2.67; 10.5×33.33→349.96); D2 A2 | Derive da centesimo vs fogli del fondo; crash latente |
| DOM-12 | 🔴 | Nessun audit trail su presenze/assignment/voci (0 righe); audit dei piani scritto ma non esposto da alcun endpoint | D4 S5 (query audit_logs); models.py:1914 | Impossibile dimostrare chi/quando ha corretto un dato di rendicontazione |
| DOM-13 | 🔴 | Riepilogo sovrascrive gli importi manuali delle voci fisse con aggregati dalle assignment; Excel con dettaglio (voci persistite) e totali (ricalcolo live) da fonti diverse nello stesso file | crud.py:4644-4649; routers/piani_finanziari.py:90 vs 485 | Excel consegnabile internamente incoerente |
| DOM-14 | 🔴 | `create_attendance` non atomica: 4 commit separati, errori dei ricalcoli degradati a warning | crud.py:1472-1483; è il meccanismo di D2 A8 | Aggregati che divergono silenziosamente dalla verità |
| DOM-15 | 🟠 | Presenze senza assignment: ammesse, nessun tetto ore, invisibili a voci e timesheet | crud.py:1444-1468; D2 A7 (16h reali), D4 S3.2 | Ore erogate che non rendicontano; nessun controllo di spesa |
| DOM-16 | 🟠 | `rendicontazione_generator.py` (pacchetto ZIP per fondo) è codice morto: mai importato | grep D5 | Il deliverable finale per il fondo non è producibile dal sistema |
| DOM-17 | 🟠 | Nessuna duplicazione piano/progetto per nuova annualità | grep D5 | Ricreazione manuale integrale ogni anno |
| DOM-18 | 🟠 | `importo_presentato` sovrascritto ad ogni ricalcolo (= consuntivo corrente) | models.py:1033; crud.py:4392-4395 | Il valore storicamente presentato al fondo non è conservato |
| DOM-19 | 🟠 | `Project.ore_totali/ore_completate/progress` ricalcolati solo dal CRUD presenze → stale dopo ogni modifica assignment | crud.py:1492-1524; D2 A3 (3/5 progetti stale) | Viste avanzamento inaffidabili |
| DOM-20 | 🟠 | DELETE assignment con presenze → 500 "Errore interno" invece del messaggio di business | D4 S2.1; routers/assignments.py:323 | Operatore cieco sul da farsi |
| DOM-21 | 🟠 | Anti-overlap presenze solo applicativo (nessun EXCLUDE constraint DB → race condition); su update parziale il ricontrollo salta se cambiano solo date/ore | crud.py:1575-1577; models.py:403 | Doppie presenze concorrenti possibili |
| DOM-22 | 🟠 | UPDATE presenza senza i validator del create (futuro max +7gg, passato max 1 anno, sanitizzazione) | routers/attendances.py:145-167 vs validators.py:242-285 | Correzioni possono introdurre date assurde |
| DOM-23 | 🟡 | `progress_percentage` cap a 100 nasconde gli sforamenti (200% reale mostrato come 100%) | crud.py:1511,1542 | Eccessi invisibili nei cruscotti |
| DOM-24 | 🟡 | Tetto ore voce disattivo se `ore_previste=0`; doppio tetto (assignment vs voce) non sincronizzato | routers/attendances.py:38 | Tetti che si contraddicono o non scattano |
| DOM-25 | 🟡 | Alert macrovoce B>50% inevitabile su piani solo-docenza → rumore che desensibilizza | D4 S1.7 | Alert reali ignorati per assuefazione |
| DOM-26 | 🟡 | Anonimizzazione GDPR + rigenerazione timesheet = PDF con nome anonimo | services/gdpr_service.py:39 | Timesheet inutilizzabile se rigenerato dopo anonimizzazione |
| DOM-27 | 🟡 | Dati piano fragili: `data_inizio=data_fine` di default (2 casi reali), `codice_piano` NULL (2 casi), tassonomia `tipo_fondo` senza formazienda/fapi | models.py:819-820, 805-806; D2 A13/A15 | Range temporali vuoti, identificazione debole |
| DOM-28 | 🟡 | `hours` fornibile dal client indipendente da end−start | crud.py:1411-1415 | Ore dichiarate ≠ orari dichiarati possibili |
| DOM-29 | 🟢 | Timesheet: layout unico proprietario, config per fondo limitata alle firme; nessun modello ufficiale Formazienda/FAPI/Fondimpresa | timesheet_generator.py:21-46 | Rilavorazione manuale a ogni invio |
| DOM-30 | 🟢 | Riconciliazione limitata a preventivo vs consuntivo: gli stadi approvato/presentato/validato non hanno report; nessun report cross-piano | D5 §8 | Riconciliazione annuale a mano |

---

# 3. ANOMALIE NEI DATI REALI (D2) E PROPOSTA DI BONIFICA

Contesto: il DB attuale contiene dati di sviluppo/test (7 presenze totali). Nessun danno economico reale — ma la bonifica serve comunque se questi dati diventano base della produzione. **Query DA SOTTOPORRE, non eseguite.**

Anomalie trovate (12 classi, dettagli in D2): eccesso ore assignment 46; `completed_hours` NULL; `ore_totali` stale 3/5 progetti; 7/7 presenze fuori date progetto; 2 presenze senza assignment; `budget_utilizzato` disallineato di 3.100 €; 27 voci `rendicontato` incoerenti; `tipo_fondo='altro'` ovunque; tariffa 1.000 €/h; piani con range date vuoto; 2 `codice_piano` NULL; 27 voci con importi senza categoria.

### Query correttive proposte (ordine di esecuzione)

```sql
-- B1. Riallineare completed_hours dalle presenze (fix NULL e stale)
UPDATE assignments a SET completed_hours = COALESCE(s.h, 0)
FROM (SELECT assignment_id, SUM(hours) h FROM attendances GROUP BY assignment_id) s
WHERE s.assignment_id = a.id OR a.completed_hours IS NULL;
-- (variante completa: LEFT JOIN per azzerare anche chi non ha presenze)

-- B2. Riallineare ore progetti
UPDATE projects p SET
  ore_totali    = COALESCE((SELECT SUM(assigned_hours) FROM assignments WHERE project_id=p.id AND is_active), 0),
  ore_completate= COALESCE((SELECT SUM(hours) FROM attendances WHERE project_id=p.id), 0);

-- B3. Riallineare budget piani dalle voci
UPDATE piani_finanziari pf SET
  budget_utilizzato = COALESCE((SELECT SUM(importo_consuntivo) FROM voci_piano_finanziario WHERE piano_id=pf.id), 0),
  budget_rimanente  = pf.budget_totale - COALESCE((SELECT SUM(importo_consuntivo) FROM voci_piano_finanziario WHERE piano_id=pf.id), 0);

-- B4. Tassonomia fondi (PREREQUISITO: estendere i valori ammessi in models.py:849)
UPDATE piani_finanziari SET tipo_fondo='formazienda' WHERE lower(ente_erogatore) LIKE '%formazienda%' AND tipo_fondo='altro';
UPDATE piani_finanziari SET tipo_fondo='fapi'        WHERE lower(ente_erogatore) LIKE '%fapi%'        AND tipo_fondo='altro';

-- B5. Codici piano mancanti
UPDATE piani_finanziari SET codice_piano = 'PF-'||progetto_id||'-LEGACY-'||id WHERE codice_piano IS NULL;
```

### Decisioni umane richieste (non automatizzabili)
| Caso | Opzioni |
|---|---|
| 7 presenze fuori date progetto 1 | (a) correggere date progetto, (b) spostare presenze, (c) marcare progetto come test e archiviare |
| Presenze 1-2 senza assignment | collegarle all'assignment 1 (stesso collab/progetto) o eliminarle |
| Assignment 46: 20h su 10h + tariffa 1.000 €/h | dato di test: eliminare o correggere assigned_hours/tariffa |
| 27 voci piano 1 `rendicontato` con tariffa 0 e presentato 0 | piano di test in `bozza`: riportare voci a `previsto` o archiviare il piano |
| Piani 1-2 con data_inizio=data_fine | valorizzare date reali |

---

# 4. PIANO DI CORREZIONE (proposta ondata "DOMINIO FINANZIARIO")

Effort: S <½g · M 1–3g · L >3g. Ordinato per impatto; le dipendenze sono indicate.

### Wave 1 — Il conto torna (integrità del calcolo)
| # | Intervento | Finding | Effort | Dipendenze |
|---|---|---|---|---|
| 1.1 | Fix sync budget: `db.flush()` prima delle SUM in `aggiorna_budget_utilizzato`/`aggiorna_voce_da_presenze` (o expire_all) + bonifica B3 | DOM-01 | S | — |
| 1.2 | Transazione unica su create/update/delete presenza (un solo commit; niente errori→warning) e validazione voci PRIMA del commit nel router | DOM-14, DOM-06 | M | — |
| 1.3 | Guardie di propagazione: `assigned_hours < completed_hours` → 422; cambio `hourly_rate` con consuntivi → richiede flag esplicito `ricalcola_consuntivo`; update date progetto con presenze/assignment fuori → 422 con elenco | DOM-03 | M | 1.2 |
| 1.4 | Vincolo presenze/assignment ⊂ date progetto + blocco scritture su progetto non-active e piano rendicontato/chiuso | DOM-02, DOM-08 (parte) | M | 1.2 |
| 1.5 | Sbloccare il multi-progetto: eliminare il veto di periodo cross-progetto (`check_assignment_overlap`), tenere solo anti-overlap ORARIO presenze + constraint DB `EXCLUDE USING gist (collaborator_id WITH =, tsrange(start_time,end_time) WITH &&)` | DOM-04, DOM-21 | M | — |
| 1.6 | Bonifiche B1, B2, B5 + decisioni umane §3 | dati | S | 1.1 |

### Wave 2 — Il numero inviato non cambia più (rendicontazione affidabile)
| # | Intervento | Finding | Effort | Dipendenze |
|---|---|---|---|---|
| 2.1 | Timesheet snapshot vero: persistere righe+totali in tabella; generazione = congela le presenze incluse (flag/blocco modifica); `rigenera` solo dopo unlock; unlock = utente autenticato + motivo, audit | DOM-07 | L | 1.2 |
| 2.2 | Macchina a stati piano: `rendicontato`/`chiuso` → voci e presenze collegate read-only; `importo_presentato` congelato allo stato `inviato` (colonna storica separata) | DOM-08, DOM-18 | M | 1.4 |
| 2.3 | Regole per fondo: tassonomia `tipo_fondo` estesa (formazienda, fapi, fondimpresa) + bonifica B4; percentuali e massimali configurati PER fondo; risolvere la contraddizione A≥70 vs A≤20 col dominio (Formazienda: limiti macrovoce 20/50/30; la regola A≥70 appartiene ad altro schema — verificare con l'ufficio a quale fondo va applicata); massimali anche su `hourly_rate` assignment e percorso automatico | DOM-05, DOM-10 | M | — |
| 2.4 | Collaboratori: vietare disattivazione con assignment con presenze (o mantenerne le ore nei consuntivi: rimuovere filtro `is_active` dai calcoli storici) | DOM-09 | S/M | — |
| 2.5 | Migrazione `Float`→`Numeric(12,2)` su importi e `Numeric(6,2)` su ore; arrotondamento `ROUND_HALF_UP` centralizzato; NOT NULL su completed_hours | DOM-11 | L | 1.* |
| 2.6 | Audit trail esteso: presenze, assignment, voci (create/update/delete con old/new) + endpoint di consultazione + UI storico | DOM-12 | M | — |

### Wave 3 — Il lavoro d'ufficio completo
| # | Intervento | Finding | Effort |
|---|---|---|---|
| 3.1 | Collegare `rendicontazione_generator` a endpoint+UI; modelli timesheet per fondo | DOM-16, DOM-29 | M |
| 3.2 | Duplica piano/progetto per annualità (copia struttura, azzera consuntivi) | DOM-17 | S |
| 3.3 | Report riconciliazione 5 stadi (preventivo/approvato/consuntivo/presentato/validato) per piano e cross-piano | DOM-30 | M |
| 3.4 | Fix minori: DELETE assignment → 409 con messaggio; validator su UPDATE presenza; `hours` derivato server-side da end−start; rimozione cap 100%; presenze senza assignment → obbligo assignment o warning bloccante; tetto voce anche con ore_previste=0; alert per fondo; guard GDPR su rigenerazione timesheet | DOM-15, 20, 22, 23, 24, 25, 26, 28 | M |
| 3.5 | Trigger ricalcolo `ore_totali` anche da CRUD assignment | DOM-19 | S |

Totale stimato: Wave 1 ≈ 5-7g · Wave 2 ≈ 8-12g · Wave 3 ≈ 5-7g.

**Priorità assoluta se si va in produzione prima delle wave:** 1.1 (budget sbagliato sempre), 1.4 (presenze fuori periodo = decurtazione certa), 2.1 (timesheet instabile), 1.5 (operatività bloccata).

---

*Audit eseguito read-only. DB reale mai modificato; scenari su copia `gestionale_audit` (creata da dump, eliminata a fine test). Nessuna correzione applicata: il piano sopra è da pianificare insieme.*
