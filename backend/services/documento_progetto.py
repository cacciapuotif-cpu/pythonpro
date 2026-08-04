"""UX-6 — associazione di un atto/convenzione a un progetto gia' esistente.

Caricare un documento dentro un progetto non deve mai generare un progetto
gemello: i dati estratti vanno riversati sul progetto corrente. Questo modulo
tiene la parte di dominio della riconciliazione, cosi' i router restano sottili
e la stessa regola vale per tutti i fondi.

Regola non negoziabile: **nessuna sovrascrittura silenziosa**. Un campo vuoto
sul progetto viene arricchito; un campo gia' valorizzato e discordante diventa
un conflitto, che l'utente deve accettare campo per campo. Un dato gia'
validato da un operatore non viene ribaltato da un parser.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Iterable, Optional

import models
from services.audit_log import write_audit_log

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CampoDocumento:
    """Campo del progetto alimentabile dal documento."""

    nome: str
    etichetta: str
    tipo: str  # "testo" | "data" | "numero" | "intero"


# Campi che un atto/convenzione puo' alimentare sul progetto. L'ordine e'
# quello in cui il diff viene mostrato all'operatore.
CAMPI_DOCUMENTO: tuple[CampoDocumento, ...] = (
    CampoDocumento("codice_fapi", "Codice piano", "testo"),
    CampoDocumento("name", "Titolo del piano", "testo"),
    CampoDocumento("cup", "CUP", "testo"),
    CampoDocumento("id_piano_esterno", "ID piano sul portale del fondo", "testo"),
    CampoDocumento("avviso", "Avviso", "testo"),
    CampoDocumento("delibera_numero", "Numero delibera", "testo"),
    CampoDocumento("delibera_data", "Data delibera", "data"),
    CampoDocumento("data_approvazione", "Data approvazione", "data"),
    CampoDocumento("costo_totale", "Costo totale", "numero"),
    CampoDocumento("contributo_ente", "Contributo del fondo", "numero"),
    CampoDocumento("cofinanziamento", "Cofinanziamento", "numero"),
    CampoDocumento("budget", "Budget", "numero"),
    CampoDocumento("ente_attuatore_id", "Ente attuatore", "intero"),
)

_CAMPI_PER_NOME = {c.nome: c for c in CAMPI_DOCUMENTO}


def parse_data(valore: Any) -> Optional[date]:
    """Data da stringa ISO; ``None`` se assente o non interpretabile."""
    if valore is None or valore == "":
        return None
    if isinstance(valore, datetime):
        return valore.date()
    if isinstance(valore, date):
        return valore
    try:
        return datetime.strptime(str(valore), "%Y-%m-%d").date()
    except ValueError:
        return None


def _coerce(campo: CampoDocumento, valore: Any) -> Any:
    if valore is None or valore == "":
        return None
    if campo.tipo == "data":
        return parse_data(valore)
    if campo.tipo == "intero":
        # FK e contatori: la colonna e' Integer, un float ci finirebbe dentro
        # arrotondato in silenzio (e su SQLite ci resterebbe come 1.0).
        try:
            return int(valore)
        except (TypeError, ValueError):
            return None
    if campo.tipo == "numero":
        try:
            return float(valore)
        except (TypeError, ValueError):
            return None
    return str(valore).strip() or None


def _vuoto(valore: Any) -> bool:
    """Un campo e' vuoto solo se non ha valore: lo zero e' un valore."""
    return valore is None or (isinstance(valore, str) and not valore.strip())


def _uguali(campo: CampoDocumento, attuale: Any, estratto: Any) -> bool:
    if campo.tipo == "intero":
        try:
            return int(attuale) == int(estratto)
        except (TypeError, ValueError):
            return False
    if campo.tipo == "numero":
        try:
            return abs(float(attuale) - float(estratto)) < 0.005
        except (TypeError, ValueError):
            return False
    if campo.tipo == "data":
        return parse_data(attuale) == parse_data(estratto)
    return str(attuale).strip() == str(estratto).strip()


def _serializza(valore: Any) -> Any:
    if isinstance(valore, (date, datetime)):
        return valore.isoformat()
    return valore


def confronta_dati(progetto, estratti: dict[str, Any]) -> list[dict[str, Any]]:
    """Confronto completo, compresi i valori identici.

    Lo stato è uno fra ``identico``, ``diverso`` e
    ``assente_nel_sistema``: è il contratto della tabella UX-6b.
    """
    confronto: list[dict[str, Any]] = []
    for campo in CAMPI_DOCUMENTO:
        estratto = _coerce(campo, estratti.get(campo.nome))
        if estratto is None:
            continue
        attuale = getattr(progetto, campo.nome, None)
        if _vuoto(attuale):
            stato = "assente_nel_sistema"
        elif _uguali(campo, attuale, estratto):
            stato = "identico"
        else:
            stato = "diverso"
        confronto.append({
            "campo": campo.nome,
            "etichetta": campo.etichetta,
            "valore_attuale": _serializza(attuale),
            "valore_estratto": _serializza(estratto),
            "stato": stato,
            "conflitto": stato == "diverso",
        })
    return confronto


def calcola_diff(progetto, estratti: dict[str, Any]) -> list[dict[str, Any]]:
    """Compatibilità UX-6: ritorna soltanto campi diversi o assenti."""
    return [
        voce
        for voce in confronta_dati(progetto, estratti)
        if voce["stato"] != "identico"
    ]


def applica_estratti(
    progetto,
    estratti: dict[str, Any],
    campi_da_applicare: Optional[Iterable[str]] = None,
) -> dict[str, list[str]]:
    """Riversa i dati estratti sul progetto rispettando i conflitti.

    I campi vuoti sono arricchiti sempre; quelli in conflitto solo se elencati
    in ``campi_da_applicare``. Ritorna i nomi dei campi applicati e di quelli
    lasciati indietro, cosi' il chiamante puo' dirlo all'operatore.
    """
    accettati = set(campi_da_applicare or ())
    applicati: list[str] = []
    non_applicati: list[str] = []

    for voce in calcola_diff(progetto, estratti):
        campo = _CAMPI_PER_NOME[voce["campo"]]
        if voce["conflitto"] and campo.nome not in accettati:
            non_applicati.append(campo.nome)
            continue
        setattr(progetto, campo.nome, _coerce(campo, estratti.get(campo.nome)))
        applicati.append(campo.nome)

    return {"campi_applicati": applicati, "campi_in_conflitto_non_applicati": non_applicati}


def applica_solo_campi_scelti(
    progetto,
    estratti: dict[str, Any],
    campi_da_applicare: Optional[Iterable[str]] = None,
) -> dict[str, list[str]]:
    """UX-6b: applica esattamente la selezione, anche sui campi vuoti.

    La modalità ``associa`` passa una selezione vuota e non modifica alcun dato
    anagrafico/finanziario. La modalità ``aggiorna`` non può quindi trascinare
    arricchimenti impliciti non spuntati.
    """
    scelti = set(campi_da_applicare or ())
    sconosciuti = scelti - set(_CAMPI_PER_NOME)
    if sconosciuti:
        raise ValueError(
            "Campi non aggiornabili dal documento: "
            + ", ".join(sorted(sconosciuti))
        )

    applicati: list[str] = []
    disponibili = {
        voce["campo"]: voce
        for voce in confronta_dati(progetto, estratti)
        if voce["stato"] != "identico"
    }
    for nome in CAMPI_DOCUMENTO:
        if nome.nome not in scelti or nome.nome not in disponibili:
            continue
        setattr(progetto, nome.nome, _coerce(nome, estratti.get(nome.nome)))
        applicati.append(nome.nome)

    non_applicati = [
        nome for nome in disponibili
        if nome not in scelti
    ]
    return {
        "campi_applicati": applicati,
        "campi_in_conflitto_non_applicati": non_applicati,
    }


def documento_riconosciuto(piano: dict[str, Any]) -> bool:
    """Il parser ha identificato il documento come atto del fondo?

    Senza almeno il codice del piano o il titolo non c'e' nulla che identifichi
    l'atto: creare un progetto da un simile estratto produce solo un fantasma
    col nome di fallback. E' quello che ha generato il progetto 13 in
    produzione.
    """
    return bool((piano.get("codice_fapi") or "").strip() or (piano.get("titolo") or "").strip())


def archivia_documento_progetto(
    db,
    *,
    project,
    preview: dict,
    file_path: str,
    tipo_documento: str,
    current_user,
):
    """Versiona e archivia un documento di progetto, per qualunque fondo.

    Estratta da ``convenzione_upload._archivia_documento`` cosi' che
    ``formazienda_upload.py`` e i futuri router per-fondo condividano la
    stessa regola di versionamento invece di duplicarla.
    """
    from sqlalchemy import func

    versione = (
        db.query(func.max(models.ProjectDocumento.versione))
        .filter(
            models.ProjectDocumento.project_id == project.id,
            models.ProjectDocumento.tipo_documento == tipo_documento,
        )
        .scalar()
        or 0
    ) + 1
    digest = None
    try:
        with open(file_path, "rb") as stream:
            digest = hashlib.sha256(stream.read()).hexdigest()
    except OSError:
        logger.warning("Impossibile calcolare SHA-256 del documento %s", file_path)

    documento = models.ProjectDocumento(
        project_id=project.id,
        tipo_documento=tipo_documento,
        versione=versione,
        file_path=file_path,
        file_name=preview.get("original_filename"),
        mime_type=preview.get("mime_type") or "application/pdf",
        sha256=digest,
        caricato_da_user_id=current_user.id,
    )
    db.add(documento)
    db.flush()
    # Compatibilita' con generatori e schermate legacy: il campo si chiama
    # *convenzione*_file_path e deve puntare soltanto a un documento primario.
    if tipo_documento in {"convenzione", "atto_concessione", "delibera"}:
        project.convenzione_file_path = file_path
    write_audit_log(
        db,
        user_id=current_user.id,
        azione="documento_progetto_caricato",
        risorsa_tipo="project_document",
        risorsa_id=documento.id,
        dati_dopo={
            "project_id": project.id,
            "tipo_documento": tipo_documento,
            "versione": versione,
            "sha256": digest,
        },
    )
    return documento
