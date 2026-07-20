"""Logica di dominio per i template dei piani finanziari (FASE E1).

Interfacce concordate nel piano 2026-07-19-ui-completamento (Task E1.1/E1.2):

- ``TEMPLATE_SEED: list[dict]`` — costanti seed derivate dalle costanti reali
  di ``piano_finanziario_config`` (``VOICE_TEMPLATES`` e
  ``MACROVOCE_LIMITS_BY_FONDO`` via ``get_macrovoce_limits``): un template
  generico versione 1 per ciascun fondo presente nel DB reale
  (``formazienda``, ``fapi``, ``fondimpresa``). Nessuna voce inventata.
- ``seed_templates(db) -> int`` — idempotente: inserisce solo i
  ``(nome, versione)`` assenti e ritorna il numero di inserimenti.
  Nessun seed dentro le migration (coerente con catena greenfield NEW-003).
- ``crea_piano_da_template(db, template_id, progetto_id, testata, user)``
  → ``models.PianoFinanziario`` con voci strutturate dal template (Task E1.2).

Struttura JSON di ``struttura_voci`` (forma canonica dei template seed)::

    {
        "voci": [
            {
                "voce_codice": "B.2",        # da VOICE_TEMPLATES
                "macrovoce": "B",             # da VOICE_TEMPLATES
                "categoria": "docenza",       # derivata con crud._derive_categoria_from_role(descrizione)
                "descrizione": "Docenza",     # da VOICE_TEMPLATES
                "is_dynamic": true            # da VOICE_TEMPLATES
            },
            ...
        ],
        "limiti_macrovoce": {"A": 20.0, "B": 50.0, "C": 30.0, "D": null}
    }

``limiti_macrovoce`` proviene da ``get_macrovoce_limits(tipo_fondo)``:
per i fondi non ancora censiti in ``MACROVOCE_LIMITS_BY_FONDO`` (oggi solo
``formazienda`` è censito) vale il default Formazienda, per decisione
GATE W1.2 / DOM-05 documentata in ``piano_finanziario_config``.

Il modello dati è ``models.PianoFinanziarioTemplate`` (migration 060).
"""

from __future__ import annotations

from copy import deepcopy

import models
from crud import _derive_categoria_from_role
from piano_finanziario_config import VOICE_TEMPLATES, get_macrovoce_limits

__all__ = ["TEMPLATE_SEED", "build_struttura_voci", "seed_templates", "crea_piano_da_template"]

#: Fondi presenti nel DB reale (ricognizione piano E1.1); stessi valori
#: ammessi dal validator ``PianoFinanziario.tipo_fondo``.
_SEED_FONDI = ("formazienda", "fapi", "fondimpresa")


def build_struttura_voci(tipo_fondo: str) -> dict:
    """Deriva la ``struttura_voci`` canonica del template dalle costanti reali.

    Nessun valore inventato: voci da ``VOICE_TEMPLATES`` (categoria derivata
    dalla descrizione con la stessa euristica di produzione), limiti macrovoce
    da ``get_macrovoce_limits`` (fallback Formazienda documentato in config).
    """
    return {
        "voci": [
            {
                "voce_codice": tpl["voce_codice"],
                "macrovoce": tpl["macrovoce"],
                "categoria": _derive_categoria_from_role(tpl["descrizione"]),
                "descrizione": tpl["descrizione"],
                "is_dynamic": tpl["is_dynamic"],
            }
            for tpl in VOICE_TEMPLATES
        ],
        "limiti_macrovoce": deepcopy(get_macrovoce_limits(tipo_fondo)),
    }


TEMPLATE_SEED: list[dict] = [
    {
        "nome": f"Template standard {fondo}",
        "descrizione": (
            f"Template generico per piani finanziari {fondo}: voci standard "
            "da VOICE_TEMPLATES e limiti macrovoce da MACROVOCE_LIMITS_BY_FONDO."
        ),
        "tipo_fondo": fondo,
        "ente_erogatore": None,
        "versione": 1,
        "struttura_voci": build_struttura_voci(fondo),
    }
    for fondo in _SEED_FONDI
]


def seed_templates(db) -> int:
    """Inserisce i template di ``TEMPLATE_SEED`` assenti (idempotente).

    Un template è considerato già presente se esiste una riga con lo stesso
    ``(nome, versione)`` (chiave naturale ``uq_pf_template_nome_versione``).
    Ritorna il numero di template effettivamente inseriti (0 alla seconda
    chiamata).
    """
    inserted = 0
    for seed in TEMPLATE_SEED:
        exists = (
            db.query(models.PianoFinanziarioTemplate.id)
            .filter(
                models.PianoFinanziarioTemplate.nome == seed["nome"],
                models.PianoFinanziarioTemplate.versione == seed["versione"],
            )
            .first()
        )
        if exists:
            continue
        db.add(models.PianoFinanziarioTemplate(**deepcopy(seed)))
        inserted += 1
    if inserted:
        db.commit()
    return inserted


def crea_piano_da_template(db, template_id: int, progetto_id: int, testata: dict, user):
    """Crea un PianoFinanziario dalle voci del template. Non ancora implementato."""
    raise NotImplementedError("crea_piano_da_template: implementazione nel task E1 successivo (seed/endpoint)")
