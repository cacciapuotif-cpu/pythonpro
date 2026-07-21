"""Endpoint archivio avvisi (FASE E3, Task E3.2).

Due rotte di sola lettura semantica sull'archivio:

- ``GET  /api/v1/archivio/search`` — ricerca full-text (E3.1);
- ``POST /api/v1/archivio/chiedi`` — risposta ancorata all'archivio con
  citazioni obbligatorie e degrado onesto (E3.2).

Entrambe sono consultazione (lettura): la matrice RBAC (backend/auth.py) le
apre a tutti e tre i ruoli. Il ``/chiedi`` e' tecnicamente un POST solo perche'
la domanda in linguaggio naturale viaggia nel body, ma resta una query.

Router sottile: nessuna logica qui, solo serializzazione. La ricerca vive in
``services.archivio_search`` (E3.1, riusata) e l'orchestrazione in
``services.archivio_chiedi``.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

import schemas
from auth import User, get_current_user
from database import get_db
from services.archivio_chiedi import chiedi_archivio
from services.archivio_search import RisultatoArchivio, search_archivio

router = APIRouter(prefix="/api/v1/archivio", tags=["Archivio"])


def _to_search_result(r: RisultatoArchivio) -> schemas.ArchivioSearchResult:
    return schemas.ArchivioSearchResult(
        fonte=r.fonte,
        avviso_id=r.avviso_id,
        avviso_titolo=r.avviso_titolo,
        revisione_id=r.revisione_id,
        regola_id=r.regola_id,
        conoscenza_id=r.conoscenza_id,
        esito_id=r.esito_id,
        riferimento_articolo=r.riferimento_articolo,
        estratto=r.estratto,
        rank=r.rank,
    )


def _to_citazione(r: RisultatoArchivio) -> schemas.ArchivioCitazione:
    return schemas.ArchivioCitazione(
        avviso_id=r.avviso_id,
        avviso_titolo=r.avviso_titolo,
        revisione_id=r.revisione_id,
        regola_id=r.regola_id,
        conoscenza_id=r.conoscenza_id,
        esito_id=r.esito_id,
        riferimento_articolo=r.riferimento_articolo,
        estratto=r.estratto,
    )


@router.get("/search", response_model=List[schemas.ArchivioSearchResult])
def search(
    q: str = Query(..., description="Testo da cercare nell'archivio avvisi"),
    avviso_id: Optional[int] = Query(None),
    tipo_fondo: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[schemas.ArchivioSearchResult]:
    risultati = search_archivio(
        db, q, avviso_id=avviso_id, tipo_fondo=tipo_fondo, limit=limit
    )
    return [_to_search_result(r) for r in risultati]


@router.post("/chiedi", response_model=schemas.ArchivioChiediResponse)
def chiedi(
    payload: schemas.ArchivioChiediRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> schemas.ArchivioChiediResponse:
    esito = chiedi_archivio(
        db,
        payload.domanda,
        avviso_id=payload.avviso_id,
        tipo_fondo=payload.tipo_fondo,
    )
    return schemas.ArchivioChiediResponse(
        stato=esito.stato,
        risposta=esito.risposta,
        citazioni=[_to_citazione(r) for r in esito.citazioni],
        risultati=[_to_search_result(r) for r in esito.risultati],
    )
