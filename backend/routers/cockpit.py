"""
Router per home cockpit — decisioni urgenti che richiedono l'admin.
Aggrega in un unico endpoint tutto quello che richiede attenzione.
"""
from time_utils import utc_now
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from database import get_db
from models import (
    DocumentoRichiesto, Collaborator, AgentSuggestion, AgentRun,
    Project, Assignment, TimesheetGenerato, AziendaClienteProjectLink
)
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/v1", tags=["cockpit"])


@router.get("/cockpit/decisioni")
def get_decisioni_urgenti(db: Session = Depends(get_db)):
    """
    Ritorna tutte le decisioni che richiedono attenzione dell'admin oggi.
    """
    decisioni = []
    now = utc_now()

    suggestions = db.query(AgentSuggestion).filter(
        AgentSuggestion.status == "pending",
    ).order_by(desc(AgentSuggestion.created_at)).limit(20).all()

    for s in suggestions:
        decisioni.append({
            "tipo": "agente",
            "priorita": "alta" if s.severity in ("high", "critical") else "media",
            "titolo": s.title or "Suggerimento agente",
            "descrizione": s.description or "",
            "entita": s.entity_type,
            "entita_id": s.entity_id,
            "creato_il": s.created_at.isoformat() if s.created_at else None,
            "azione_url": "/api/v1/agent-suggestions/{}/approve".format(s.id),
            "id": s.id,
            "categoria": "documento" if "document" in (s.suggestion_type or "") else "comunicazione",
        })

    docs_pending = db.query(DocumentoRichiesto).join(
        Collaborator, Collaborator.id == DocumentoRichiesto.collaboratore_id
    ).filter(
        DocumentoRichiesto.stato == "caricato",
    ).order_by(desc(DocumentoRichiesto.data_caricamento)).limit(10).all()

    for doc in docs_pending:
        collab = db.query(Collaborator).filter(
            Collaborator.id == doc.collaboratore_id
        ).first()
        nome = "{} {}".format(
            collab.first_name if collab else "",
            collab.last_name if collab else ""
        ).strip()
        decisioni.append({
            "tipo": "documento",
            "priorita": "alta",
            "titolo": "{} — {}".format(doc.tipo_documento, nome),
            "descrizione": "Documento caricato, in attesa di validazione manuale",
            "entita": "collaborator",
            "entita_id": doc.collaboratore_id,
            "creato_il": doc.data_caricamento.isoformat() if doc.data_caricamento else None,
            "azione_url": "/api/v1/documenti-richiesti/{}/valida".format(doc.id),
            "id": doc.id,
            "categoria": "documento",
        })

    progetti_attenzione = db.query(Project).filter(
        Project.status == "active",
        Project.end_date < now,
    ).limit(5).all()

    for p in progetti_attenzione:
        giorni = (now.date() - p.end_date.date()).days if p.end_date else 0
        decisioni.append({
            "tipo": "progetto",
            "priorita": "alta" if giorni > 30 else "media",
            "titolo": "Progetto {} oltre termine".format(p.name),
            "descrizione": "Scaduto da {} giorni — verifica stato rendicontazione".format(giorni),
            "entita": "project",
            "entita_id": p.id,
            "creato_il": None,
            "azione_url": None,
            "id": p.id,
            "categoria": "progetto",
        })

    beneficiari_senza_regime = db.query(AziendaClienteProjectLink).filter(
        AziendaClienteProjectLink.regime_aiuto == None,
    ).limit(5).all()

    for link in beneficiari_senza_regime:
        project = db.query(Project).filter(Project.id == link.project_id).first()
        azienda = link.azienda
        decisioni.append({
            "tipo": "regime_aiuto",
            "priorita": "media",
            "titolo": "Regime aiuto non definito",
            "descrizione": "Azienda ID {} su progetto {} — definire de minimis o esenzione".format(
                link.azienda_cliente_id,
                project.name if project else link.project_id
            ),
            "entita": "project",
            "entita_id": link.project_id,
            "creato_il": link.created_at.isoformat() if link.created_at else None,
            "azione_url": None,
            "id": link.id,
            "categoria": "compliance",
        })

    stats = {
        "progetti_attivi": db.query(Project).filter(Project.status == "active").count(),
        "pratiche_aperte": db.query(DocumentoRichiesto).filter(
            DocumentoRichiesto.stato.in_(["richiesto", "caricato"])
        ).count(),
        "agenti_attivi": db.query(AgentRun).filter(
            AgentRun.status == "running"
        ).count(),
        "scadenze_7gg": db.query(Project).filter(
            Project.status == "active",
            Project.end_date <= now + timedelta(days=7),
            Project.end_date >= now,
        ).count(),
    }

    decisioni.sort(key=lambda x: (
        0 if x["priorita"] == "alta" else 1,
        x["creato_il"] or ""
    ), reverse=False)

    return {
        "decisioni": decisioni,
        "totale": len(decisioni),
        "stats": stats,
        "generato_il": now.isoformat(),
    }
