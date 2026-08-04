# Deploy PythonPro

La produzione va distribuita esclusivamente con `scripts/deploy.sh`. Non usare
`docker restart`, `docker compose up` o `--force-recreate` manualmente: questi
comandi non garantiscono un rebuild e in passato hanno lasciato backend,
worker e frontend su versioni diverse.

## Procedura standard

Prerequisiti:

- `.env` configurato nella root del repository;
- stack PythonPro gia' raggiungibile;
- Docker Compose 2.24.4 o successivo (`!override` e' richiesto);
- commit da distribuire presente in Git. Le modifiche non committate vengono
  deliberatamente escluse dalla release.

Eseguire:

```bash
./scripts/deploy.sh
```

Lo script esegue, in quest'ordine:

1. archivia esattamente `Git HEAD` in una directory temporanea;
2. crea e verifica un backup PostgreSQL cifrato;
3. salva gli image ID correnti e li tagga `rollback-<timestamp>`;
4. costruisce backend, ARQ worker, scheduler e frontend con commit/data nelle
   label OCI e nelle variabili runtime;
5. applica `alembic upgrade head` con la nuova immagine;
6. ricrea in ordine backend, worker/scheduler e frontend;
7. attende gli health check, verifica i kill switch, l'assenza di bind mount,
   il commit esposto e gli smoke autenticati sui progetti;
8. scrive un manifest non sensibile in `artifacts/deployments/`.

Il profilo `docker-compose.deploy.yml` rimuove i mount del sorgente da `/app`.
Il runtime esegue quindi solo codice incluso nelle immagini; il normale
`docker-compose.yml` conserva i mount utili allo sviluppo locale.

## Verifica versione

Il backend espone:

```bash
curl http://127.0.0.1:8001/health
```

La risposta contiene `commit`, `build_date` e `runtime_source=image`. Lo stesso
commit abbreviato compare nel pie' di pagina dell'interfaccia su porta 3001.
I container e le immagini espongono inoltre la label OCI:

```bash
docker image inspect pythonpro-backend:latest \
  --format '{{index .Config.Labels "org.opencontainers.image.revision"}}'
```

## Rollback

Se build, migration, health o smoke falliscono, `scripts/deploy.sh` esegue il
rollback automaticamente:

- ferma i servizi applicativi;
- se Alembic era avanzato, ripristina il DB dal backup pre-deploy collegandosi
  al database PostgreSQL di manutenzione;
- rimette i tag `latest` sugli image ID precedenti;
- ricrea i servizi e ne verifica la salute.

Per un rollback manuale consultare prima il manifest piu' recente in
`artifacts/deployments/`, quindi usare esclusivamente i tag
`rollback-<timestamp>` registrati. Non ripristinare il DB quando la revisione
Alembic pre/post e' identica.

## Regola di chiusura

Ogni task deve dichiarare `deployato e verificato: SI/NO`. Un task con `NO` e'
completato nel codice ma non e' attivo sul sistema reale e non va descritto
come disponibile all'utente.
