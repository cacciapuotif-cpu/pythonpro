# MOB-3 — Elenchi responsive

**Data:** 2026-07-30  
**Stato:** completato  
**Regola desktop:** invariata a 1280, 1440 e 1920 px

## Architettura

`ResponsiveEntityList` riceve una sola collezione e monta una sola
rappresentazione: tabella/griglia densa su desktop, card impilate su mobile.
Fetch, filtri, RBAC e azioni restano nei manager; non esistono copie mobili
della logica applicativa. Il breakpoint JavaScript è letto dal token CSS
`--breakpoint-mobile-max`, esportato dal registro Sass unico.

`ResponsivePagination` mantiene i controlli di pagina desktop e presenta
“Carica altri” su smartphone. `useResponsivePageItems` accumula le pagine e
deduplica per ID. Le proposte agenti, già caricate come collezione client-side,
sono rese a blocchi di 20 su mobile.

`ResponsiveFilters` mantiene ricerca e accesso ai filtri visibili, sposta i
filtri secondari in un bottom sheet mobile con contatore, azzeramento, focus
iniziale, focus trap, Escape e chiusura tramite Back/gesture.

## Matrice campi card

| Entità | Campi mobili principali | Azione primaria |
|---|---|---|
| Collaboratore | nome/ruolo, stato documenti, progetti attivi, stato operativo | dettaglio documenti |
| Allievo | nome/stato, azienda/sede, progetti, contatto | chiamata, se disponibile |
| Progetto | titolo/stato, avviso-fondo, scadenza, partecipanti | dettaglio espandibile |
| Azienda | ragione sociale/stato, sede, fondo, progetti, referente | chiamata, se disponibile |
| Ordine | numero/stato, cliente, origine, data | completa, se consentito |
| Preventivo | numero/stato, cliente, oggetto, scadenza, totale | dettaglio |
| Avviso | titolo/stato, codice, fondo, ente | apri |
| Proposta agente | titolo/priorità, entità, stato, agente/data | leggi e revisiona |
| Documenti | collaboratore/urgenza, tipi aperti, scadenza vicina, email | invia sollecito |

Le azioni distruttive sono separate e marcate; sulle proposte agenti
l’approvazione non è disponibile direttamente dalla card mobile: si apre
prima il dettaglio.

## Correzioni funzionali emerse

- `NEW-046` chiuso: gli allievi oltre pagina 1 sono ora raggiungibili.
- `NEW-047` chiuso: i progetti sono caricati in batch fino a esaurimento e i
  filtri stato non lavorano più sul primo blocco da 100.
- `NEW-048` resta aperto per MOB-6: il manager Collaboratori usa ancora il
  Context per lookup/CRUD e la fonte paginata per la lista; le due rese
  responsive della lista usano comunque una sola fonte.
- `NEW-049` chiuso: il test backup SQLite attende ora `.db.zip.gpg`.

## Verifiche

- Frontend: **39 suite / 320 test / 3 snapshot** previsti al commit finale
  (il dato definitivo è registrato in `STATUS.md`).
- Build produzione: verde.
- Playwright reale: **4 profili × 21 sezioni + 4 flussi pubblici**, zero
  overflow e zero resa responsive doppia; per ogni lista popolata il report
  verifica layout atteso e assenza di ID duplicati.
- Mobile: iPhone SE 375 px.
- Desktop: 1280, 1440 e 1920 px.
- Evidenze JSON e screenshot:
  `frontend/test-results/responsive-layout/` (artefatti locali ignorati da Git).

## Esito

MOB-3 è superato. Le nove famiglie di elenco hanno una resa mobile usabile
senza rimuovere o semplificare la resa desktop. Restano a MOB-6 la
consolidazione della doppia sorgente Collaboratori e la paginazione server-side
degli endpoint che oggi restituiscono collezioni ampie.
