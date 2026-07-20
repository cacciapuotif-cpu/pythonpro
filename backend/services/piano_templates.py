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
from datetime import datetime
from types import SimpleNamespace

import crud
import models
import schemas
from crud import _derive_categoria_from_role
from piano_finanziario_config import VOICE_TEMPLATES, get_macrovoce_limits
from services.massimali import get_massimale_effettivo

__all__ = [
    "TEMPLATE_SEED",
    "build_struttura_voci",
    "seed_templates",
    "crea_piano_da_template",
    "massimali_anteprima",
]

#: categorie voce coperte dal servizio massimali (docenza/tutoraggio)
CATEGORIE_MASSIMALI = ("docenza", "tutoraggio")

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


def massimali_anteprima(db, template, *, avviso_revisione_id, anno) -> list[dict]:
    """Massimali effettivi per l'anteprima template, SENZA piano persistito.

    Scelta E1.2: ``get_massimale_effettivo`` legge dal piano solo
    ``avviso_revisione_id``, ``tipo_fondo`` e ``anno`` — un oggetto leggero non
    persistito è sufficiente e la logica di precedenza resta in un solo posto
    (nessuna duplicazione, nessuna firma alternativa del servizio massimali).
    """
    pseudo_piano = SimpleNamespace(
        avviso_revisione_id=avviso_revisione_id,
        tipo_fondo=template.tipo_fondo,
        anno=anno,
    )
    massimali = []
    for categoria in CATEGORIE_MASSIMALI:
        effettivo = get_massimale_effettivo(db, pseudo_piano, categoria)
        if effettivo is None:
            continue  # nessun limite verificabile: niente badge inventati
        massimali.append({
            "categoria": categoria,
            "limite": float(effettivo.limite),
            "fonte": effettivo.fonte,
            "riferimento_articolo": effettivo.riferimento_articolo,
        })
    return massimali


def _valida_struttura_template(template) -> None:
    """Valida la ``struttura_voci`` PRIMA di creare il piano: un template
    malformato deve fallire con 400 senza lasciare piani orfani già committati
    da ``crud.create_piano_finanziario``."""
    voci_template = (template.struttura_voci or {}).get("voci") or []
    if not voci_template:
        raise ValueError("struttura_voci del template senza voci: template non utilizzabile")
    for voce_tpl in voci_template:
        if not voce_tpl.get("voce_codice") or not voce_tpl.get("macrovoce"):
            raise ValueError(
                "struttura_voci del template non valida: voce senza voce_codice/macrovoce"
            )


def _applica_struttura_template(db, piano, template, user) -> None:
    """Riallinea le voci del piano appena creato alla ``struttura_voci`` del
    template: upsert per ``voce_codice`` (le default auto-seedate da
    ``crud.create_piano_finanziario`` vengono arricchite di categoria, le voci
    mancanti — es. le dinamiche B.2/B.3 — aggiunte), rimozione delle voci non
    previste dal template. ``crud.create_voce_piano`` non è utilizzabile qui:
    il suo schema non espone ``voce_codice``/``macrovoce`` (verificato E1.2).
    La struttura è già stata validata da ``_valida_struttura_template`` PRIMA
    della creazione del piano (nessun piano orfano su template malformato).
    """
    voci_template = template.struttura_voci["voci"]
    username = getattr(user, "username", None)
    esistenti = {v.voce_codice: v for v in piano.voci}
    codici_template = set()
    # Si lavora sulla relationship (append/remove, cascade delete-orphan) e non
    # su db.add/db.delete diretti: così la collezione ``piano.voci`` resta
    # coerente anche con sessioni ``expire_on_commit=False``.
    for voce_tpl in voci_template:
        codice = voce_tpl["voce_codice"]
        macrovoce = voce_tpl["macrovoce"]
        codici_template.add(codice)
        voce = esistenti.get(codice)
        if voce is None:
            voce = models.VocePianoFinanziario(voce_codice=codice, macrovoce=macrovoce)
            piano.voci.append(voce)
        voce.macrovoce = macrovoce
        voce.descrizione = voce_tpl.get("descrizione") or voce.descrizione
        voce.categoria = voce_tpl.get("categoria") or voce.categoria
        if username:
            voce.created_by_user = username
    for codice, voce in esistenti.items():
        if codice not in codici_template:
            piano.voci.remove(voce)


def crea_piano_da_template(db, template_id: int, progetto_id: int, testata: dict, user):
    """Crea un ``PianoFinanziario`` con le voci strutturate dal template.

    Riusa ``crud.create_piano_finanziario`` (dedup, codice piano, audit log,
    eventi budget) e poi applica la struttura del template. Con ``avviso_id``
    in testata valorizza ``avviso_pf_id`` e ``avviso_revisione_id`` (revisione
    corrente dell'avviso).

    Raises:
        LookupError: template o avviso inesistenti (-> 404 nel router).
        ValueError: input non validi / duplicati (-> 400 nel router).
    """
    template = db.get(models.PianoFinanziarioTemplate, template_id)
    if template is None or not template.is_active:
        raise LookupError("Template piano finanziario non trovato")
    _valida_struttura_template(template)

    avviso = None
    if testata.get("avviso_id") is not None:
        avviso = db.get(models.Avviso, testata["avviso_id"])
        if avviso is None:
            raise LookupError("Avviso non trovato")

    anno = testata["anno"]
    data_inizio = testata.get("data_inizio") or datetime(anno, 1, 1)
    data_fine = testata.get("data_fine") or datetime(anno, 12, 31, 23, 59, 59)
    if data_inizio.year != anno:
        # il crud deriva l'anno del piano da data_inizio: incoerenze esplicite
        raise ValueError("anno e data_inizio non coerenti: l'anno del piano deriva da data_inizio")

    payload = schemas.PianoFinanziarioCreate(
        progetto_id=progetto_id,
        nome=testata["nome"],
        tipo_fondo=template.tipo_fondo,
        budget_totale=testata.get("budget_totale") or 0.0,
        data_inizio=data_inizio,
        data_fine=data_fine,
        codice_progetto_fondo=testata.get("codice_progetto_fondo"),
        importo_ammesso=testata.get("importo_ammesso"),
        data_ammissione=testata.get("data_ammissione"),
        note=testata.get("note"),
    )
    piano = crud.create_piano_finanziario(db, payload)

    _applica_struttura_template(db, piano, template, user)
    if avviso is not None:
        piano.avviso_pf_id = avviso.id
        piano.avviso_revisione_id = avviso.revisione_corrente_id
    db.commit()
    return crud.get_piano_finanziario(db, piano.id)
