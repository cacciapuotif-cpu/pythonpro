"""Router per i template dei piani finanziari (FASE E1 — Task E1.2/E1.5).

Espone listing e anteprima (consultabili da tutti e tre i ruoli: il prefisso
è censito in ``auth.OPERATIONAL_PREFIXES``, GET = safe). La creazione del
piano da template vive in ``routers/piani_finanziari.py``
(``POST /api/v1/piani-finanziari/from-template``) per coerenza URL.

Router sottile: la logica di dominio sta in ``services/piano_templates.py``
e i massimali dell'anteprima riusano ``services/massimali`` (nessuna
duplicazione della precedenza regola avviso > massimale fondo).
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from services.piano_templates import massimali_anteprima

router = APIRouter(prefix="/api/v1/piano-templates", tags=["Piano Templates"])


@router.get("/", response_model=List[schemas.PianoTemplateRead])
def list_piano_templates(
    tipo_fondo: Optional[str] = Query(None, description="Filtra i template per fondo"),
    avviso_id: Optional[int] = Query(
        None,
        description="Marca preselezionato=true il template collegato all'avviso",
    ),
    db: Session = Depends(get_db),
):
    """Template attivi pertinenti; il template collegato all'avviso richiesto
    (``PianoFinanziarioTemplate.avviso_id``) esce con ``preselezionato=true``
    e in testa alla lista."""
    query = db.query(models.PianoFinanziarioTemplate).filter(
        models.PianoFinanziarioTemplate.is_active.is_(True)
    )
    if tipo_fondo:
        query = query.filter(
            models.PianoFinanziarioTemplate.tipo_fondo == tipo_fondo.strip().lower()
        )
    templates = query.order_by(
        models.PianoFinanziarioTemplate.tipo_fondo,
        models.PianoFinanziarioTemplate.versione.desc(),
        models.PianoFinanziarioTemplate.nome,
    ).all()

    items = []
    for template in templates:
        item = schemas.PianoTemplateRead.model_validate(template)
        item.preselezionato = bool(avviso_id and template.avviso_id == avviso_id)
        items.append(item)
    items.sort(key=lambda item: not item.preselezionato)  # preselezionato in testa
    return items


@router.get("/{template_id}/anteprima", response_model=schemas.PianoTemplateAnteprima)
def anteprima_piano_template(
    template_id: int,
    avviso_id: Optional[int] = Query(
        None,
        description="Avviso da usare per i massimali (default: quello collegato al template)",
    ),
    anno: Optional[int] = Query(
        None,
        ge=2000,
        le=2100,
        description="Anno per il lookup MassimaleFondo (default: anno corrente)",
    ),
    db: Session = Depends(get_db),
):
    """Anteprima del template: voci della ``struttura_voci`` + massimali
    effettivi per docenza/tutoraggio con fonte esplicita
    (``regola_avviso`` | ``massimale_fondo``)."""
    template = db.get(models.PianoFinanziarioTemplate, template_id)
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template piano finanziario non trovato",
        )

    effective_avviso_id = avviso_id or template.avviso_id
    avviso_revisione_id = None
    if effective_avviso_id:
        avviso = db.get(models.Avviso, effective_avviso_id)
        if avviso is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Avviso non trovato",
            )
        avviso_revisione_id = avviso.revisione_corrente_id

    return {
        "template": schemas.PianoTemplateRead.model_validate(template),
        "voci": (template.struttura_voci or {}).get("voci") or [],
        "massimali": massimali_anteprima(
            db,
            template,
            avviso_revisione_id=avviso_revisione_id,
            anno=anno or datetime.now().year,
        ),
    }
