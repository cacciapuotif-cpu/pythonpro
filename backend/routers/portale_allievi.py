"""
Router pubblico del portale allievi.

L'autenticazione NON e' il JWT applicativo: l'allievo esterno arriva da
un magic link con token a scadenza giornaliera (vedi
/api/v1/allievi/{id}/magic-link in sprint7.py, che resta protetto).
Per questo il router va incluso SENZA le dependency di protezione
globale: il controllo di accesso e' la validazione del token stesso.
"""
import hashlib
import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
import models
from models import Assignment

router = APIRouter(prefix="/api/v1/portale-allievi", tags=["Portale Allievi"])


@router.get("/profilo")
def get_profilo_allievo(
    token: str,
    db: Session = Depends(get_db),
):
    from models import Allievo, AllievoProject, Project

    allievi = db.query(Allievo).filter(Allievo.email.isnot(None)).all()
    allievo_trovato = None
    for allievo in allievi:
        for day_offset in range(2):
            expected = hashlib.sha256(
                "{}{}{}".format(
                    allievo.id,
                    allievo.email or "",
                    int(time.time() // 86400) - day_offset
                ).encode()
            ).hexdigest()[:32]
            if expected == token:
                allievo_trovato = allievo
                break
        if allievo_trovato:
            break

    if not allievo_trovato:
        raise HTTPException(status_code=401, detail="Token non valido o scaduto")

    links = db.query(AllievoProject).filter(
        AllievoProject.allievo_id == allievo_trovato.id
    ).all() if hasattr(models, 'AllievoProject') else []

    progetti_list = []
    for link in links:
        project = db.query(Project).filter(Project.id == link.project_id).first()
        if not project:
            continue

        ore_frequentate = float(getattr(link, 'ore_frequentate', 0) or 0)

        assignments_docenza = db.query(Assignment).filter(
            Assignment.project_id == project.id,
            Assignment.is_active == True,
            Assignment.role.ilike("%docen%"),
        ).all()
        ore_totali = sum(float(a.assigned_hours or 0) for a in assignments_docenza)

        percentuale = round(ore_frequentate / ore_totali * 100, 1) if ore_totali > 0 else 0
        attestato_disponibile = getattr(link, 'attestato_emesso', False)

        progetti_list.append({
            "project_id": project.id,
            "project_name": project.name,
            "ente_erogatore": project.ente_erogatore or "",
            "avviso": project.avviso or "",
            "ore_frequentate": ore_frequentate,
            "ore_totali": ore_totali,
            "percentuale_frequenza": percentuale,
            "attestato_disponibile": attestato_disponibile,
            "attestato_url": "/api/v1/allievi/{}/attestato/{}".format(
                allievo_trovato.id, project.id
            ) if attestato_disponibile else None,
        })

    return {
        "allievo": {
            "id": allievo_trovato.id,
            "nome": allievo_trovato.nome,
            "cognome": allievo_trovato.cognome,
            "email": allievo_trovato.email,
        },
        "progetti": progetti_list,
    }
