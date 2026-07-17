"""Generazione del pacchetto di rendicontazione per progetto.

Servizio di dominio senza dipendenze HTTP. Produce uno ZIP strutturato per
fondo e regime di aiuto; i router si occupano di RBAC e risposta download.
"""
from __future__ import annotations

import io
import logging
import os
import re
import unicodedata
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

UPLOAD_BASE = "/app/uploads"


def _safe_zip_component(value: object, *, max_length: int = 80) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", ascii_value).strip("._-")
    return (safe or "senza_nome")[:max_length]


def _add_file(zf: zipfile.ZipFile, file_path: Optional[str], zip_name: str) -> bool:
    if not file_path:
        return False
    full = os.path.join(UPLOAD_BASE, file_path) if not file_path.startswith("/") else file_path
    if not os.path.exists(full):
        logger.warning("File non trovato: {}".format(full))
        return False
    zf.write(full, zip_name)
    return True


def _add_text(zf: zipfile.ZipFile, content: str, zip_name: str) -> None:
    zf.writestr(zip_name, content)


def _normalize_fondo(value: Optional[str]) -> str:
    normalized = (value or "").strip().lower()
    if "formazienda" in normalized:
        return "formazienda"
    if normalized == "fapi" or "fapi" in normalized:
        return "fapi"
    if "fondimpresa" in normalized:
        return "fondimpresa"
    if "campania" in normalized or "regione" in normalized or normalized == "regionale":
        return "regione_campania"
    return "generico"


def _resolve_fondo(project) -> str:
    """Preferisce la FK canonica dell'avviso, con fallback legacy."""
    avviso = getattr(project, "avviso_rel", None)
    return _normalize_fondo(
        getattr(avviso, "fondo", None)
        or getattr(avviso, "ente_erogatore", None)
        or getattr(project, "ente_erogatore", None)
    )


def _add_fund_specific_structure(zf: zipfile.ZipFile, fondo: str, manifest_lines: list[str]) -> int:
    added = 0
    if fondo == "formazienda":
        manifest_lines.append("Fondo: Formazienda — include autocertificazioni, questionari, FormUp")
        entries = {
            "04_fondo_formazienda/autocertificazioni/autocertificazione_beneficiario.txt": "Placeholder autocertificazione beneficiario Formazienda.\n",
            "04_fondo_formazienda/questionari/questionario_gradimento.txt": "Placeholder questionario Formazienda.\n",
            "04_fondo_formazienda/formup/formup_1_anagrafica.txt": "Placeholder FormUp 1 - anagrafica.\n",
            "04_fondo_formazienda/formup/formup_2_presenze.txt": "Placeholder FormUp 2 - presenze.\n",
            "04_fondo_formazienda/formup/formup_3_docenti.txt": "Placeholder FormUp 3 - docenti.\n",
            "04_fondo_formazienda/formup/formup_4_rendiconto.txt": "Placeholder FormUp 4 - rendiconto.\n",
        }
    elif fondo == "fapi":
        manifest_lines.append("Fondo: FAPI — include relazione beneficiario e relazione ente formazione")
        entries = {
            "04_fondo_fapi/relazione_beneficiario.txt": "Placeholder relazione beneficiario FAPI.\n",
            "04_fondo_fapi/relazione_ente_formazione.txt": "Placeholder relazione ente formazione FAPI.\n",
        }
    elif fondo == "fondimpresa":
        manifest_lines.append("Fondo: Fondimpresa — include dettaglio budget e margine")
        entries = {
            "04_fondo_fondimpresa/dettaglio_budget.txt": "Placeholder dettaglio budget Fondimpresa.\n",
            "04_fondo_fondimpresa/margine.txt": "Placeholder margine Fondimpresa.\n",
        }
    elif fondo == "regione_campania":
        manifest_lines.append("Fondo: Regione Campania — include atti regionali")
        entries = {
            "04_fondo_regione_campania/atti_regionali/determina_concessione.txt": "Placeholder determina concessione Regione Campania.\n",
            "04_fondo_regione_campania/atti_regionali/atto_liquidazione.txt": "Placeholder atto liquidazione Regione Campania.\n",
        }
    else:
        manifest_lines.append("Fondo: generico — struttura standard")
        entries = {
            "04_fondo_generico/note_fondo.txt": "Nessuna struttura fondo specifica configurata.\n",
        }

    for zip_name, content in entries.items():
        _add_text(zf, content, zip_name)
        manifest_lines.append("  [OK] {}".format(zip_name))
        added += 1
    return added


