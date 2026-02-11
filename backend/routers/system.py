"""
Router per endpoints di sistema
Health check, root endpoint e utility
"""

from fastapi import APIRouter
from sqlalchemy import text
from database import SessionLocal
import logging
import os

logger = logging.getLogger(__name__)
router = APIRouter(tags=["System"])


@router.get("/")
def read_root():
    """Endpoint di benvenuto pubblico"""
    return {
        "message": "Gestionale Collaboratori e Progetti v2.0",
        "status": "online",
        "security": "enabled",
        "docs": "/docs" if os.getenv("ENVIRONMENT") != "production" else "Contact admin"
    }


@router.get("/health")
def health_check():
    """Health check superficiale - NO dipendenze DB/Redis"""
    return {"status": "ok"}


def check_db_health():
    """Controlla lo stato del database"""
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False
