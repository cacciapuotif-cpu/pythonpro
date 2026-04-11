"""Gestisce intake automatico dei documenti ricevuti via email."""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

import models

logger = logging.getLogger(__name__)

DOCUMENT_CATALOG = {
    "curriculum": {
        "entity_types": {"collaborator"},
        "aliases": {"cv", "resume", "curriculum_vitae", "c_v", "curriculum"},
        "hints": {"cv", "curriculum", "resume"},
    },
    "documento_identita": {
        "entity_types": {"collaborator"},
        "aliases": {"carta_identita", "carta_identità", "id_card", "documento_identita", "passport", "patente"},
        "hints": {"carta_identita", "documento_identita", "idcard", "identity", "passport", "patente"},
    },
    "visura_camerale": {
        "entity_types": {"azienda_cliente"},
        "aliases": {"visura", "visura_camerale", "camera_di_commercio", "company_registry_extract"},
        "hints": {"visura", "camerale", "registro_imprese", "camera_commercio"},
    },
    "durc": {
        "entity_types": {"azienda_cliente"},
        "aliases": {"durc", "regolarita_contributiva", "regolarità_contributiva"},
        "hints": {"durc", "regolarita_contributiva", "regolarità_contributiva", "inps", "inail"},
    },
    "certificato_attribuzione_partita_iva": {
        "entity_types": {"azienda_cliente"},
        "aliases": {"attribuzione_partita_iva", "certificato_attribuzione_partita_iva", "agenzia_entrate_piva"},
        "hints": {"attribuzione_partita_iva", "partita_iva", "agenzia_entrate"},
    },
    "statuto": {
        "entity_types": {"azienda_cliente"},
        "aliases": {"statuto", "company_bylaws"},
        "hints": {"statuto", "bylaws"},
    },
    "atto_costitutivo": {
        "entity_types": {"azienda_cliente"},
        "aliases": {"atto_costitutivo", "incorporation_act", "deed_of_incorporation"},
        "hints": {"atto_costitutivo", "costituzione", "incorporation"},
    },
    "documento_generico": {
        "entity_types": {"collaborator", "azienda_cliente", "allievo"},
        "aliases": {"documento", "generic_document", "documento_generico"},
        "hints": set(),
    },
}

DOC_TYPE_ALIASES = {
    alias: canonical
    for canonical, meta in DOCUMENT_CATALOG.items()
    for alias in meta["aliases"]
}


