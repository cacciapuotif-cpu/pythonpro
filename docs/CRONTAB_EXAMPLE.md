# Crontab Example

Esempi di pianificazione per il sistema agenti del backend `pythonpro`.

## Agenti schedulati

- `data_quality`: ogni giorno alle `06:00`
- `document_reminder`: ogni giorno alle `08:00`
- `budget_alert`: ogni lunedi alle `09:00`

## Esempio crontab

```cron
0 6 * * * cd /DATA/progetti/pythonpro/backend && /usr/bin/python3 jobs/run_agents.py --agent data_quality >> /var/log/pythonpro_agents.log 2>&1
0 8 * * * cd /DATA/progetti/pythonpro/backend && /usr/bin/python3 jobs/run_agents.py --agent document_reminder >> /var/log/pythonpro_agents.log 2>&1
0 9 * * 1 cd /DATA/progetti/pythonpro/backend && /usr/bin/python3 jobs/run_agents.py --agent budget_alert >> /var/log/pythonpro_agents.log 2>&1
```

## Esecuzione manuale

```bash
python jobs/run_agents.py --all
python jobs/run_agents.py --agent data_quality
python jobs/run_agents.py --show-schedule
```
