"""Logica di dominio per i template dei piani finanziari (FASE E1).

Questo modulo ospita (per il task successivo di seed/endpoint) le interfacce
concordate nel piano 2026-07-19-ui-completamento (Task E1.1/E1.2):

- ``TEMPLATE_SEED: list[dict]`` — costanti seed: almeno un template generico
  per fondo presente nel DB reale (``formazienda``, ``fapi``, ``fondimpresa``)
  con voci standard docenza/tutoraggio/coordinamento/materiali. Ogni elemento
  ha la stessa forma del modello: ``nome``, ``descrizione``, ``tipo_fondo``,
  ``ente_erogatore``, ``versione``, ``struttura_voci``.
- ``seed_templates(db) -> int`` — idempotente: inserisce solo i
  ``(nome, versione)`` assenti e ritorna il numero di inserimenti.
  Nessun seed dentro le migration (coerente con catena greenfield NEW-003).
- ``crea_piano_da_template(db, template_id, progetto_id, testata, user)``
  → ``models.PianoFinanziario`` con voci strutturate dal template.

Il modello dati è ``models.PianoFinanziarioTemplate`` (migration 060).
Qui, in Task E1.1, il modulo è volutamente solo progettato: le funzioni
verranno implementate RED→GREEN nel task dedicato (nessuna implementazione
parziale nascosta).
"""

from __future__ import annotations

__all__ = ["TEMPLATE_SEED", "seed_templates", "crea_piano_da_template"]

#: Popolato dal task di seed (vedi docstring di modulo).
TEMPLATE_SEED: list[dict] = []


def seed_templates(db) -> int:
    """Inserisce i template di ``TEMPLATE_SEED`` assenti. Non ancora implementato."""
    raise NotImplementedError("seed_templates: implementazione nel task E1 successivo (seed/endpoint)")


def crea_piano_da_template(db, template_id: int, progetto_id: int, testata: dict, user):
    """Crea un PianoFinanziario dalle voci del template. Non ancora implementato."""
    raise NotImplementedError("crea_piano_da_template: implementazione nel task E1 successivo (seed/endpoint)")
