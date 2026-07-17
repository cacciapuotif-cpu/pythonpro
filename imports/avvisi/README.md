# imports/avvisi — Avvisi sorgente per ingestione

Depositare qui i file markdown (.md, UTF-8) degli avvisi da ingerire nella
piattaforma (V5 dell'ondata ARCHIVIO AVVISI ingerirà i 4 avvisi reali).

Flusso: `POST /api/v1/avvisi/{avviso_id}/revisioni/ingest` (multipart, ruoli
admin/manager) → pulizia → segmentazione → estrazione LLM (agente
`avviso_extractor`, kill switch `AGENT_AVVISO_EXTRACTOR_ENABLED`) →
suggerimenti in revisione umana → apply che materializza regole/scadenze
validate sulla revisione.

I file qui presenti NON vengono ingeriti automaticamente.
