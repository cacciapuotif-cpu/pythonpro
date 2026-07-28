# UX-6b — GATE dominio codici progetto per beneficiaria

**Stato:** aperto, in attesa di conferma utente

**Data:** 2026-07-28

**Regola:** nessuna migration o persistenza dei codici/importi/partecipanti
prima della conferma.

## Evidenza reale

Il progetto/piano 11 ha codice `20250611CMIA001`. La convenzione contiene
cinque righe aziendali e cinque codici figli:

| Codice | Partecipanti | Totale |
|---|---:|---:|
| `20250611CMIA00101` | 9 | € 9.882,36 |
| `20250611CMIA00102` | 9 | € 10.376,47 |
| `20250611CMIA00103` | 6 | € 11.747,90 |
| `20250611CMIA00104` | 15 | € 13.563,03 |
| `20250611CMIA00105` | 4 | € 5.672,27 |

La somma è € 51.242,03, cioè il costo totale del piano. Sono quindi
interventi/progetti aziendali dentro lo stesso piano finanziato, non cinque
nuovi record `Project` di primo livello.

## Perché il modello corrente non basta

- `AziendaClienteProjectLink` dice che un'azienda partecipa al piano e conserva
  dati di regime di aiuto, ma non rappresenta il progetto aziendale.
- `ModuloFormativo.codice_progetto_fapi` ripete il codice sui moduli; sul dato
  reale `azienda_beneficiaria_id` è nullo, quindi il codice non è agganciato
  alla beneficiaria.
- Mettere tre colonne sul link azienda-piano sarebbe semplice ma imporrebbe
  un solo codice per azienda. Non abbiamo una regola validata che garantisca
  questa cardinalità per tutti i fondi e tutti gli avvisi.

## Modello proposto

Nuova entità generica `InterventoBeneficiario`:

- `id`
- `project_id` — il piano/progetto gestionale padre
- `azienda_cliente_project_link_id` — beneficiaria nel piano
- `codice_progetto_fondo` — codice esterno, non hardcoded FAPI
- `titolo` nullable
- `partecipanti_approvati` nullable
- `costo_totale` nullable
- `contributo_fondo` e `cofinanziamento` nullable, già disponibili
  nell'Allegato A e utili al controllo della somma
- `documento_fonte_id` nullable — versione della convenzione da cui proviene
- timestamp e stato

Vincoli:

- unique `(project_id, codice_progetto_fondo)`;
- nessun unique sulla sola beneficiaria: una beneficiaria può avere più
  interventi;
- importi non negativi, partecipanti non negativi;
- `ModuloFormativo.intervento_beneficiario_id` nullable con backfill per codice;
- il vecchio `codice_progetto_fapi` resta temporaneamente per compatibilità e
  viene qualificato prima di qualsiasi rimozione.

## Comportamento upload dopo approvazione

- match beneficiaria prima per P.IVA/C.F., poi per ragione sociale normalizzata;
- upsert dell'intervento per codice dentro il piano;
- mai duplicare `AziendaClienteProjectLink`;
- differenze su codice, partecipanti o importi mostrate e applicate solo se
  selezionate;
- i moduli con lo stesso codice vengono collegati all'intervento;
- somme di interventi confrontate con costo/contributo/cofinanziamento del
  piano, con warning su scostamenti e mai correzione silenziosa.

## Decisione richiesta

Confermare o correggere questi due punti:

1. `InterventoBeneficiario` separato è preferito alle colonne sul link
   azienda-piano.
2. Il valore `Totale` dell'Allegato B va registrato come `costo_totale`
   dell'intervento; `Finanz.` e `Cofinanz.` restano due componenti distinte.
