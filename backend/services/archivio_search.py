"""Ricerca full-text sull'archivio avvisi (FASE E3, Task E3.1).

Fonti (le sole in DB — i markdown puliti delle revisioni stanno su file,
``AvvisoRevisione.cleaned_md_path``, e restano fuori da questa ricerca):

1. ``AvvisoRegola`` con ``stato='validata'`` — testo = chiave + valore
   serializzato + testo_originale;
2. ``AvvisoConoscenza`` — contenuto + tags;
3. ``AvvisoEsitoProgetto`` — esito + note.

Dialect-aware, stesso contratto di ritorno:

- PostgreSQL: ``to_tsvector('italian', ...)`` @@ ``websearch_to_tsquery`` con
  ``ts_rank``; le espressioni ricalcano ESATTAMENTE gli indici GIN della
  migration 061 (stesso ordine di concatenazione, stesse coalesce/cast) cosi'
  il planner puo' usarli.
- SQLite (suite) e qualunque altro dialect: fallback ``ILIKE %term%`` per
  termine con rank = numero di termini matchati. Il fallback e' anche il
  degrado runtime.

Servizio puro (nessuna dipendenza da router): consumato dall'endpoint
``/api/v1/archivio/search`` e da "chiedi all'archivio" (Task E3.2).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import func
from sqlalchemy.orm import Session

import models

FONTE_REGOLA = "regola"
FONTE_CONOSCENZA = "conoscenza"
FONTE_ESITO = "esito"

_TS_CONFIG = "italian"
_MIN_QUERY_LEN = 3
_MIN_TERM_LEN = 3
_ESTRATTO_WIDTH = 240


@dataclass(frozen=True)
class RisultatoArchivio:
    fonte: str
    avviso_id: int
    avviso_titolo: str
    revisione_id: Optional[int]
    regola_id: Optional[int]
    conoscenza_id: Optional[int]
    esito_id: Optional[int]
    riferimento_articolo: Optional[str]
    estratto: str
    rank: float


def _termini(q: str) -> list[str]:
    """Termini utili della query per il fallback ILIKE e per l'estratto:
    minuscole, solo alfanumerici, lunghezza >= 3, dedup con ordine stabile."""
    visti: list[str] = []
    for tok in re.split(r"[^\w]+", q.lower(), flags=re.UNICODE):
        if len(tok) >= _MIN_TERM_LEN and tok not in visti:
            visti.append(tok)
    return visti


def _txt(col):
    """coalesce(cast(col, TEXT), '') — identico alle espressioni indicizzate
    nella migration 061 (il cast serializza le colonne JSON/JSONB)."""
    return func.coalesce(sa.cast(col, sa.Text), "")


def _match_and_rank(dialect: str, text_expr, q: str, termini: list[str]):
    """(condizione WHERE, espressione rank) per il dialect corrente."""
    if dialect == "postgresql":
        tsv = func.to_tsvector(_TS_CONFIG, text_expr)
        tsq = func.websearch_to_tsquery(_TS_CONFIG, q)
        return tsv.op("@@")(tsq), func.ts_rank(tsv, tsq)
    condizioni = [text_expr.ilike(f"%{t}%") for t in termini]
    rank = sum(
        (sa.case((cond, 1), else_=0) for cond in condizioni),
        start=sa.literal(0),
    )
    return sa.or_(*condizioni), rank


def _estratto(testo: str, termini: list[str], width: int = _ESTRATTO_WIDTH) -> str:
    """Porzione pertinente del testo attorno al primo termine trovato.

    Su PostgreSQL lo stemming italiano puo' matchare flessioni diverse dal
    termine esatto: si ritenta con prefissi via via piu' corti del termine.
    """
    testo = (testo or "").strip()
    lower = testo.lower()
    for termine in termini:
        for prefisso in (termine, termine[:6], termine[:4]):
            if len(prefisso) < _MIN_TERM_LEN:
                break
            idx = lower.find(prefisso)
            if idx >= 0:
                start = max(0, idx - width // 3)
                end = min(len(testo), idx + width)
                snippet = testo[start:end].strip()
                prefix = "…" if start > 0 else ""
                suffix = "…" if end < len(testo) else ""
                return f"{prefix}{snippet}{suffix}"
    return testo[:width] + ("…" if len(testo) > width else "")


def _cerca_regole(db, dialect, q, termini, avviso_id, tipo_fondo, limit):
    R = models.AvvisoRegola
    text_expr = (
        _txt(R.chiave) + " " + _txt(R.valore) + " " + _txt(R.testo_originale)
    )
    match, rank = _match_and_rank(dialect, text_expr, q, termini)
    query = (
        db.query(R, models.Avviso.id, models.Avviso.titolo, rank.label("rank"))
        .join(models.AvvisoRevisione, R.avviso_revisione_id == models.AvvisoRevisione.id)
        .join(models.Avviso, models.AvvisoRevisione.avviso_id == models.Avviso.id)
        .filter(R.stato == "validata", match)
    )
    if avviso_id is not None:
        query = query.filter(models.Avviso.id == avviso_id)
    if tipo_fondo is not None:
        query = query.filter(models.Avviso.fondo == tipo_fondo)
    risultati = []
    for regola, av_id, av_titolo, rank_val in query.order_by(sa.desc("rank")).limit(limit):
        valore_txt = "" if regola.valore is None else str(regola.valore)
        testo = f"{regola.testo_originale} [{regola.chiave}: {valore_txt}]"
        risultati.append(RisultatoArchivio(
            fonte=FONTE_REGOLA,
            avviso_id=av_id,
            avviso_titolo=av_titolo,
            revisione_id=regola.avviso_revisione_id,
            regola_id=regola.id,
            conoscenza_id=None,
            esito_id=None,
            riferimento_articolo=regola.riferimento_articolo,
            estratto=_estratto(testo, termini),
            rank=float(rank_val or 0.0),
        ))
    return risultati


def _cerca_conoscenze(db, dialect, q, termini, avviso_id, tipo_fondo, limit):
    C = models.AvvisoConoscenza
    text_expr = _txt(C.contenuto) + " " + _txt(C.tags)
    match, rank = _match_and_rank(dialect, text_expr, q, termini)
    query = (
        db.query(C, models.Avviso.id, models.Avviso.titolo, rank.label("rank"))
        .join(models.Avviso, C.avviso_id == models.Avviso.id)
        .filter(match)
    )
    if avviso_id is not None:
        query = query.filter(models.Avviso.id == avviso_id)
    if tipo_fondo is not None:
        query = query.filter(models.Avviso.fondo == tipo_fondo)
    risultati = []
    for conoscenza, av_id, av_titolo, rank_val in query.order_by(sa.desc("rank")).limit(limit):
        tags_txt = " ".join(str(t) for t in (conoscenza.tags or []))
        testo = f"{conoscenza.contenuto} [{tags_txt}]" if tags_txt else conoscenza.contenuto
        risultati.append(RisultatoArchivio(
            fonte=FONTE_CONOSCENZA,
            avviso_id=av_id,
            avviso_titolo=av_titolo,
            revisione_id=conoscenza.avviso_revisione_id,
            regola_id=None,
            conoscenza_id=conoscenza.id,
            esito_id=None,
            riferimento_articolo=None,
            estratto=_estratto(testo, termini),
            rank=float(rank_val or 0.0),
        ))
    return risultati


def _cerca_esiti(db, dialect, q, termini, avviso_id, tipo_fondo, limit):
    E = models.AvvisoEsitoProgetto
    text_expr = _txt(E.esito) + " " + _txt(E.note)
    match, rank = _match_and_rank(dialect, text_expr, q, termini)
    query = (
        db.query(E, models.Avviso.id, models.Avviso.titolo, rank.label("rank"))
        .join(models.Avviso, E.avviso_id == models.Avviso.id)
        .filter(match)
    )
    if avviso_id is not None:
        query = query.filter(models.Avviso.id == avviso_id)
    if tipo_fondo is not None:
        query = query.filter(models.Avviso.fondo == tipo_fondo)
    risultati = []
    for esito, av_id, av_titolo, rank_val in query.order_by(sa.desc("rank")).limit(limit):
        testo = f"{esito.esito}: {esito.note}" if esito.note else esito.esito
        risultati.append(RisultatoArchivio(
            fonte=FONTE_ESITO,
            avviso_id=av_id,
            avviso_titolo=av_titolo,
            revisione_id=esito.avviso_revisione_id,
            regola_id=None,
            conoscenza_id=None,
            esito_id=esito.id,
            riferimento_articolo=None,
            estratto=_estratto(testo, termini),
            rank=float(rank_val or 0.0),
        ))
    return risultati


def search_archivio(
    db: Session,
    q: str,
    *,
    avviso_id: Optional[int] = None,
    tipo_fondo: Optional[str] = None,
    limit: int = 20,
) -> list[RisultatoArchivio]:
    """Ricerca full-text sulle 3 fonti archivio, ordinata per rank decrescente.

    Query vuota o piu' corta di 3 caratteri (o senza termini utili) -> [].
    """
    q = (q or "").strip()
    if len(q) < _MIN_QUERY_LEN or limit <= 0:
        return []
    termini = _termini(q)
    if not termini:
        return []

    dialect = db.get_bind().dialect.name

    risultati: list[RisultatoArchivio] = []
    for cerca in (_cerca_regole, _cerca_conoscenze, _cerca_esiti):
        risultati.extend(cerca(db, dialect, q, termini, avviso_id, tipo_fondo, limit))

    risultati = [r for r in risultati if r.rank > 0]
    risultati.sort(key=lambda r: r.rank, reverse=True)
    return risultati[:limit]