def genera_pacchetto_rendicontazione(
    db,
    project_id: int,
) -> tuple[bytes, str]:
    """
    Genera il pacchetto ZIP di rendicontazione per un progetto.
    Ritorna (zip_bytes, filename).
    """
    from models import (
        Project, Assignment, Collaborator, TimesheetGenerato,
        AziendaClienteProjectLink, DatiRetributivi, Allievo,
    )
    from sqlalchemy.orm import joinedload

    project = (
        db.query(Project)
        .options(joinedload(Project.ente_attuatore), joinedload(Project.avviso_rel))
        .filter(Project.id == project_id)
        .first()
    )

    if not project:
        raise ValueError("Progetto non trovato: {}".format(project_id))

    buffer = io.BytesIO()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    project_safe = _safe_zip_component(project.name, max_length=30)
    zip_filename = "rendicontazione_{}_{}.zip".format(project_safe, timestamp)

    file_count = 0
    avviso = getattr(project, "avviso_rel", None)
    fondo = _resolve_fondo(project)
    manifest_lines = [
        "PACCHETTO RENDICONTAZIONE",
        "Progetto: {}".format(project.name),
        "CUP: {}".format(project.cup or "N/D"),
        "Ente Erogatore: {}".format(
            getattr(avviso, "ente_erogatore", None) or project.ente_erogatore or "N/D"
        ),
        "Avviso: {}".format(
            getattr(avviso, "codice", None) or project.avviso or "N/D"
        ),
        "Generato il: {}".format(datetime.now().strftime("%d/%m/%Y %H:%M")),
        "",
        "=" * 60,
        "CONTENUTO DEL PACCHETTO",
        "=" * 60,
        "",
    ]

    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        file_count += _add_fund_specific_structure(zf, fondo, manifest_lines)
        manifest_lines.append("")

        manifest_lines.append("--- TIMESHEET COLLABORATORI ---")
        assignments = db.query(Assignment).options(
            joinedload(Assignment.collaborator)
        ).filter(
            Assignment.project_id == project_id,
            Assignment.is_active == True,
        ).all()

        for assignment in assignments:
            collab = assignment.collaborator
            collab_safe = _safe_zip_component(
                "{}_{}".format(collab.last_name, collab.first_name)
            ).upper()

            ultimo_ts = db.query(TimesheetGenerato).filter(
                TimesheetGenerato.assignment_id == assignment.id
            ).order_by(TimesheetGenerato.generato_il.desc()).first()

            if ultimo_ts and os.path.exists(ultimo_ts.pdf_path):
                zip_name = "01_timesheet/{}/{}.pdf".format(
                    collab_safe,
                    Path(ultimo_ts.pdf_filename).stem
                )
                zf.write(ultimo_ts.pdf_path, zip_name)
                file_count += 1
                manifest_lines.append("  [OK] {}".format(zip_name))
            else:
                manifest_lines.append("  [MANCANTE] Timesheet {} - {}".format(
                    collab_safe, assignment.role
                ))

            if collab.curriculum_path:
                ext = Path(collab.curriculum_path).suffix
                zip_name = "02_collaboratori/{}/CV_{}{}" .format(
                    collab_safe, collab_safe, ext
                )
                if _add_file(zf, collab.curriculum_path, zip_name):
                    file_count += 1
                    manifest_lines.append("  [OK] {}".format(zip_name))

            if collab.documento_identita_path:
                ext = Path(collab.documento_identita_path).suffix
                zip_name = "02_collaboratori/{}/CI_{}{}".format(
                    collab_safe, collab_safe, ext
                )
                if _add_file(zf, collab.documento_identita_path, zip_name):
                    file_count += 1
                    manifest_lines.append("  [OK] {}".format(zip_name))

        manifest_lines.append("")
        manifest_lines.append("--- AZIENDE BENEFICIARIE ---")

        links = db.query(AziendaClienteProjectLink).options(
            joinedload(AziendaClienteProjectLink.azienda)
        ).filter(
            AziendaClienteProjectLink.project_id == project_id
        ).all()

        for link in links:
            azienda = link.azienda
            if not azienda:
                continue

            azienda_safe = _safe_zip_component(azienda.ragione_sociale, max_length=30)
            regime = link.regime_aiuto or "regime_non_definito"

            manifest_lines.append("  Azienda: {} | Regime: {}".format(
                azienda.ragione_sociale, regime
            ))

            if regime == "de_minimis":
                if link.dichiarazione_de_minimis:
                    zip_name = "03_beneficiari/{}/dichiarazione_de_minimis.txt".format(azienda_safe)
                    _add_text(zf, link.dichiarazione_de_minimis, zip_name)
                    file_count += 1
                    manifest_lines.append("  [OK] {}".format(zip_name))

                summary = (
                    "RIEPILOGO DE MINIMIS\n"
                    "Azienda: {}\n"
                    "P.IVA: {}\n"
                    "Plafond dichiarato: {} EUR\n"
                    "Regime: de minimis\n"
                    "Progetto: {}\n"
                    "Generato il: {}\n"
                ).format(
                    azienda.ragione_sociale,
                    azienda.partita_iva or "N/D",
                    link.plafond_dichiarato or "N/D",
                    project.name,
                    datetime.now().strftime("%d/%m/%Y")
                )
                zip_name = "03_beneficiari/{}/riepilogo_de_minimis.txt".format(azienda_safe)
                _add_text(zf, summary, zip_name)
                file_count += 1

            elif regime == "esenzione":
                dati_ret = db.query(DatiRetributivi).filter(
                    DatiRetributivi.project_id == project_id
                ).join(
                    Allievo, DatiRetributivi.allievo_id == Allievo.id
                ).filter(
                    Allievo.azienda_cliente_id == azienda.id
                ).all()

                for dr in dati_ret:
                    if dr.busta_paga_path:
                        ext = Path(dr.busta_paga_path).suffix
                        zip_name = "03_beneficiari/{}/buste_paga/busta_{}{}".format(
                            azienda_safe,
                            dr.allievo_id,
                            ext
                        )
                        if _add_file(zf, dr.busta_paga_path, zip_name):
                            file_count += 1
                            manifest_lines.append("  [OK] {}".format(zip_name))

                if link.cofinanziamento_perc:
                    cofinanziamento_txt = (
                        "DICHIARAZIONE COFINANZIAMENTO\n"
                        "Azienda: {}\n"
                        "P.IVA: {}\n"
                        "Percentuale cofinanziamento: {}%\n"
                        "Progetto: {}\n"
                        "Generato il: {}\n"
                    ).format(
                        azienda.ragione_sociale,
                        azienda.partita_iva or "N/D",
                        link.cofinanziamento_perc,
                        project.name,
                        datetime.now().strftime("%d/%m/%Y")
                    )
                    zip_name = "03_beneficiari/{}/dichiarazione_cofinanziamento.txt".format(azienda_safe)
                    _add_text(zf, cofinanziamento_txt, zip_name)
                    file_count += 1

        manifest_lines.extend([
            "",
            "=" * 60,
            "RIEPILOGO",
            "=" * 60,
            "Totale file inclusi: {}".format(file_count),
            "Collaboratori: {}".format(len(assignments)),
            "Aziende beneficiarie: {}".format(len(links)),
            "De minimis: {}".format(len([l for l in links if l.regime_aiuto == "de_minimis"])),
            "Esenzione: {}".format(len([l for l in links if l.regime_aiuto == "esenzione"])),
        ])

        zf.writestr("00_MANIFEST.txt", "\n".join(manifest_lines))

    buffer.seek(0)
    return buffer.read(), zip_filename