@dataclass
class DocumentIntakeOutcome:
    expected_doc_type: str
    resolved_doc_type: str
    processing_status: str
    documento_richiesto_id: Optional[int] = None
    created_documento_richiesto: bool = False
    collaborator_updated_fields: list[str] = field(default_factory=list)
    note: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DocumentIntakeAgent:
    def infer_expected_doc_type(
        self,
        db,
        *,
        entity_type: Optional[str],
        entity_id: Optional[int],
        subject: Optional[str],
        attachment_name: Optional[str],
    ) -> str:
        guessed = self._guess_doc_type_from_text(subject, attachment_name)
        if guessed:
            return guessed

        if entity_type == "azienda_cliente" and entity_id:
            return "documento_generico"

        if entity_type != "collaborator" or not entity_id:
            return "documento"

        pending = (
            db.query(models.DocumentoRichiesto)
            .filter(
                models.DocumentoRichiesto.collaboratore_id == entity_id,
                models.DocumentoRichiesto.stato.in_(("richiesto", "scaduto", "rifiutato")),
            )
            .order_by(models.DocumentoRichiesto.data_richiesta.desc(), models.DocumentoRichiesto.id.desc())
            .first()
        )
        if pending and pending.tipo_documento:
            return pending.tipo_documento

        return "documento"

    def apply_document_result(
        self,
        db,
        *,
        entity_type: Optional[str],
        entity_id: Optional[int],
        attachment_path: Optional[str],
        attachment_name: Optional[str],
        result,
        expected_doc_type: str,
    ) -> DocumentIntakeOutcome:
        resolved_doc_type = self._normalize_doc_type(result.doc_type or expected_doc_type)
        if not attachment_path:
            return DocumentIntakeOutcome(
                expected_doc_type=expected_doc_type,
                resolved_doc_type=resolved_doc_type,
                processing_status="manual_review",
                note="nessun allegato persistito",
            )

        if entity_type == "azienda_cliente" and entity_id:
            return self._apply_company_document_result(
                db,
                entity_id=entity_id,
                result=result,
                expected_doc_type=expected_doc_type,
                resolved_doc_type=resolved_doc_type,
            )

        if entity_type != "collaborator" or not entity_id:
            return DocumentIntakeOutcome(
                expected_doc_type=expected_doc_type,
                resolved_doc_type=resolved_doc_type,
                processing_status=self._status_from_validity(result.valid),
                note="auto-persist disponibile solo per collaborator",
            )

        collaborator = db.query(models.Collaborator).filter(models.Collaborator.id == entity_id).first()
        if not collaborator:
            return DocumentIntakeOutcome(
                expected_doc_type=expected_doc_type,
                resolved_doc_type=resolved_doc_type,
                processing_status="manual_review",
                note="collaboratore non trovato",
            )

        documento, created_documento = self._find_or_create_documento_richiesto(
            db,
            collaboratore_id=entity_id,
            doc_type=resolved_doc_type,
            expected_doc_type=expected_doc_type,
        )

        documento.file_path = attachment_path
        documento.file_name = attachment_name
        documento.data_caricamento = datetime.now()

        extracted = dict(getattr(result, "extracted_data", {}) or {})
        expiry_date = self._parse_datetime(
            extracted.get("data_scadenza")
            or extracted.get("expiry_date")
            or extracted.get("document_expiry")
        )
        if expiry_date:
            documento.data_scadenza = expiry_date

        updated_fields: list[str] = []
        if result.valid is True:
            documento.stato = "validato"
            documento.validato_da = "email_agent"
            documento.validato_il = datetime.now()
            documento.note_operatore = None
            updated_fields = self._apply_collaborator_updates(
                collaborator,
                doc_type=resolved_doc_type,
                attachment_path=attachment_path,
                attachment_name=attachment_name,
                extracted_data=extracted,
                expiry_date=expiry_date,
            )
        elif result.valid is False:
            documento.stato = "rifiutato"
            documento.validato_da = None
            documento.validato_il = None
            documento.note_operatore = "; ".join(result.issues)[:2000] if result.issues else "Documento rifiutato automaticamente"
        else:
            documento.stato = "caricato"
            documento.validato_da = None
            documento.validato_il = None
            documento.note_operatore = "Richiede revisione manuale"

        db.add(documento)
        db.add(collaborator)
        db.commit()
        db.refresh(documento)

        return DocumentIntakeOutcome(
            expected_doc_type=expected_doc_type,
            resolved_doc_type=resolved_doc_type,
            processing_status=self._status_from_validity(result.valid),
            documento_richiesto_id=documento.id,
            created_documento_richiesto=created_documento,
            collaborator_updated_fields=updated_fields,
        )

    def _find_or_create_documento_richiesto(self, db, *, collaboratore_id: int, doc_type: str, expected_doc_type: str):
        candidate_types = []
        for raw in (doc_type, expected_doc_type):
            normalized = self._normalize_doc_type(raw)
            if normalized and normalized not in candidate_types:
                candidate_types.append(normalized)

        documento = (
            db.query(models.DocumentoRichiesto)
            .filter(
                models.DocumentoRichiesto.collaboratore_id == collaboratore_id,
                models.DocumentoRichiesto.tipo_documento.in_(candidate_types),
            )
            .order_by(models.DocumentoRichiesto.data_richiesta.desc(), models.DocumentoRichiesto.id.desc())
            .first()
        )
        if documento:
            return documento, False

        documento = models.DocumentoRichiesto(
            collaboratore_id=collaboratore_id,
            tipo_documento=candidate_types[0] if candidate_types else "documento_generico",
            descrizione="Creato automaticamente da email inbox",
            obbligatorio=True,
            stato="richiesto",
            data_richiesta=datetime.now(),
        )
        db.add(documento)
        db.flush()
        return documento, True

    def _apply_collaborator_updates(
        self,
        collaborator,
        *,
        doc_type: str,
        attachment_path: Optional[str],
        attachment_name: Optional[str],
        extracted_data: Dict[str, Any],
        expiry_date: Optional[datetime],
    ) -> list[str]:
        updated_fields: list[str] = []

        if doc_type == "documento_identita":
            collaborator.documento_identita_path = attachment_path
            collaborator.documento_identita_filename = attachment_name
            collaborator.documento_identita_uploaded_at = datetime.now()
            collaborator.documento_identita_scadenza = expiry_date
            updated_fields.extend([
                "documento_identita_path",
                "documento_identita_filename",
                "documento_identita_uploaded_at",
                "documento_identita_scadenza",
            ])
        elif doc_type == "curriculum":
            collaborator.curriculum_path = attachment_path
            collaborator.curriculum_filename = attachment_name
            collaborator.curriculum_uploaded_at = datetime.now()
            updated_fields.extend([
                "curriculum_path",
                "curriculum_filename",
                "curriculum_uploaded_at",
            ])

            profile = self._clean_optional_text(
                extracted_data.get("profilo_professionale") or extracted_data.get("profile")
            )
            if profile and not collaborator.profilo_professionale:
                collaborator.profilo_professionale = profile
                updated_fields.append("profilo_professionale")

            skills = extracted_data.get("competenze_principali") or extracted_data.get("skills")
            if skills and not collaborator.competenze_principali:
                if isinstance(skills, list):
                    collaborator.competenze_principali = ", ".join(str(item).strip() for item in skills if str(item).strip())
                else:
                    collaborator.competenze_principali = str(skills).strip()
                if collaborator.competenze_principali:
                    updated_fields.append("competenze_principali")

            education = self._clean_optional_text(extracted_data.get("education") or extracted_data.get("titolo_studio"))
            if education and not collaborator.education:
                collaborator.education = education
                updated_fields.append("education")

        fiscal_code = self._clean_optional_text(extracted_data.get("fiscal_code") or extracted_data.get("codice_fiscale"))
        if fiscal_code:
            fiscal_code = fiscal_code.upper().replace(" ", "")
            if not collaborator.fiscal_code:
                collaborator.fiscal_code = fiscal_code
                updated_fields.append("fiscal_code")
            elif collaborator.fiscal_code.upper() != fiscal_code:
                logger.warning(
                    "DocumentIntakeAgent: fiscal code estratto %s diverso da collaboratore %s (%s), skip overwrite",
                    fiscal_code,
                    collaborator.id,
                    collaborator.fiscal_code,
                )

        partita_iva = self._clean_optional_text(extracted_data.get("partita_iva") or extracted_data.get("vat_number"))
        if partita_iva and not collaborator.partita_iva:
            collaborator.partita_iva = partita_iva.replace("IT", "").replace(" ", "")
            updated_fields.append("partita_iva")

        return updated_fields

    def _apply_company_document_result(
        self,
        db,
        *,
        entity_id: int,
        result,
        expected_doc_type: str,
        resolved_doc_type: str,
    ) -> DocumentIntakeOutcome:
        azienda = db.query(models.AziendaCliente).filter(models.AziendaCliente.id == entity_id).first()
        if not azienda:
            return DocumentIntakeOutcome(
                expected_doc_type=expected_doc_type,
                resolved_doc_type=resolved_doc_type,
                processing_status="manual_review",
                note="azienda cliente non trovata",
            )

        extracted = dict(getattr(result, "extracted_data", {}) or {})
        updated_fields = self._apply_company_updates(
            azienda,
            doc_type=resolved_doc_type,
            extracted_data=extracted,
        )
        db.add(azienda)
        db.commit()

        return DocumentIntakeOutcome(
            expected_doc_type=expected_doc_type,
            resolved_doc_type=resolved_doc_type,
            processing_status=self._status_from_validity(result.valid),
            collaborator_updated_fields=updated_fields,
            note="azienda_cliente aggiornato da documento" if updated_fields else None,
        )

    def _apply_company_updates(
        self,
        azienda,
        *,
        doc_type: str,
        extracted_data: Dict[str, Any],
    ) -> list[str]:
        if doc_type == "visura_camerale":
            updates = {
                "ragione_sociale": self._clean_optional_text(extracted_data.get("ragione_sociale") or extracted_data.get("company_name")),
                "partita_iva": self._clean_optional_text(extracted_data.get("partita_iva") or extracted_data.get("vat_number")),
                "codice_fiscale": self._clean_optional_text(extracted_data.get("codice_fiscale") or extracted_data.get("tax_code")),
                "settore_ateco": self._clean_optional_text(extracted_data.get("settore_ateco") or extracted_data.get("codice_ateco") or extracted_data.get("ateco")),
                "indirizzo": self._clean_optional_text(extracted_data.get("indirizzo") or extracted_data.get("sede_legale_indirizzo") or extracted_data.get("address")),
                "citta": self._clean_optional_text(extracted_data.get("citta") or extracted_data.get("sede_legale_citta") or extracted_data.get("city")),
                "cap": self._clean_optional_text(extracted_data.get("cap") or extracted_data.get("sede_legale_cap") or extracted_data.get("zip_code")),
                "provincia": self._clean_optional_text(extracted_data.get("provincia") or extracted_data.get("sede_legale_provincia")),
                "pec": self._clean_optional_text(extracted_data.get("pec")),
                "email": self._clean_optional_text(extracted_data.get("email")),
                "telefono": self._clean_optional_text(extracted_data.get("telefono") or extracted_data.get("phone")),
                "legale_rappresentante_nome": self._clean_optional_text(extracted_data.get("legale_rappresentante_nome") or extracted_data.get("legal_representative_first_name")),
                "legale_rappresentante_cognome": self._clean_optional_text(extracted_data.get("legale_rappresentante_cognome") or extracted_data.get("legal_representative_last_name")),
                "legale_rappresentante_codice_fiscale": self._clean_optional_text(extracted_data.get("legale_rappresentante_codice_fiscale") or extracted_data.get("legal_representative_tax_code")),
                "legale_rappresentante_email": self._clean_optional_text(extracted_data.get("legale_rappresentante_email")),
                "legale_rappresentante_telefono": self._clean_optional_text(extracted_data.get("legale_rappresentante_telefono")),
                "attivita_erogate": self._clean_optional_text(extracted_data.get("oggetto_sociale") or extracted_data.get("attivita_erogate") or extracted_data.get("company_activity")),
                "note": self._build_company_note(doc_type, extracted_data),
            }
            return self._apply_company_field_updates(azienda, updates)

        if doc_type == "certificato_attribuzione_partita_iva":
            updates = {
                "ragione_sociale": self._clean_optional_text(extracted_data.get("ragione_sociale") or extracted_data.get("company_name")),
                "partita_iva": self._clean_optional_text(extracted_data.get("partita_iva") or extracted_data.get("vat_number")),
                "codice_fiscale": self._clean_optional_text(extracted_data.get("codice_fiscale") or extracted_data.get("tax_code")),
                "indirizzo": self._clean_optional_text(extracted_data.get("indirizzo") or extracted_data.get("sede_legale_indirizzo") or extracted_data.get("address")),
                "citta": self._clean_optional_text(extracted_data.get("citta") or extracted_data.get("sede_legale_citta") or extracted_data.get("city")),
                "cap": self._clean_optional_text(extracted_data.get("cap") or extracted_data.get("sede_legale_cap") or extracted_data.get("zip_code")),
                "provincia": self._clean_optional_text(extracted_data.get("provincia") or extracted_data.get("sede_legale_provincia")),
                "attivita_erogate": self._clean_optional_text(extracted_data.get("attivita_erogate") or extracted_data.get("attivita") or extracted_data.get("company_activity")),
                "note": self._build_company_note(doc_type, extracted_data),
            }
            return self._apply_company_field_updates(azienda, updates)

        if doc_type in {"statuto", "atto_costitutivo"}:
            updates = {
                "ragione_sociale": self._clean_optional_text(extracted_data.get("ragione_sociale") or extracted_data.get("company_name")),
                "partita_iva": self._clean_optional_text(extracted_data.get("partita_iva") or extracted_data.get("vat_number")),
                "codice_fiscale": self._clean_optional_text(extracted_data.get("codice_fiscale") or extracted_data.get("tax_code")),
                "attivita_erogate": self._clean_optional_text(extracted_data.get("oggetto_sociale") or extracted_data.get("company_activity")),
                "note": self._build_company_note(doc_type, extracted_data),
            }
            return self._apply_company_field_updates(azienda, updates)

        if doc_type == "durc":
            updates = {
                "ragione_sociale": self._clean_optional_text(extracted_data.get("ragione_sociale") or extracted_data.get("company_name")),
                "partita_iva": self._clean_optional_text(extracted_data.get("partita_iva") or extracted_data.get("vat_number")),
                "codice_fiscale": self._clean_optional_text(extracted_data.get("codice_fiscale") or extracted_data.get("tax_code")),
                "pec": self._clean_optional_text(extracted_data.get("pec")),
                "email": self._clean_optional_text(extracted_data.get("email")),
                "telefono": self._clean_optional_text(extracted_data.get("telefono") or extracted_data.get("phone")),
                "note": self._build_company_note(doc_type, extracted_data),
            }
            return self._apply_company_field_updates(azienda, updates)

        generic_fields = {
            "ragione_sociale": self._clean_optional_text(extracted_data.get("ragione_sociale") or extracted_data.get("company_name")),
            "partita_iva": self._clean_optional_text(extracted_data.get("partita_iva") or extracted_data.get("vat_number")),
            "codice_fiscale": self._clean_optional_text(extracted_data.get("codice_fiscale") or extracted_data.get("tax_code")),
            "pec": self._clean_optional_text(extracted_data.get("pec")),
            "email": self._clean_optional_text(extracted_data.get("email")),
            "telefono": self._clean_optional_text(extracted_data.get("telefono") or extracted_data.get("phone")),
            "note": self._build_company_note(doc_type, extracted_data),
        }
        return self._apply_company_field_updates(azienda, generic_fields)

    def _apply_company_field_updates(self, azienda, updates: Dict[str, Optional[str]]) -> list[str]:
        updated_fields: list[str] = []
        for field_name, value in updates.items():
            if value is None:
                continue
            normalized_value = value
            if field_name == "partita_iva":
                normalized_value = value.replace("IT", "").replace(" ", "")
            elif field_name in {"codice_fiscale", "legale_rappresentante_codice_fiscale"}:
                normalized_value = value.replace(" ", "").upper()
            elif field_name == "provincia":
                normalized_value = value.upper()
            elif field_name == "note":
                normalized_value = self._merge_note(getattr(azienda, "note", None), value)

            if getattr(azienda, field_name, None) != normalized_value:
                setattr(azienda, field_name, normalized_value)
                updated_fields.append(field_name)

        return updated_fields

    def _build_company_note(self, doc_type: str, extracted_data: Dict[str, Any]) -> Optional[str]:
        relevant = {
            key: value
            for key, value in extracted_data.items()
            if value not in (None, "", [], {})
        }
        if not relevant:
            return None
        return f"[{doc_type}] " + ", ".join(f"{key}={value}" for key, value in sorted(relevant.items()))

    def _merge_note(self, existing: Optional[str], new_fragment: str) -> str:
        base = (existing or "").strip()
        if new_fragment in base:
            return base
        if not base:
            return new_fragment
        return f"{base}\n{new_fragment}"[:5000]

    def _guess_doc_type_from_text(self, subject: Optional[str], attachment_name: Optional[str]) -> Optional[str]:
        haystack = f"{subject or ''} {attachment_name or ''}".lower()
        haystack = haystack.replace(" ", "_")
        for doc_type, meta in DOCUMENT_CATALOG.items():
            hints = meta.get("hints") or set()
            if any(hint in haystack for hint in hints):
                return doc_type
        return None

    def _normalize_doc_type(self, raw: Optional[str]) -> str:
        value = (raw or "documento").strip().lower().replace(" ", "_")
        return DOC_TYPE_ALIASES.get(value, value or "documento_generico")

    def _status_from_validity(self, valid: Optional[bool]) -> str:
        if valid is True:
            return "valid"
        if valid is False:
            return "invalid"
        return "manual_review"

    def _parse_datetime(self, value: Any) -> Optional[datetime]:
        if value in (None, ""):
            return None
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            logger.debug("DocumentIntakeAgent: data non parseabile %r", value)
            return None

    def _clean_optional_text(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None
