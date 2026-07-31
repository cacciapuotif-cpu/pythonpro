# DATE PROGETTO — report di avanzamento

**Stato:** GATE DATE-1 aperto; DATE-2 non iniziato  
**Data:** 2026-07-31  
**Branch:** `claude/platform-audit-compliance-XnH86` (locale, nessun push)

## Prerequisiti verificati

- Letti `STATUS.md`, `audit/FINDINGS_NUOVI.md`, il piano Ondata B e gli ultimi
  15 commit.
- B2 è operativo esclusivamente per massimali/parametri costo: una regola
  avviso validata prevale sul massimale fondo e il 422 cita l'articolo. B2 non
  implementa durate o termini di progetto.
- Schema live Alembic: `070 (head)`.
- Worktree iniziale pulita.
- Backup fresco cifrato:
  `/app/backups/gestionale_backup_pre_date1_20260731_140410.sql.zip.gpg`.
  Verifica applicativa completa (checksum, decifratura, ZIP): `True`.
  SHA-256:
  `a754cd0beebf21c0ad1ad1208cf1af206307cc315340de8de3487bfbe16f1c58`.

## Stato trovato: UX-5 e PRJ-2

UX-5 è stato implementato con migration 064 e servizio
`services/date_progetto.py`, ma rappresenta come campi liberi anche
`data_termine_piano` e `data_termine_rendicontazione`. Questo contraddice il
nuovo dominio, nel quale i termini sono derivati da regola avviso + data di
fatto. Mancano inoltre `data_sottoscrizione`, la distinzione esplicita
`data_avvio_piano_effettiva`, il motore di calcolo, la provenienza e le
proroghe.

Il vincolo presenze UX-5 usa correttamente l'intervallo delle attività
formative quando entrambi gli estremi sono presenti, ma non applica ancora il
termine di conclusione vigente. Cockpit e documenti continuano a usare in più
punti i campi legacy `start_date`/`end_date`. Questi aspetti appartengono a
DATE-4 e non sono stati modificati al gate.

PRJ-2 non risulta iniziato. PRJ-5 ha rimosso i vecchi collegamenti avviso e ha
lasciato il gate dati aperto.

## Censimento live preliminare, sola lettura

Il DB reale contiene due progetti:

| ID | Progetto | Avviso/revisione | Legacy start/end | Nuove date UX-5 | Presenze |
|---:|---|---|---|---|---:|
| 5 | poppi | assenti | 06/04/2026–23/12/2026 | tutte vuote | 0 |
| 11 | MAXI COMMUNICATION | assenti | 21/04/2026–16/02/2027 | tutte vuote | 0 |

`avviso_regole` contiene 0 righe, quindi 0 regole validate. Oggi nessun termine
è calcolabile. Le date legacy non sono state reinterpretate né copiate.

## DATE-1 — struttura proposta e implementata senza migration

`AvvisoRegola` supporta già `valore` JSONB, `tipo_valore` e
`schema_version`. Non serve una nuova tabella o colonna per rappresentare una
regola di durata. Il nuovo valore canonico è:

```json
{
  "tipo": "durata_termine",
  "tipo_termine": "conclusione",
  "ancoraggio": "sottoscrizione",
  "durata": {
    "valore": 12,
    "unita": "mesi"
  },
  "prorogabile": true,
  "tassativo": true,
  "slittamento_giorno_non_lavorativo": "non_specificato"
}
```

Domini chiusi:

- `tipo_termine`: `avvio | conclusione | rendicontazione`;
- `ancoraggio`: `approvazione | sottoscrizione | avvio_piano | fine_attivita`;
- `durata.unita`: `giorni | giorni_lavorativi | mesi`;
- `slittamento_giorno_non_lavorativo`:
  `primo_giorno_utile | nessuno | non_specificato`.

`durata.valore` deve essere un intero positivo. `prorogabile` e `tassativo`
sono chiavi obbligatorie, ma accettano anche `null`: l'assenza di una
disposizione nell'avviso non deve essere trasformata silenziosamente in “no”.
Questa scelta preserva il requisito di non inventare regole.

Aggancio al modello esistente:

- categoria `attuazione` per i termini di avvio e conclusione;
- categoria `rendicontazione` per il termine di rendicontazione;
- `testo_originale` e `riferimento_articolo` obbligatori per la durata;
- `tipo_valore = durata_termine`, `schema_version = 2`;
- tutte le forme valore v1 restano valide e persistono con
  `tipo_valore = oggetto`, `schema_version = 1`.

La correzione umana prima dell'approvazione passa ora dallo stesso schema: non
può validare un ancoraggio o una forma JSON sconosciuti.

## Estrattore

Il prompt del gruppo `gestione` richiede ora il valore strutturato e vieta di
dedurre l'ancoraggio. Se prorogabilità, tassatività o slittamento non sono
esplicitati, usa rispettivamente `null`, `null` e `non_specificato`. Le date
assolute restano nel gruppo dedicato. Il collector conserva il JSON strutturato
nella proposta e l'applicazione resta subordinata alla revisione umana.

## Evidenza RED → GREEN

- Primo RED: 6 fallimenti — tipo `durata_termine` sconosciuto, prompt non
  strutturato, collector degradava il valore a testo.
- Primo GREEN: 7 test mirati passati.
- Secondo RED: la correzione umana con ancoraggio `pubblicazione` veniva
  validata senza errore.
- Secondo GREEN: correzione respinta, regola ancora `proposta`, valore originale
  invariato.
- Regressione avvisi completa completata fino a 35/35 test verdi; un test
  preesistente sul riconoscimento del gruppo scadenze ha individuato una parola
  ambigua nel nuovo prompt, poi rimossa e riverificata.
- Smoke B2 mirato: precedenza regola avviso su massimale fondo verde nel
  container runtime.

La suite globale e la migration non sono richieste al gate intermedio e non
sono dichiarate eseguite. Nessun deploy e nessuna modifica al DB reale.

## GATE DATE-1 — decisione richiesta

Confermare:

1. il valore JSONB `durata_termine` e i domini sopra;
2. `null` come stato onesto “non specificato” per `prorogabile`/`tassativo`;
3. il campo esplicito sullo slittamento, con default `non_specificato`.

Dopo conferma: DATE-2, con motore unico, provenienza e proposta di migration
Alembic da provare prima su copia. Nessuna migration viene scritta prima del
gate.
