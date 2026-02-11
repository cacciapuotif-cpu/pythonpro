# FIX TEMPORANEO - Assegnazioni Non Salvano

## Problema Identificato

Il POST `/assignments/` va in **timeout/deadlock** a causa di:
1. ❌ `SafeTransaction` con doppio commit causava deadlock
2. ❌ `@retry_on_db_error` decorator rallentava le richieste
3. ❌ `EnhancedAssignmentCreate` con validazioni pesanti su database

## Soluzione Implementata

L'endpoint è stato semplificato rimuovendo:
- SafeTransaction wrapper
- retry_on_db_error decorator
- EnhancedAssignmentCreate validations

Usa ora `schemas.AssignmentCreate` diretto con commit manuale.

## Test Manuale (se serve)

### Crea assegnazione via SQL diretto:

```bash
docker exec pythonpro-db-1 psql -U admin -d gestionale -c "
INSERT INTO assignments (
  collaborator_id, project_id, role, assigned_hours,
  start_date, end_date, hourly_rate, created_at
) VALUES (
  1, 1, 'docente', 10.0,
  '2025-10-01', '2025-12-31', 50.0, NOW()
) RETURNING *;"
```

### Verifica assegnazioni:

```bash
docker exec pythonpro-db-1 psql -U admin -d gestionale -c "
SELECT a.id, c.first_name, c.last_name, p.name as project, a.role, a.assigned_hours
FROM assignments a
JOIN collaborators c ON a.collaborator_id = c.id
JOIN projects p ON a.project_id = p.id;"
```

## Prossimi Passi

Una volta che il sistema è stabile, considerare:
1. Ottimizzare le validazioni di BusinessValidator
2. Rivedere SafeTransaction per evitare deadlock
3. Aggiungere timeout configurabili
4. Test di performance su POST /assignments/

## Note

Il backend deve essere riavviato dopo le modifiche:
```bash
docker-compose restart backend
```

Attendere 40 secondi per l'avvio completo e le migrazioni automatiche.
