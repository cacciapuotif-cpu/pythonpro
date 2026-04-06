from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path


CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CURRENT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from database import SessionLocal  # noqa: E402
from ai_agents import data_quality  # noqa: F401,E402
from ai_agents.registry import agent_registry  # noqa: E402


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("run_agents")


SCHEDULE_CONFIG = {
    "data_quality": "Ogni giorno alle 06:00",
    "document_reminder": "Ogni giorno alle 08:00",
    "budget_alert": "Ogni lunedi alle 09:00",
}


def run_agent(agent_type: str):
    db = SessionLocal()
    try:
        logger.info("Avvio agente %s", agent_type)
        run = agent_registry.run_agent(db, agent_type=agent_type, triggered_by="scheduler")
        logger.info(
            "Agente %s completato: status=%s items_processed=%s items_with_issues=%s suggestions=%s duration_ms=%s",
            agent_type,
            run.status,
            run.items_processed,
            run.items_with_issues,
            run.suggestions_created,
            run.execution_time_ms,
        )
        return run
    except Exception as exc:
        logger.exception("Errore esecuzione agente %s: %s", agent_type, exc)
        return None
    finally:
        db.close()


def run_all_agents():
    results = []
    for agent_info in agent_registry.list_agents():
        agent_type = agent_info["agent_type"]
        try:
            result = run_agent(agent_type)
            results.append((agent_type, result))
        except Exception as exc:
            logger.exception("Errore non bloccante su agente %s: %s", agent_type, exc)
            results.append((agent_type, None))
    return results


def main():
    parser = argparse.ArgumentParser(description="Esecuzione schedulata agenti AI")
    parser.add_argument("--all", action="store_true", help="Esegue tutti gli agenti registrati")
    parser.add_argument("--agent", type=str, help="Esegue un singolo agente per tipo")
    parser.add_argument("--show-schedule", action="store_true", help="Mostra la configurazione schedule prevista")
    args = parser.parse_args()

    if args.show_schedule:
        for agent_type, schedule in SCHEDULE_CONFIG.items():
            logger.info("%s -> %s", agent_type, schedule)
        return

    if args.all:
        run_all_agents()
        return

    if args.agent:
        run_agent(args.agent)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
