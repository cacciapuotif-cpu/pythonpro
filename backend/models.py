from sqlalchemy import Column, Integer, String, DateTime, Date, ForeignKey, Table, Text, Float, Numeric, Index, Boolean, UniqueConstraint, CheckConstraint, JSON, text, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship, validates, foreign
from sqlalchemy.sql import func
from sqlalchemy.ext.hybrid import hybrid_property
from database import Base
from money_utils import quantize_euro, quantize_ore, to_decimal
from typing import Optional
import re

# TABELLA DI ASSOCIAZIONE per la relazione many-to-many
# Un collaboratore può lavorare su più progetti e un progetto può avere più collaboratori
collaborator_project = Table(
    'collaborator_project',  # Nome della tabella di collegamento
    Base.metadata,
    # Colonna che punta al collaboratore
    Column('collaborator_id', Integer, ForeignKey('collaborators.id', ondelete="CASCADE"), primary_key=True),
    # Colonna che punta al progetto
    Column('project_id', Integer, ForeignKey('projects.id', ondelete="CASCADE"), primary_key=True)
)

class AllievoProject(Base):
    __tablename__ = 'allievo_project'

    allievo_id = Column(Integer, ForeignKey('allievi.id', ondelete="CASCADE"), primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey('projects.id', ondelete="CASCADE"), primary_key=True, index=True)
    id = Column(Integer, nullable=True)
    ore_frequentate = Column(Numeric(8, 2), default=0.0, nullable=True)
    stato = Column(String(30), default='iscritto', nullable=True)
    attestato_emesso = Column(Boolean, default=False, nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=True)

allievo_project = AllievoProject.__table__

class Collaborator(Base):
    __tablename__ = "collaborators"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String(50), nullable=False, index=True)
    last_name = Column(String(50), nullable=False, index=True)
    email = Column(String(100), unique=True, index=True, nullable=False)
    phone = Column(String(20))
    position = Column(String(100), index=True)

    birthplace = Column(String(100))
    birth_date = Column(DateTime)
    gender = Column(String(10))
    fiscal_code = Column(String(16), unique=True, index=True, nullable=False)
    partita_iva = Column(String(11), unique=True, index=True)
    city = Column(String(100))
    address = Column(String(200))
    education = Column(String(50))
    profilo_professionale = Column(Text)
    competenze_principali = Column(Text)
    certificazioni = Column(Text)
    sito_web = Column(String(255))
    portfolio_url = Column(String(255))
    linkedin_url = Column(String(255))
    facebook_url = Column(String(255))
    instagram_url = Column(String(255))
    tiktok_url = Column(String(255))
    is_agency = Column(Boolean, default=False, index=True)
    is_consultant = Column(Boolean, default=False, index=True)

    # Campi per performance e sicurezza
    is_active = Column(Boolean, default=True, index=True)
    last_login = Column(DateTime)

    # Campi per documenti allegati
    documento_identita_filename = Column(String(255))  # Nome file originale
    documento_identita_path = Column(String(500))      # Path storage
    documento_identita_uploaded_at = Column(DateTime)  # Data upload
    documento_identita_scadenza = Column(DateTime)     # Data scadenza documento

    curriculum_filename = Column(String(255))          # Nome file originale
    curriculum_path = Column(String(500))              # Path storage
    curriculum_uploaded_at = Column(DateTime)          # Data upload

    consenso_email_agenti = Column(Boolean, nullable=False, default=False, server_default=text("false"), index=True)
    consenso_whatsapp_agenti = Column(Boolean, nullable=False, default=False, server_default=text("false"), index=True)
    anonimizzato = Column(Boolean, nullable=False, default=False, server_default=text("false"), index=True)
    data_anonimizzazione = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relazioni ottimizzate con lazy loading
    projects = relationship("Project", secondary=collaborator_project, back_populates="collaborators", lazy="select")
    attendances = relationship("Attendance", back_populates="collaborator", lazy="select")
    assignments = relationship("Assignment", back_populates="collaborator", lazy="select")
    linked_agency = relationship("Agenzia", back_populates="source_collaborator", uselist=False, lazy="select")

    # Proprietà calcolate per performance
    @hybrid_property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    # Validazioni
    @validates('email')
    def validate_email(self, key, address):
        if not re.match(r'^[^@]+@[^@]+\.[^@]+$', address):
            raise ValueError("Email non valida")
        return address.lower()

    @validates('fiscal_code')
    def validate_fiscal_code(self, key, code):
        if code and len(code) != 16:
            raise ValueError("Codice fiscale deve essere di 16 caratteri")
        return code.upper() if code else code

    @validates('partita_iva')
    def validate_partita_iva(self, key, piva):
        if piva:
            piva_clean = piva.replace(' ', '').replace('IT', '').replace('it', '')
            if not piva_clean.isdigit() or len(piva_clean) != 11:
                raise ValueError("Partita IVA deve essere di 11 cifre numeriche")
            return piva_clean
        return piva

    # NB: l'indice PG-only idx_collab_fulltext_search (lower(first_name),
    # lower(last_name)) vive solo nel DB: usa un cast ::text non valido su
    # SQLite (usato dai test) ed e' escluso dal confronto autogenerate in
    # alembic/env.py.
    __table_args__ = (
        Index("idx_collab_city", "city"),
        Index("idx_collab_active_created", "is_active", text("created_at DESC")),
    )


class GDPRConsenso(Base):
    __tablename__ = "gdpr_consensi"

    id = Column(Integer, primary_key=True, index=True)
    collaboratore_id = Column(Integer, ForeignKey("collaborators.id", ondelete="CASCADE"), nullable=False, index=True)
    tipo_consenso = Column(String(50), nullable=False, index=True)
    data_consenso = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ip_address_hash = Column(String(64), nullable=True)
    revocato = Column(Boolean, nullable=False, default=False, server_default=text("false"), index=True)
    data_revoca = Column(DateTime(timezone=True), nullable=True)

    collaboratore = relationship("Collaborator", backref="gdpr_consensi")



class SecurityAuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    azione = Column(String(100), nullable=False, index=True)
    risorsa_tipo = Column(String(100), nullable=False, index=True)
    risorsa_id = Column(String(100), nullable=True, index=True)
    dati_prima = Column(Text, nullable=True)
    dati_dopo = Column(Text, nullable=True)
    ip_address_hash = Column(String(64), nullable=True)
    esito = Column(String(50), nullable=False, default="success", index=True)

    __table_args__ = (
        Index("ix_audit_log_risorsa", "risorsa_tipo", "risorsa_id"),
    )


class DocumentoRichiesto(Base):
    __tablename__ = "documenti_richiesti"

    id = Column(Integer, primary_key=True, index=True)
    collaboratore_id = Column(Integer, ForeignKey("collaborators.id", ondelete="CASCADE"), nullable=False, index=True)
    tipo_documento = Column(String(100), nullable=False, index=True)
    descrizione = Column(Text)
    obbligatorio = Column(Boolean, nullable=False, default=True)
    data_richiesta = Column(DateTime, nullable=False, default=func.now())
    data_scadenza = Column(DateTime, nullable=True, index=True)
    data_caricamento = Column(DateTime, nullable=True)
    stato = Column(String(20), nullable=False, default="richiesto", index=True)
    file_path = Column(String(500), nullable=True)
    file_name = Column(String(255), nullable=True)
    note_operatore = Column(Text)
    validato_da = Column(String(100))
    validato_il = Column(DateTime)

    collaboratore = relationship("Collaborator", backref="documenti_richiesti")

    @validates("stato")
    def validate_stato(self, key, value):
        stati_validi = {"richiesto", "caricato", "validato", "rifiutato", "scaduto"}
        if value not in stati_validi:
            raise ValueError(f"stato deve essere uno di: {sorted(stati_validi)}")
        return value


class Notifica(Base):
    __tablename__ = "notifiche"

    id = Column(Integer, primary_key=True, index=True)
    tipo = Column(String(50), nullable=False, index=True)
    titolo = Column(String(200), nullable=False)
    messaggio = Column(Text, nullable=False)
    destinatario_id = Column(Integer, ForeignKey("collaborators.id", ondelete="SET NULL"), nullable=True, index=True)
    destinatario_email = Column(String(100), nullable=True, index=True)
    letta = Column(Boolean, nullable=False, default=False, index=True)
    inviata_email = Column(Boolean, nullable=False, default=False)
    data_invio_email = Column(DateTime, nullable=True)
    riferimento_tipo = Column(String(50), nullable=True, index=True)
    riferimento_id = Column(Integer, nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    destinatario = relationship("Collaborator", backref="notifiche")

    @validates("tipo")
    def validate_tipo(self, key, value):
        tipi_validi = {"documento_mancante", "documento_scadenza", "assegnazione", "sistema"}
        if value not in tipi_validi:
            raise ValueError(f"tipo deve essere uno di: {sorted(tipi_validi)}")
        return value

    @validates("riferimento_tipo")
    def validate_riferimento_tipo(self, key, value):
        if value is None:
            return value
        tipi_validi = {"documento", "assegnazione", "progetto"}
        if value not in tipi_validi:
            raise ValueError(f"riferimento_tipo deve essere uno di: {sorted(tipi_validi)}")
        return value

    __table_args__ = (
        Index("idx_notifiche_destinatario_letta", "destinatario_id", "letta"),
        Index("idx_notifiche_email_letta", "destinatario_email", "letta"),
    )

class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    description = Column(Text)
    start_date = Column(DateTime, index=True)
    end_date = Column(DateTime, index=True)
    status = Column(String(20), default="active", index=True)
    cup = Column(String(50), index=True)
    id_piano_esterno = Column(String(50), nullable=True, index=True)
    atto_approvazione = Column(String(255))
    sede_aziendale_comune = Column(String(100))
    sede_aziendale_via = Column(String(200))
    sede_aziendale_numero_civico = Column(String(20))
    ente_erogatore = Column(String(100), nullable=True, index=True)
    avviso = Column(String(100), nullable=True, index=True)
    avviso_id = Column(
        Integer,
        ForeignKey("avvisi.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
        index=True,
    )
    avviso_revisione_id = Column(
        Integer,
        ForeignKey("avviso_revisioni.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
        index=True,
    )
    # FK verso ImplementingEntity (Ente Attuatore)
    ente_attuatore_id = Column(Integer, ForeignKey("implementing_entities.id", ondelete="SET NULL"), nullable=True, index=True)

    # Campi FAPI
    codice_fapi = Column(String(30), unique=True, nullable=True, index=True)
    delibera_numero = Column(String(20), nullable=True)
    delibera_data = Column(Date, nullable=True)
    data_approvazione = Column(Date, nullable=True)
    costo_totale = Column(Numeric(12, 2), nullable=True)
    contributo_ente = Column(Numeric(12, 2), nullable=True)
    cofinanziamento = Column(Numeric(12, 2), nullable=True)
    convenzione_file_path = Column(String(500), nullable=True)

    # Campi per performance
    priority = Column(Integer, default=1, index=True)
    budget = Column(Numeric(12, 2))
    ore_totali = Column(Numeric(8, 2), default=0.0, nullable=False)
    ore_completate = Column(Numeric(8, 2), default=0.0, nullable=False)
    progress_percentage = Column(Float, default=0.0, nullable=False)
    is_active = Column(Boolean, default=True, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relazioni ottimizzate
    collaborators = relationship("Collaborator", secondary=collaborator_project, back_populates="projects", lazy="select")
    allievi_coinvolti = relationship("Allievo", secondary=allievo_project, back_populates="projects", lazy="select")
    attendances = relationship("Attendance", back_populates="project", lazy="select")
    assignments = relationship("Assignment", back_populates="project", lazy="select")
    azienda_links = relationship("AziendaClienteProjectLink", back_populates="project", lazy="select")
    aziende_coinvolte = relationship("AziendaCliente", secondary="azienda_cliente_projects", lazy="select", viewonly=True)
    ente_attuatore = relationship("ImplementingEntity", back_populates="projects", lazy="select")
    avviso_rel = relationship("Avviso", back_populates="projects", lazy="select")
    avviso_revisione = relationship("AvvisoRevisione", foreign_keys=[avviso_revisione_id], lazy="select")
    piani_finanziari = relationship("PianoFinanziario", back_populates="progetto", lazy="select", cascade="all, delete-orphan")

    # Proprietà calcolate
    @hybrid_property
    def is_current(self):
        from datetime import datetime
        now = datetime.now()
        return (self.start_date <= now <= self.end_date) if self.start_date and self.end_date else True

    @validates('status')
    def validate_status(self, key, status):
        valid_statuses = ['active', 'completed', 'paused', 'cancelled']
        if status not in valid_statuses:
            raise ValueError(f"Status deve essere uno di: {valid_statuses}")
        return status

    @property
    def resolved_ente_erogatore(self):
        return self.ente_erogatore

    @property
    def resolved_avviso(self):
        return self.avviso

    @property
    def azienda_ids(self):
        if self.azienda_links:
            return [link.azienda_cliente_id for link in self.azienda_links]
        return []

    @property
    def allievo_ids(self):
        if self.allievi_coinvolti:
            return [allievo.id for allievo in self.allievi_coinvolti]
        return []

class Avviso(Base):
    __tablename__ = "avvisi"

    id = Column(Integer, primary_key=True, index=True)
    codice = Column(String(50), nullable=False)
    ente_erogatore = Column(String(100), nullable=False, index=True)
    descrizione = Column(String(200), nullable=True)
    fondo = Column(String(20), nullable=False, default="altro", server_default="altro", index=True)
    numero = Column(String(50), nullable=False, index=True)
    anno = Column(Integer, nullable=False, index=True)
    titolo = Column(String(300), nullable=False)
    descrizione_breve = Column(Text, nullable=True)
    stato = Column(String(20), nullable=False, default="bozza", server_default="bozza", index=True)
    revisione_corrente_id = Column(
        Integer,
        ForeignKey("avviso_revisioni.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
        index=True,
    )
    template_id = Column(
        Integer,
        ForeignKey("contract_templates.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
        index=True,
    )
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    template = relationship("ContractTemplate", back_populates="avvisi", lazy="select")
    projects = relationship("Project", back_populates="avviso_rel", lazy="select")
    revisioni = relationship(
        "AvvisoRevisione",
        foreign_keys="AvvisoRevisione.avviso_id",
        back_populates="avviso",
        lazy="select",
    )
    revisione_corrente = relationship(
        "AvvisoRevisione",
        foreign_keys=[revisione_corrente_id],
        post_update=True,
        lazy="select",
    )
    piani_finanziari = relationship(
        "PianoFinanziario",
        primaryjoin="foreign(PianoFinanziario.avviso_pf_id) == Avviso.id",
        lazy="select",
        viewonly=True,
    )

    __table_args__ = (
        Index("idx_unique_avvisi_codice_ente", "codice", "ente_erogatore", unique=True),
        Index("uq_avvisi_identita", "fondo", "ente_erogatore", "numero", "anno", unique=True),
        CheckConstraint(
            "fondo IN ('fondimpresa','formazienda','fapi','regionale','altro')",
            name="ck_avvisi_fondo",
        ),
        CheckConstraint(
            "stato IN ('bozza','attivo','in_scadenza','scaduto','archiviato')",
            name="ck_avvisi_stato",
        ),
        CheckConstraint("anno IS NULL OR anno BETWEEN 2000 AND 2100", name="ck_avvisi_anno"),
    )


AVVISO_JSON_TYPE = JSON().with_variant(JSONB(), "postgresql")


class AvvisoRevisione(Base):
    __tablename__ = "avviso_revisioni"

    id = Column(Integer, primary_key=True, index=True)
    avviso_id = Column(Integer, ForeignKey("avvisi.id", ondelete="RESTRICT"), nullable=False, index=True)
    numero_revisione = Column(Integer, nullable=False)
    etichetta_revisione = Column(String(50), nullable=True)
    revisione_precedente_id = Column(
        Integer, ForeignKey("avviso_revisioni.id", ondelete="SET NULL"), nullable=True, index=True
    )
    titolo = Column(String(300), nullable=False)
    descrizione_breve = Column(Text, nullable=True)
    data_pubblicazione = Column(Date, nullable=True, index=True)
    data_scadenza_presentazione = Column(DateTime(timezone=True), nullable=True, index=True)
    source_md_path = Column(String(500), nullable=True)
    cleaned_md_path = Column(String(500), nullable=True)
    source_pdf_path = Column(String(500), nullable=True)
    original_filename = Column(String(255), nullable=True)
    source_sha256 = Column(String(64), nullable=True)
    stato_estrazione = Column(String(30), nullable=False, default="caricato", server_default="caricato", index=True)
    diff_from_previous = Column(AVVISO_JSON_TYPE, nullable=True)
    extraction_run_id = Column(Integer, ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    avviso = relationship("Avviso", foreign_keys=[avviso_id], back_populates="revisioni")
    revisione_precedente = relationship("AvvisoRevisione", remote_side=[id], lazy="select")
    regole = relationship("AvvisoRegola", back_populates="revisione", lazy="select")
    scadenze = relationship("AvvisoScadenza", back_populates="revisione", lazy="select")

    __table_args__ = (
        UniqueConstraint("avviso_id", "numero_revisione", name="uq_avviso_revisioni_numero"),
        UniqueConstraint("avviso_id", "source_sha256", name="uq_avviso_revisioni_sha256"),
        CheckConstraint("numero_revisione > 0", name="ck_avviso_revisioni_numero_positivo"),
        CheckConstraint(
            "stato_estrazione IN ('caricato','pulito','segmentato','in_estrazione','estratto','errore')",
            name="ck_avviso_revisioni_stato_estrazione",
        ),
    )


class AvvisoRegola(Base):
    __tablename__ = "avviso_regole"

    id = Column(Integer, primary_key=True, index=True)
    avviso_revisione_id = Column(
        Integer, ForeignKey("avviso_revisioni.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    categoria = Column(String(30), nullable=False, index=True)
    sottocategoria = Column(String(80), nullable=True, index=True)
    chiave = Column(String(150), nullable=False, index=True)
    valore = Column(AVVISO_JSON_TYPE, nullable=False)
    tipo_valore = Column(String(30), nullable=False, default="oggetto", server_default="oggetto")
    schema_version = Column(Integer, nullable=False, default=1, server_default="1")
    unita = Column(String(50), nullable=True)
    applicabilita = Column(AVVISO_JSON_TYPE, nullable=True)
    testo_originale = Column(Text, nullable=False)
    riferimento_articolo = Column(String(120), nullable=True)
    riferimento_sezione = Column(String(200), nullable=True)
    riferimento_pagina = Column(String(50), nullable=True)
    source_quote_sha256 = Column(String(64), nullable=True)
    stato = Column(String(20), nullable=False, default="proposta", server_default="proposta", index=True)
    confidence = Column(Numeric(5, 4), nullable=True)
    needs_careful_review = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    origin_suggestion_id = Column(
        Integer, ForeignKey("agent_suggestions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    carried_from_rule_id = Column(Integer, ForeignKey("avviso_regole.id", ondelete="SET NULL"), nullable=True)
    supersedes_rule_id = Column(Integer, ForeignKey("avviso_regole.id", ondelete="SET NULL"), nullable=True)
    validata_da_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    validata_il = Column(DateTime(timezone=True), nullable=True)
    nota_revisione = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    revisione = relationship("AvvisoRevisione", back_populates="regole")

    __table_args__ = (
        Index("ix_avviso_regole_revision_categoria_chiave", "avviso_revisione_id", "categoria", "chiave"),
        Index("ix_avviso_regole_revision_stato", "avviso_revisione_id", "stato"),
        CheckConstraint(
            "categoria IN ('massimali','parametri_costo','destinatari','beneficiari','aiuti_di_stato','presentazione','valutazione','attuazione','rendicontazione','delega','variazioni','altro')",
            name="ck_avviso_regole_categoria",
        ),
        CheckConstraint(
            "stato IN ('proposta','validata','rifiutata','superata')",
            name="ck_avviso_regole_stato",
        ),
        CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 1)", name="ck_avviso_regole_confidence"),
        CheckConstraint("length(trim(chiave)) > 0", name="ck_avviso_regole_chiave_non_vuota"),
        CheckConstraint("length(trim(testo_originale)) > 0", name="ck_avviso_regole_testo_non_vuoto"),
        CheckConstraint(
            "(stato <> 'validata') OR (validata_da_user_id IS NOT NULL AND validata_il IS NOT NULL)",
            name="ck_avviso_regole_validazione_completa",
        ),
    )


class AvvisoScadenza(Base):
    __tablename__ = "avviso_scadenze"

    id = Column(Integer, primary_key=True, index=True)
    avviso_revisione_id = Column(
        Integer, ForeignKey("avviso_revisioni.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    tipo = Column(String(30), nullable=False, index=True)
    data = Column(DateTime(timezone=True), nullable=False, index=True)
    finestra_inizio = Column(DateTime(timezone=True), nullable=True)
    finestra_fine = Column(DateTime(timezone=True), nullable=True)
    descrizione = Column(Text, nullable=False)
    tassativa = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    condizione = Column(Text, nullable=True)
    applicabilita = Column(AVVISO_JSON_TYPE, nullable=True)
    testo_originale = Column(Text, nullable=False)
    riferimento_articolo = Column(String(120), nullable=True)
    stato = Column(String(20), nullable=False, default="proposta", server_default="proposta", index=True)
    confidence = Column(Numeric(5, 4), nullable=True)
    needs_careful_review = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    origin_suggestion_id = Column(
        Integer, ForeignKey("agent_suggestions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    validata_da_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    validata_il = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    revisione = relationship("AvvisoRevisione", back_populates="scadenze")

    __table_args__ = (
        UniqueConstraint(
            "avviso_revisione_id", "tipo", "data", "descrizione", name="uq_avviso_scadenze_esatta"
        ),
        Index("ix_avviso_scadenze_data_stato", "data", "stato"),
        CheckConstraint(
            "tipo IN ('presentazione','avvio','chiusura','rendicontazione','altro')",
            name="ck_avviso_scadenze_tipo",
        ),
        CheckConstraint(
            "stato IN ('proposta','validata','rifiutata','superata')",
            name="ck_avviso_scadenze_stato",
        ),
        CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 1)", name="ck_avviso_scadenze_confidence"),
        CheckConstraint(
            "finestra_inizio IS NULL OR finestra_fine IS NULL OR finestra_fine >= finestra_inizio",
            name="ck_avviso_scadenze_finestra",
        ),
        CheckConstraint(
            "(stato <> 'validata') OR (validata_da_user_id IS NOT NULL AND validata_il IS NOT NULL)",
            name="ck_avviso_scadenze_validazione_completa",
        ),
    )


class AvvisoDocumento(Base):
    __tablename__ = "avviso_documenti"

    id = Column(Integer, primary_key=True, index=True)
    avviso_id = Column(Integer, ForeignKey("avvisi.id", ondelete="RESTRICT"), nullable=False, index=True)
    avviso_revisione_id = Column(
        Integer, ForeignKey("avviso_revisioni.id", ondelete="SET NULL"), nullable=True, index=True
    )
    tipo = Column(String(30), nullable=False, index=True)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    mime_type = Column(String(100), nullable=True)
    sha256 = Column(String(64), nullable=False)
    note = Column(Text, nullable=True)
    uploaded_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint("avviso_id", "sha256", name="uq_avviso_documenti_sha256"),
        Index("ix_avviso_documenti_avviso_tipo", "avviso_id", "tipo"),
        CheckConstraint(
            "tipo IN ('avviso','allegato','vademecum','manuale_gestione','nota_interna','controdeduzione','altro')",
            name="ck_avviso_documenti_tipo",
        ),
        CheckConstraint("length(sha256) = 64", name="ck_avviso_documenti_sha256"),
    )


class AvvisoConoscenza(Base):
    __tablename__ = "avviso_conoscenze"

    id = Column(Integer, primary_key=True, index=True)
    avviso_id = Column(Integer, ForeignKey("avvisi.id", ondelete="RESTRICT"), nullable=False, index=True)
    avviso_revisione_id = Column(
        Integer, ForeignKey("avviso_revisioni.id", ondelete="SET NULL"), nullable=True, index=True
    )
    tipo = Column(String(30), nullable=False, default="nota_operativa", server_default="nota_operativa", index=True)
    contenuto = Column(Text, nullable=False)
    tags = Column(AVVISO_JSON_TYPE, nullable=True)
    riservatezza = Column(String(20), nullable=False, default="interna", server_default="interna")
    autore_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("length(trim(contenuto)) > 0", name="ck_avviso_conoscenze_contenuto"),
        CheckConstraint(
            "riservatezza IN ('interna','ristretta')", name="ck_avviso_conoscenze_riservatezza"
        ),
    )


class AvvisoEsitoProgetto(Base):
    __tablename__ = "avviso_esiti_progetto"

    id = Column(Integer, primary_key=True, index=True)
    avviso_id = Column(Integer, ForeignKey("avvisi.id", ondelete="RESTRICT"), nullable=False, index=True)
    avviso_revisione_id = Column(
        Integer, ForeignKey("avviso_revisioni.id", ondelete="SET NULL"), nullable=True, index=True
    )
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False, index=True)
    piano_finanziario_id = Column(
        Integer, ForeignKey("piani_finanziari.id", ondelete="SET NULL"), nullable=True, index=True
    )
    esito = Column(String(30), nullable=False, index=True)
    data_evento = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    importo_richiesto = Column(Numeric(12, 2), nullable=True)
    importo_ammesso = Column(Numeric(12, 2), nullable=True)
    importo_rendicontato = Column(Numeric(12, 2), nullable=True)
    importo_riconosciuto = Column(Numeric(12, 2), nullable=True)
    importo_decurtato = Column(Numeric(12, 2), nullable=True)
    note = Column(Text, nullable=True)
    documento_id = Column(Integer, ForeignKey("avviso_documenti.id", ondelete="SET NULL"), nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    __table_args__ = (
        Index("ix_avviso_esiti_project_data", "project_id", "data_evento"),
        CheckConstraint(
            "esito IN ('approvato','rigettato','attuato','rendicontato','decurtato','controdedotto')",
            name="ck_avviso_esiti_esito",
        ),
        CheckConstraint(
            "COALESCE(importo_richiesto,0) >= 0 AND COALESCE(importo_ammesso,0) >= 0 "
            "AND COALESCE(importo_rendicontato,0) >= 0 AND COALESCE(importo_riconosciuto,0) >= 0 "
            "AND COALESCE(importo_decurtato,0) >= 0",
            name="ck_avviso_esiti_importi_non_negativi",
        ),
    )

class Attendance(Base):
    __tablename__ = "attendances"

    id = Column(Integer, primary_key=True, index=True)

    # Chiavi esterne con indici per performance
    collaborator_id = Column(Integer, ForeignKey("collaborators.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id", ondelete="SET NULL"), nullable=True, index=True)

    # Informazioni temporali con indici per query di range
    date = Column(DateTime, nullable=False, index=True)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    hours = Column(Numeric(6, 2), nullable=False, index=True)

    # Campi aggiuntivi per analisi
    notes = Column(Text)
    overtime_hours = Column(Numeric(6, 2), default=0.0)
    break_time_minutes = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relazioni ottimizzate
    collaborator = relationship("Collaborator", back_populates="attendances")
    project = relationship("Project", back_populates="attendances")
    assignment = relationship("Assignment", backref="attendances")

    # Validazioni
    @validates('hours')
    def validate_hours(self, key, hours):
        if hours < 0 or hours > 24:
            raise ValueError("Le ore devono essere tra 0 e 24")
        return hours

    @validates('start_time', 'end_time')
    def validate_times(self, key, time_value):
        if key == 'end_time' and hasattr(self, 'start_time') and self.start_time:
            if time_value <= self.start_time:
                raise ValueError("L'ora di fine deve essere successiva all'ora di inizio")
        return time_value

    __table_args__ = (
        UniqueConstraint(
            "collaborator_id",
            "project_id",
            "date",
            "start_time",
            name="uq_attendance_collaborator_project_date_time",
        ),
        Index("idx_attendance_overlap_guard", "collaborator_id", "start_time", "end_time"),
        Index("ix_attendances_collaborator_project_date", "collaborator_id", "project_id", "date"),
    )

class Assignment(Base):
    __tablename__ = "assignments"

    id = Column(Integer, primary_key=True, index=True)

    # Chiavi esterne con constraint CASCADE
    collaborator_id = Column(Integer, ForeignKey("collaborators.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)

    # Informazioni dell'assegnazione
    role = Column(String(300), nullable=False, index=True)
    modulo_formativo_id = Column(Integer, ForeignKey("moduli_formativi.id", ondelete="SET NULL"), nullable=True, index=True)
    materia = Column(String(200), nullable=True)
    modalita_erogazione = Column(String(30), nullable=True, index=True)
    assigned_hours = Column(Numeric(8, 2), nullable=False)
    start_date = Column(DateTime, nullable=False, index=True)
    end_date = Column(DateTime, nullable=False, index=True)
    contract_signed_date = Column(DateTime, nullable=True, index=True)
    hourly_rate = Column(Numeric(10, 2), nullable=False)
    contract_type = Column(String(50), nullable=True, index=True)  # Tipo contratto: Professionale, Occasionale, Ordine di servizio, Contratto a progetto
    edizione_label = Column(String(100), nullable=True, index=True)

    # Campi per tracking avanzato
    completed_hours = Column(Numeric(8, 2), nullable=False, default=0.0, server_default="0")
    progress_percentage = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relazioni
    collaborator = relationship("Collaborator", back_populates="assignments")
    project = relationship("Project", back_populates="assignments")
    modulo_formativo = relationship("ModuloFormativo", lazy="select")

    # Proprietà calcolate
    @hybrid_property
    def remaining_hours(self):
        # completed_hours può essere NULL su dati storici (D2 A2): senza
        # coalesce la property solleva TypeError (DOM-11).
        return max(0, (self.assigned_hours or 0) - (self.completed_hours or 0))

    @hybrid_property
    def total_cost(self):
        return self.assigned_hours * self.hourly_rate

    # Validazioni
    @validates('hourly_rate')
    def validate_hourly_rate(self, key, rate):
        if rate < 0:
            raise ValueError("La tariffa oraria non può essere negativa")
        return rate

    @validates('assigned_hours')
    def validate_assigned_hours(self, key, hours):
        if hours <= 0:
            raise ValueError("Le ore assegnate devono essere positive")
        return hours

    # Indici composti per performance
    __table_args__ = (
        Index('idx_collaborator_project_role', 'collaborator_id', 'project_id', 'role'),
        Index('idx_date_range', 'start_date', 'end_date'),
        Index('idx_active_assignments', 'is_active', 'start_date'),
        Index('idx_assignment_overlap_guard', 'collaborator_id', 'is_active', 'start_date', 'end_date'),
    )

class ImplementingEntity(Base):
    """
    ENTE ATTUATORE

    Rappresenta un ente che attua progetti (es: piemmei scarl, Next Group srl, Wonder srl).
    Contiene tutti i dati amministrativi, legali, di contatto e pagamento dell'ente.
    """
    __tablename__ = "implementing_entities"

    id = Column(Integer, primary_key=True, index=True)

    # === DATI LEGALI ===
    ragione_sociale = Column(String(200), nullable=False, index=True)
    forma_giuridica = Column(String(50))  # es: "S.r.l.", "S.c.a.r.l.", "S.p.A."
    partita_iva = Column(String(11), unique=True, nullable=False, index=True)
    codice_fiscale = Column(String(16), index=True)
    codice_ateco = Column(String(10))
    rea_numero = Column(String(20))
    registro_imprese = Column(String(100))

    # === SEDE LEGALE ===
    indirizzo = Column(String(200))
    cap = Column(String(5))
    citta = Column(String(100), index=True)
    provincia = Column(String(2))  # Sigla provincia (es: "NA", "MI")
    nazione = Column(String(2), default="IT")  # Codice ISO (es: "IT", "FR")

    # === CONTATTI ===
    pec = Column(String(100), index=True)
    email = Column(String(100))
    telefono = Column(String(20))
    sdi = Column(String(7))  # Codice Univoco SDI per fatturazione elettronica

    # === DATI PAGAMENTO ===
    iban = Column(String(27))  # IBAN italiano è lungo 27 caratteri
    intestatario_conto = Column(String(200))

    # === REFERENTE ===
    referente_nome = Column(String(50))
    referente_cognome = Column(String(50))
    referente_email = Column(String(100))
    referente_telefono = Column(String(20))
    referente_ruolo = Column(String(100))  # es: "Responsabile Amministrativo"

    # === LEGALE RAPPRESENTANTE ===
    legale_rappresentante_nome = Column(String(50))
    legale_rappresentante_cognome = Column(String(50))
    legale_rappresentante_luogo_nascita = Column(String(100))
    legale_rappresentante_data_nascita = Column(DateTime)
    legale_rappresentante_comune_residenza = Column(String(100))
    legale_rappresentante_via_residenza = Column(String(200))
    legale_rappresentante_codice_fiscale = Column(String(16), index=True)

    # === BRANDING ===
    logo_filename = Column(String(255))  # Nome file originale
    logo_path = Column(String(500))      # Path storage
    logo_uploaded_at = Column(DateTime)  # Data upload

    # === ALTRO ===
    note = Column(Text)
    is_active = Column(Boolean, default=True, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relazione con i progetti
    projects = relationship("Project", back_populates="ente_attuatore", lazy="select")

    # === VALIDAZIONI ===

    @validates('partita_iva')
    def validate_partita_iva(self, key, piva):
        """Valida la partita IVA italiana (11 cifre numeriche)"""
        if piva:
            # Rimuovi spazi e prefisso "IT" se presente
            piva_clean = piva.replace(' ', '').replace('IT', '').replace('it', '')

            # Deve essere 11 cifre
            if not piva_clean.isdigit() or len(piva_clean) != 11:
                raise ValueError("Partita IVA deve essere di 11 cifre numeriche")

            return piva_clean
        return piva

    @validates('codice_fiscale')
    def validate_codice_fiscale(self, key, cf):
        """Valida il codice fiscale (16 caratteri alfanumerici o 11 cifre per enti)"""
        if cf:
            cf_clean = cf.replace(' ', '').upper()

            # Può essere 11 cifre (coincide con P.IVA) o 16 alfanumerici
            if not (len(cf_clean) == 11 and cf_clean.isdigit()) and not (len(cf_clean) == 16 and cf_clean.isalnum()):
                raise ValueError("Codice fiscale deve essere 11 cifre o 16 caratteri alfanumerici")

            return cf_clean
        return cf

    @validates('pec', 'email', 'referente_email')
    def validate_email(self, key, email):
        """Valida formato email"""
        if email:
            if not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
                raise ValueError(f"{key} non è un indirizzo email valido")
            return email.lower()
        return email

    @validates('iban')
    def validate_iban(self, key, iban):
        """Valida formato IBAN italiano (27 caratteri)"""
        if iban:
            iban_clean = iban.replace(' ', '').upper()

            # IBAN italiano: IT + 2 cifre controllo + 1 lettera + 10 cifre + 12 caratteri
            if not iban_clean.startswith('IT') or len(iban_clean) != 27:
                raise ValueError("IBAN italiano deve iniziare con IT e avere 27 caratteri")

            return iban_clean
        return iban

    @validates('cap')
    def validate_cap(self, key, cap):
        """Valida CAP italiano (5 cifre)"""
        if cap:
            if not cap.isdigit() or len(cap) != 5:
                raise ValueError("CAP deve essere di 5 cifre")
            return cap
        return cap

    @validates('provincia')
    def validate_provincia(self, key, prov):
        """Valida sigla provincia (2 lettere maiuscole)"""
        if prov:
            prov_clean = prov.upper()
            if len(prov_clean) != 2 or not prov_clean.isalpha():
                raise ValueError("Provincia deve essere la sigla di 2 lettere (es: NA, MI, RM)")
            return prov_clean
        return prov

    # === PROPRIETÀ CALCOLATE ===

    @hybrid_property
    def indirizzo_completo(self):
        """Ritorna l'indirizzo completo formattato"""
        parts = []
        if self.indirizzo:
            parts.append(self.indirizzo)
        if self.cap and self.citta:
            parts.append(f"{self.cap} {self.citta}")
        elif self.citta:
            parts.append(self.citta)
        if self.provincia:
            parts.append(f"({self.provincia})")
        if self.nazione and self.nazione != "IT":
            parts.append(self.nazione)

        return ", ".join(parts) if parts else ""

    @hybrid_property
    def referente_nome_completo(self):
        """Ritorna il nome completo del referente"""
        if self.referente_nome and self.referente_cognome:
            return f"{self.referente_nome} {self.referente_cognome}"
        elif self.referente_nome:
            return self.referente_nome
        elif self.referente_cognome:
            return self.referente_cognome
        return ""

    @hybrid_property
    def legale_rappresentante_nome_completo(self):
        """Ritorna il nome completo del legale rappresentante"""
        if self.legale_rappresentante_nome and self.legale_rappresentante_cognome:
            return f"{self.legale_rappresentante_nome} {self.legale_rappresentante_cognome}"
        elif self.legale_rappresentante_nome:
            return self.legale_rappresentante_nome
        elif self.legale_rappresentante_cognome:
            return self.legale_rappresentante_cognome
        return ""

    # === INDICI ===
    __table_args__ = (
        Index('idx_ragione_sociale_active', 'ragione_sociale', 'is_active'),
        Index('idx_citta_provincia', 'citta', 'provincia'),
    )


class ProgettoMansioneEnte(Base):
    """
    ASSOCIAZIONE PROGETTO - MANSIONE - ENTE ATTUATORE

    Tabella di associazione che collega un progetto a un ente attuatore
    specificando la mansione/ruolo, le ore previste ed effettive.

    Questa tabella definisce le mansioni disponibili per un progetto
    con l'ente attuatore che le gestisce. Gli Assignment effettivi
    dei collaboratori possono poi riferirsi a queste definizioni.

    Esempio:
    - Progetto "Formazione Web Dev" ha mansione "Docente Senior"
      gestita da ente "piemmei scarl" con 100 ore previste
    - I collaboratori vengono poi assegnati tramite Assignment
    """
    __tablename__ = "progetto_mansione_ente"

    id = Column(Integer, primary_key=True, index=True)

    # === CHIAVI ESTERNE ===
    progetto_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    ente_attuatore_id = Column(
        Integer,
        ForeignKey("implementing_entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # === MANSIONE/RUOLO ===
    mansione = Column(String(100), nullable=False, index=True)
    # Es: "Docente Senior", "Tutor", "Coordinatore", "Esperto settore"

    descrizione_mansione = Column(Text)  # Dettagli sulla mansione

    # === PERIODO ===
    data_inizio = Column(DateTime, nullable=False, index=True)
    data_fine = Column(DateTime, nullable=False, index=True)

    # === ORE ===
    ore_previste = Column(Numeric(8, 2), nullable=False)  # Ore totali previste per la mansione
    ore_effettive = Column(Numeric(8, 2), default=0.0)    # Ore effettivamente svolte (calcolate da presenze)

    # === DATI ECONOMICI ===
    tariffa_oraria = Column(Numeric(10, 2))  # Tariffa oraria per questa mansione
    budget_totale = Column(Numeric(12, 2))   # Budget totale (ore_previste * tariffa_oraria)

    # === TIPO CONTRATTO ===
    tipo_contratto = Column(String(50), index=True)
    # Es: "Professionale", "Prestazione occasionale", "Ordine di servizio", "Contratto a progetto"

    # === STATO E NOTE ===
    is_active = Column(Boolean, default=True, index=True)
    note = Column(Text)

    # === AUDIT ===
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # === RELAZIONI ===
    progetto = relationship("Project", backref="mansioni_enti")
    ente_attuatore = relationship("ImplementingEntity", backref="mansioni_progetti")

    # === PROPRIETÀ CALCOLATE ===

    @hybrid_property
    def ore_rimanenti(self):
        """Ritorna le ore ancora da svolgere"""
        return max(0, self.ore_previste - self.ore_effettive)

    @hybrid_property
    def percentuale_completamento(self):
        """Ritorna la percentuale di completamento (0-100)"""
        if self.ore_previste > 0:
            return min(100, (self.ore_effettive / self.ore_previste) * 100)
        return 0

    @hybrid_property
    def costo_effettivo(self):
        """Calcola il costo effettivo basato sulle ore svolte"""
        if self.tariffa_oraria:
            return self.ore_effettive * self.tariffa_oraria
        return 0

    # === VALIDAZIONI ===

    @validates('ore_previste')
    def validate_ore_previste(self, key, ore):
        if ore <= 0:
            raise ValueError("Le ore previste devono essere positive")
        return ore

    @validates('ore_effettive')
    def validate_ore_effettive(self, key, ore):
        if ore < 0:
            raise ValueError("Le ore effettive non possono essere negative")
        return ore

    @validates('tariffa_oraria')
    def validate_tariffa_oraria(self, key, tariffa):
        if tariffa is not None and tariffa < 0:
            raise ValueError("La tariffa oraria non può essere negativa")
        return tariffa

    @validates('data_fine')
    def validate_data_fine(self, key, data_fine):
        if hasattr(self, 'data_inizio') and self.data_inizio:
            if data_fine <= self.data_inizio:
                raise ValueError("La data fine deve essere successiva alla data inizio")
        return data_fine

    # === INDICI COMPOSTI ===
    __table_args__ = (
        # Indice per query su progetto e ente
        Index('idx_progetto_ente', 'progetto_id', 'ente_attuatore_id'),
        # Indice per query su periodo
        Index('idx_periodo_mansione', 'data_inizio', 'data_fine'),
        # Indice per query su mansioni attive
        Index('idx_mansione_attiva', 'mansione', 'is_active'),
        # Constraint di unicità: non possiamo avere la stessa mansione
        # per lo stesso progetto-ente nello stesso periodo
        Index('idx_unique_progetto_ente_mansione',
              'progetto_id', 'ente_attuatore_id', 'mansione', 'data_inizio',
              unique=True),
    )


class PianoFinanziario(Base):
    """Piano finanziario collegato a un progetto."""
    __tablename__ = "piani_finanziari"

    id = Column(Integer, primary_key=True, index=True)
    progetto_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    legacy_template_id = Column(Integer, nullable=True)
    legacy_avviso_id = Column(Integer, nullable=True)
    anno = Column(Integer, nullable=False, index=True)
    ente_erogatore = Column(String(100), nullable=False, default="Formazienda")
    avviso_pf_id = Column(Integer, ForeignKey("avvisi.id", ondelete="SET NULL"), nullable=True, index=True)
    avviso_revisione_id = Column(
        Integer,
        ForeignKey("avviso_revisioni.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
        index=True,
    )

    # === IDENTIFICAZIONE ===
    codice_piano = Column(String(100), unique=True, nullable=True, index=True)
    nome = Column(String(200), nullable=False, default="")
    tipo_fondo = Column(String(30), nullable=True, default="altro", index=True)
    # Valori: "fondimpresa", "fonamcom", "formazienda", "fapi", "fse", "regionale", "altro"
    data_ammissione = Column(Date, nullable=True)
    stato_rendicontazione = Column(String(20), nullable=False, default="bozza", server_default="bozza", index=True)
    codice_progetto_fondo = Column(String(50), nullable=True, index=True)
    importo_ammesso = Column(Numeric(12, 2), nullable=True)

    # === BUDGET ===
    budget_totale = Column(Numeric(12, 2), nullable=False, default=0.0)
    budget_approvato = Column(Numeric(12, 2), nullable=False, default=0.0)
    budget_utilizzato = Column(Numeric(12, 2), default=0.0)
    budget_rimanente = Column(Numeric(12, 2), default=0.0, nullable=False)

    # === DATE ===
    data_inizio = Column(DateTime, nullable=False, default=func.now())
    data_fine = Column(DateTime, nullable=False, default=func.now())
    data_approvazione = Column(DateTime(timezone=True), nullable=True)
    data_rendicontazione = Column(DateTime(timezone=True), nullable=True)

    # === STATO ===
    stato = Column(String(20), default="bozza", index=True)
    # Valori: "bozza", "inviato", "approvato", "in_corso", "completato", "rendicontato", "chiuso", "respinto"

    # === NOTE ===
    note = Column(Text)
    note_ente = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    progetto = relationship("Project", back_populates="piani_finanziari", lazy="joined")
    avviso_rel = relationship("Avviso", foreign_keys=[avviso_pf_id], lazy="select")
    avviso_revisione = relationship("AvvisoRevisione", foreign_keys=[avviso_revisione_id], lazy="select")
    voci = relationship("VocePianoFinanziario", back_populates="piano", lazy="select", cascade="all, delete-orphan")

    @property
    def avviso(self):
        return self.avviso_rel.codice if self.avviso_rel else ""

    @avviso.setter
    def avviso(self, value):
        self._pending_avviso = value

    @validates('tipo_fondo')
    def validate_tipo_fondo(self, key, valore):
        # DOM-10: formazienda e fapi aggiunti — senza di essi i piani restavano
        # 'altro' e il lookup massimali per (tipo_fondo, anno) non matchava mai.
        tipi_validi = ['fondimpresa', 'fonamcom', 'formazienda', 'fapi', 'fse', 'regionale', 'altro']
        if valore not in tipi_validi:
            raise ValueError(f"tipo_fondo deve essere uno di: {tipi_validi}")
        return valore

    @validates('stato')
    def validate_stato(self, key, valore):
        stati_validi = ['bozza', 'inviato', 'approvato', 'in_corso', 'completato', 'rendicontato', 'chiuso', 'respinto']
        if valore not in stati_validi:
            raise ValueError(f"stato deve essere uno di: {stati_validi}")
        return valore

    __table_args__ = (
        UniqueConstraint("progetto_id", "anno", "codice_piano", name="uq_piano_progetto_anno_codice"),
        Index("idx_piano_progetto_stato", "progetto_id", "stato"),
        Index("idx_piano_fondo_stato", "tipo_fondo", "stato"),
        Index("idx_piano_date", "data_inizio", "data_fine"),
    )

    def __repr__(self):
        return f"<PianoFinanziario {self.codice_piano or self.id}>"

    @validates("stato_rendicontazione")
    def validate_stato_rendicontazione(self, key, valore):
        stati_validi = ["bozza", "in_corso", "inviato", "approvato", "respinto"]
        if valore not in stati_validi:
            raise ValueError(f"stato_rendicontazione deve essere uno di: {stati_validi}")
        return valore

    def aggiorna_budget_utilizzato(self, db):
        # La sessione lavora con autoflush=False: le voci modificate in memoria
        # vanno flushate prima della SUM SQL, altrimenti il totale resta
        # indietro dell'ultima modifica (DOM-01).
        db.flush()
        totale = db.query(
            func.coalesce(func.sum(VocePianoFinanziario.importo_consuntivo), 0.0)
        ).filter(
            VocePianoFinanziario.piano_id == self.id
        ).scalar()
        # DOM-11: quantizzazione unica ROUND_HALF_UP a 2 decimali.
        self.budget_utilizzato = quantize_euro(totale)
        self.budget_rimanente = quantize_euro(
            to_decimal(self.budget_totale) - to_decimal(self.budget_utilizzato)
        )
        return self.budget_utilizzato


class ProgettoBeneficiario(Base):
    __tablename__ = "progetto_beneficiario"

    id = Column(Integer, primary_key=True, index=True)
    progetto_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    nome = Column(String(100), nullable=False)
    cognome = Column(String(100), nullable=False)
    cf = Column(String(16), nullable=False, index=True)
    ruolo = Column(String(100), nullable=True)
    data_inizio = Column(Date, nullable=True)
    data_fine = Column(Date, nullable=True)


class MassimaleFondo(Base):
    __tablename__ = "massimali_fondo"

    id = Column(Integer, primary_key=True, index=True)
    tipo_fondo = Column(String(30), nullable=False, index=True)
    anno = Column(Integer, nullable=False, index=True)
    massimale_orario_docenza = Column(Numeric(8, 2), nullable=True)
    massimale_orario_tutoraggio = Column(Numeric(8, 2), nullable=True)
    massimale_spese_generali_pct = Column(Numeric(5, 2), nullable=True)

    __table_args__ = (
        UniqueConstraint("tipo_fondo", "anno", name="uq_massimali_fondo_tipo_anno"),
    )


class VocePianoFinanziario(Base):
    """Singola voce del piano finanziario."""
    __tablename__ = "voci_piano_finanziario"

    id = Column(Integer, primary_key=True, index=True)
    piano_id = Column(Integer, ForeignKey("piani_finanziari.id", ondelete="CASCADE"), nullable=False, index=True)
    collaborator_id = Column(Integer, ForeignKey("collaborators.id", ondelete="SET NULL"), nullable=True, index=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id", ondelete="SET NULL"), nullable=True, index=True)
    modulo_formativo_id = Column(Integer, ForeignKey("moduli_formativi.id", ondelete="SET NULL"), nullable=True, index=True)
    macrovoce = Column(String(1), nullable=False, index=True)
    voce_codice = Column(String(10), nullable=False, index=True)
    categoria = Column(String(100), nullable=True, index=True)
    # Valori: "docenza", "tutoraggio", "coordinamento", "materiali", "aula", "altro"
    sottocategoria = Column(String(100), nullable=True)
    mansione_riferimento = Column(String(100), nullable=True, index=True)
    descrizione = Column(Text)
    progetto_label = Column(String(100), nullable=True)
    edizione_label = Column(String(100), nullable=True)
    ore = Column(Numeric(8, 2), nullable=False, default=0.0)
    ore_previste = Column(Numeric(8, 2), nullable=False, default=0.0)
    ore_effettive = Column(Numeric(8, 2), nullable=False, default=0.0)
    tariffa_oraria = Column(Numeric(10, 2), nullable=False, default=0.0)
    importo_consuntivo = Column(Numeric(12, 2), nullable=False, default=0.0)
    importo_preventivo = Column(Numeric(12, 2), nullable=False, default=0.0)
    importo_approvato = Column(Numeric(12, 2), nullable=False, default=0.0)
    importo_validato = Column(Numeric(12, 2), nullable=False, default=0.0)
    importo_presentato = Column(Numeric(12, 2), nullable=False, default=0.0)
    stato = Column(String(20), nullable=False, default="previsto", index=True)
    note = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by_user = Column(String(100), nullable=True)

    piano = relationship("PianoFinanziario", back_populates="voci", lazy="select")
    collaborator = relationship("Collaborator", foreign_keys=[collaborator_id], lazy="select")
    assignment = relationship("Assignment", backref="voci_piano", lazy="select")
    modulo_formativo = relationship("ModuloFormativo", lazy="select")

    # Alias italiano per compatibilità con l'interfaccia richiesta
    @property
    def collaboratore(self):
        return self.collaborator

    @property
    def importo_previsto(self) -> float:
        return self.importo_preventivo

    @property
    def importo_rendicontato(self) -> float:
        return self.importo_consuntivo

    @property
    def importo_rimanente(self) -> float:
        return self.importo_preventivo - self.importo_consuntivo

    @property
    def percentuale_utilizzo(self) -> float:
        if not self.importo_preventivo:
            return 0.0
        return (self.importo_consuntivo / self.importo_preventivo) * 100

    @validates("macrovoce")
    def validate_macrovoce(self, key, value):
        if value not in {"A", "B", "C", "D"}:
            raise ValueError("Macrovoce deve essere una di: A, B, C, D")
        return value

    @validates("categoria")
    def validate_categoria(self, key, value):
        if value is None:
            return value
        categorie_valide = ["docenza", "tutoraggio", "coordinamento", "progettazione", "materiali", "materiali_didattici", "aula", "viaggi", "attrezzature", "certificazioni", "altro"]
        if value not in categorie_valide:
            raise ValueError(f"categoria deve essere una di: {categorie_valide}")
        return value

    @validates("stato")
    def validate_stato(self, key, value):
        stati_validi = ["previsto", "in_corso", "rendicontato", "validato"]
        if value not in stati_validi:
            raise ValueError(f"stato deve essere uno di: {stati_validi}")
        return value

    @validates("ore", "ore_previste", "ore_effettive", "tariffa_oraria", "importo_consuntivo", "importo_preventivo", "importo_approvato", "importo_validato", "importo_presentato")
    def validate_non_negative(self, key, value):
        if value is None:
            return 0.0
        if value < 0:
            raise ValueError(f"{key} non può essere negativo")
        return value

    __table_args__ = (
        Index("idx_voci_piano_macrovoce", "piano_id", "macrovoce"),
        Index("idx_voci_piano_codice", "piano_id", "voce_codice"),
        Index("idx_voci_piano_categoria", "piano_id", "categoria"),
        Index("idx_voci_piano_assignment", "assignment_id"),
        Index("idx_voci_piano_mansione", "mansione_riferimento"),
        Index("idx_voci_piano_modulo", "modulo_formativo_id"),
    )

    def __repr__(self):
        return f"<VocePianoFinanziario {self.voce_codice} {self.importo_preventivo}>"

    def aggiorna_da_presenze(self, db):
        if not self.assignment_id:
            return

        # Sessione con autoflush=False: presenze aggiunte/modificate/cancellate
        # in questa transazione devono essere visibili alla SUM (DOM-01).
        db.flush()
        ore = db.query(
            func.coalesce(func.sum(Attendance.hours), 0.0)
        ).filter(
            Attendance.assignment_id == self.assignment_id
        ).scalar()

        # DOM-11: aritmetica in Decimal con regola unica ROUND_HALF_UP —
        # mai round() (banker's) sui valori economici.
        ore_eff = quantize_ore(ore)
        self.ore_effettive = ore_eff
        self.ore = ore_eff
        self.importo_consuntivo = quantize_euro(ore_eff * to_decimal(self.tariffa_oraria))
        self.importo_presentato = self.importo_consuntivo
        if self.importo_consuntivo > 0 and self.stato == "previsto":
            self.stato = "in_corso"


class Prodotto(Base):
    """Prodotto / Servizio del catalogo."""
    __tablename__ = "prodotti"

    TIPI_VALIDI = ['apprendistato', 'tirocinio', 'formazione', 'altro']
    UNITA_VALIDE = ['ora', 'giorno', 'mese', 'forfait', 'partecipante']

    id = Column(Integer, primary_key=True, index=True)
    codice = Column(String(50), unique=True, index=True)
    nome = Column(String(200), nullable=False, index=True)
    descrizione = Column(Text)
    tipo = Column(String(30), nullable=False, default='altro', index=True)
    prezzo_base = Column(Numeric(12, 2), nullable=False, default=0.0)
    unita_misura = Column(String(50), default='ora')
    attivo = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    voci = relationship("ListinoVoce", back_populates="prodotto", lazy="select", cascade="all, delete-orphan")

    @validates('tipo')
    def validate_tipo(self, key, val):
        if val not in self.TIPI_VALIDI:
            raise ValueError(f"Tipo deve essere uno di: {self.TIPI_VALIDI}")
        return val

    @validates('prezzo_base')
    def validate_prezzo(self, key, val):
        if val is not None and val < 0:
            raise ValueError("Il prezzo base non può essere negativo")
        return val

    __table_args__ = (
        Index('idx_prodotto_tipo_attivo', 'tipo', 'attivo'),
    )


class Listino(Base):
    """Listino prezzi per tipo cliente."""
    __tablename__ = "listini"

    TIPI_CLIENTE_VALIDI = ['standard', 'apprendistato', 'finanziato', 'gratis']

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(200), nullable=False, index=True)
    descrizione = Column(Text)
    tipo_cliente = Column(String(30), nullable=False, default='standard', index=True)
    attivo = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    voci = relationship("ListinoVoce", back_populates="listino", lazy="select", cascade="all, delete-orphan")

    @validates('tipo_cliente')
    def validate_tipo_cliente(self, key, val):
        if val not in self.TIPI_CLIENTE_VALIDI:
            raise ValueError(f"tipo_cliente deve essere uno di: {self.TIPI_CLIENTE_VALIDI}")
        return val


class ListinoVoce(Base):
    """Voce di listino: associa un prodotto a un listino con prezzo/sconto specifico."""
    __tablename__ = "listino_voci"

    id = Column(Integer, primary_key=True, index=True)
    listino_id = Column(Integer, ForeignKey("listini.id", ondelete="CASCADE"), nullable=False, index=True)
    prodotto_id = Column(Integer, ForeignKey("prodotti.id", ondelete="CASCADE"), nullable=False, index=True)
    prezzo_override = Column(Numeric(12, 2), nullable=True)          # Se null → usa prezzo_base del prodotto
    sconto_percentuale = Column(Numeric(5, 2), default=0.0)
    note = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    listino = relationship("Listino", back_populates="voci", lazy="select")
    prodotto = relationship("Prodotto", back_populates="voci", lazy="select")

    @hybrid_property
    def prezzo_finale(self):
        """prezzo_override ?? prezzo_base × (1 - sconto/100)"""
        if self.prezzo_override is not None:
            return self.prezzo_override
        if self.prodotto and self.prodotto.prezzo_base is not None:
            # DOM-11: colonne Numeric -> Decimal; niente aritmetica mista con float
            sconto = to_decimal(self.sconto_percentuale)
            return quantize_euro(to_decimal(self.prodotto.prezzo_base) * (1 - sconto / 100))
        return 0.0

    @validates('sconto_percentuale')
    def validate_sconto(self, key, val):
        if val is not None and (val < 0 or val > 100):
            raise ValueError("Sconto deve essere tra 0 e 100")
        return val

    @validates('prezzo_override')
    def validate_override(self, key, val):
        if val is not None and val < 0:
            raise ValueError("Il prezzo override non può essere negativo")
        return val

    __table_args__ = (
        Index('idx_voce_listino_prodotto', 'listino_id', 'prodotto_id', unique=True),
    )


class Agenzia(Base):
    """Agenzia di riferimento per i consulenti/agenti commerciali."""
    __tablename__ = "agenzie"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(200), nullable=False, index=True)
    partita_iva = Column(String(11), unique=True, index=True)
    telefono = Column(String(20))
    email = Column(String(100))
    note = Column(Text)
    collaborator_id = Column(Integer, ForeignKey("collaborators.id", ondelete="SET NULL"), nullable=True, unique=True, index=True)
    attivo = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    consulenti = relationship("Consulente", back_populates="agenzia", lazy="select")
    aziende_clienti = relationship("AziendaCliente", back_populates="agenzia", lazy="select")
    source_collaborator = relationship("Collaborator", back_populates="linked_agency", lazy="select")

    @validates('email')
    def validate_email(self, key, email):
        if email and not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
            raise ValueError("Email non valida")
        return email.lower() if email else email

    @validates('partita_iva')
    def validate_partita_iva(self, key, piva):
        if piva:
            piva_clean = piva.replace(' ', '').replace('IT', '').replace('it', '')
            if not piva_clean.isdigit() or len(piva_clean) != 11:
                raise ValueError("Partita IVA deve essere di 11 cifre numeriche")
            return piva_clean
        return piva


class Consulente(Base):
    """Consulente / agente commerciale."""
    __tablename__ = "consulenti"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), nullable=False)
    cognome = Column(String(100), nullable=False, index=True)
    email = Column(String(100), unique=True, index=True)
    telefono = Column(String(20))
    partita_iva = Column(String(11), unique=True, index=True)
    agenzia_id = Column(Integer, ForeignKey("agenzie.id", ondelete="SET NULL"), nullable=True, index=True)
    collaborator_id = Column(Integer, ForeignKey("collaborators.id", ondelete="SET NULL"), nullable=True, unique=True, index=True)
    zona_competenza = Column(String(200))
    provvigione_percentuale = Column(Numeric(5, 2))
    note = Column(Text)
    attivo = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    agenzia = relationship("Agenzia", back_populates="consulenti", lazy="select")
    aziende_clienti = relationship("AziendaCliente", back_populates="consulente", lazy="select")

    @hybrid_property
    def nome_completo(self):
        return f"{self.nome} {self.cognome}"

    @validates('email')
    def validate_email(self, key, email):
        if email and not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
            raise ValueError("Email non valida")
        return email.lower() if email else email

    @validates('partita_iva')
    def validate_partita_iva(self, key, piva):
        if piva:
            piva_clean = piva.replace(' ', '').replace('IT', '').replace('it', '')
            if not piva_clean.isdigit() or len(piva_clean) != 11:
                raise ValueError("Partita IVA deve essere di 11 cifre numeriche")
            return piva_clean
        return piva

    @validates('provvigione_percentuale')
    def validate_provvigione(self, key, val):
        if val is not None and (val < 0 or val > 100):
            raise ValueError("Provvigione deve essere tra 0 e 100")
        return val

    __table_args__ = (
        Index('idx_consulente_cognome_nome', 'cognome', 'nome'),
    )


class AziendaCliente(Base):
    """Azienda cliente."""
    __tablename__ = "aziende_clienti"

    id = Column(Integer, primary_key=True, index=True)
    ragione_sociale = Column(String(200), nullable=False, index=True)
    natura_giuridica = Column(String(50))
    partita_iva = Column(String(11), unique=True, index=True)
    codice_fiscale = Column(String(16), index=True)
    settore_ateco = Column(String(10))
    settore_codice = Column(String(10))
    settore_descrizione = Column(String(255))
    attivita_erogate = Column(Text)
    indirizzo = Column(String(200))
    citta = Column(String(100), index=True)
    cap = Column(String(5))
    provincia = Column(String(2))
    sede_legale_indirizzo = Column(String(255))
    sede_legale_cap = Column(String(5))
    sede_legale_comune = Column(String(100))
    sede_legale_provincia = Column(String(100))
    sede_operativa_indirizzo = Column(String(255))
    sede_operativa_cap = Column(String(5))
    sede_operativa_comune = Column(String(100))
    sede_operativa_provincia = Column(String(100))
    email = Column(String(100))
    pec = Column(String(100))
    telefono = Column(String(20))
    sito_web = Column(String(255))
    linkedin_url = Column(String(255))
    facebook_url = Column(String(255))
    instagram_url = Column(String(255))
    legale_rappresentante_nome = Column(String(100))
    legale_rappresentante_cognome = Column(String(100))
    legale_rappresentante_codice_fiscale = Column(String(16))
    legale_rappresentante_email = Column(String(100))
    legale_rappresentante_telefono = Column(String(30))
    legale_rappresentante_indirizzo = Column(String(255))
    legale_rappresentante_linkedin = Column(String(255))
    legale_rappresentante_facebook = Column(String(255))
    legale_rappresentante_instagram = Column(String(255))
    legale_rappresentante_tiktok = Column(String(255))
    referente_nome = Column(String(100))
    referente_cognome = Column(String(100))
    referente_ruolo = Column(String(100))
    referente_email = Column(String(100))
    referente_telefono = Column(String(30))
    referente_indirizzo = Column(String(255))
    referente_luogo_nascita = Column(String(100))
    referente_data_nascita = Column(DateTime)
    referente_linkedin = Column(String(255))
    referente_facebook = Column(String(255))
    referente_instagram = Column(String(255))
    referente_tiktok = Column(String(255))
    matricola_inps = Column(String(30))
    anno_adesione = Column(String(4))
    regime_aiuto_default = Column(String(30))
    num_dipendenti = Column(Integer)
    ccnl_prevalente = Column(String(255))
    agenzia_id = Column(Integer, ForeignKey("agenzie.id", ondelete="SET NULL"), nullable=True, index=True)
    consulente_id = Column(Integer, ForeignKey("consulenti.id", ondelete="SET NULL"), nullable=True, index=True)
    note = Column(Text)
    attivo = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    agenzia = relationship("Agenzia", back_populates="aziende_clienti", lazy="select")
    consulente = relationship("Consulente", back_populates="aziende_clienti", lazy="select")
    allievi = relationship("Allievo", back_populates="azienda_cliente", lazy="select")
    sedi_operative = relationship(
        "AziendaClienteSedeOperativa",
        back_populates="azienda",
        lazy="select",
        cascade="all, delete-orphan",
        order_by="AziendaClienteSedeOperativa.nome.asc()",
    )
    project_links = relationship(
        "AziendaClienteProjectLink",
        back_populates="azienda",
        lazy="select",
        cascade="all, delete-orphan",
    )
    linked_projects = relationship(
        "Project",
        secondary="azienda_cliente_projects",
        lazy="select",
        viewonly=True,
    )
    fund_memberships = relationship(
        "AziendaClienteFundMembership",
        back_populates="azienda",
        lazy="select",
        cascade="all, delete-orphan",
        order_by="AziendaClienteFundMembership.data_inizio.desc()",
    )

    @validates('partita_iva')
    def validate_partita_iva(self, key, piva):
        if piva:
            piva_clean = piva.replace(' ', '').replace('IT', '').replace('it', '')
            if not piva_clean.isdigit() or len(piva_clean) != 11:
                raise ValueError("Partita IVA deve essere di 11 cifre numeriche")
            return piva_clean
        return piva

    @validates('codice_fiscale')
    def validate_codice_fiscale(self, key, cf):
        if cf:
            cf_clean = cf.replace(' ', '').upper()
            if not ((len(cf_clean) == 11 and cf_clean.isdigit()) or
                    (len(cf_clean) == 16 and cf_clean.isalnum())):
                raise ValueError("Codice fiscale deve essere 11 cifre o 16 caratteri alfanumerici")
            return cf_clean
        return cf

    @validates('email', 'pec', 'referente_email', 'legale_rappresentante_email')
    def validate_email(self, key, email):
        if email and not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
            raise ValueError(f"{key} non è un indirizzo email valido")
        return email.lower() if email else email

    @validates('cap')
    def validate_cap(self, key, cap):
        if cap and (not cap.isdigit() or len(cap) != 5):
            raise ValueError("CAP deve essere di 5 cifre")
        return cap

    @validates('provincia')
    def validate_provincia(self, key, prov):
        if prov:
            prov_clean = prov.upper()
            if len(prov_clean) != 2 or not prov_clean.isalpha():
                raise ValueError("Provincia deve essere la sigla di 2 lettere (es: NA, MI, RM)")
            return prov_clean
        return prov

    __table_args__ = (
        Index('idx_azienda_ragione_citta', 'ragione_sociale', 'citta'),
    )

    @property
    def project_ids(self):
        if self.project_links:
            return [link.project_id for link in self.project_links]
        return []

    @property
    def allievo_ids(self):
        if self.allievi:
            return [allievo.id for allievo in self.allievi]
        return []


class Allievo(Base):
    __tablename__ = "allievi"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), nullable=False, index=True)
    cognome = Column(String(100), nullable=False, index=True)
    codice_fiscale = Column(String(16), unique=True, nullable=True, index=True)
    luogo_nascita = Column(String(100), nullable=True)
    data_nascita = Column(DateTime, nullable=True, index=True)
    telefono = Column(String(30), nullable=True)
    email = Column(String(100), nullable=True, index=True)
    residenza = Column(String(255), nullable=True)
    cap = Column(String(5), nullable=True)
    citta = Column(String(100), nullable=True, index=True)
    provincia = Column(String(2), nullable=True, index=True)
    occupato = Column(Boolean, default=False, nullable=False, index=True)
    azienda_cliente_id = Column(Integer, ForeignKey("aziende_clienti.id", ondelete="SET NULL"), nullable=True, index=True)
    azienda_sede_operativa_id = Column(Integer, ForeignKey("azienda_cliente_sedi_operative.id", ondelete="SET NULL"), nullable=True, index=True)
    data_assunzione = Column(DateTime, nullable=True, index=True)
    tipo_contratto = Column(String(100), nullable=True)
    ccnl = Column(String(100), nullable=True)
    mansione = Column(String(100), nullable=True)
    livello_inquadramento = Column(String(100), nullable=True)
    note = Column(Text, nullable=True)
    attivo = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    azienda_cliente = relationship("AziendaCliente", back_populates="allievi", lazy="select")
    sede_operativa = relationship("AziendaClienteSedeOperativa", back_populates="allievi", lazy="select")
    projects = relationship("Project", secondary=allievo_project, back_populates="allievi_coinvolti", lazy="select")

    @validates('email')
    def validate_email(self, key, address):
        if address and not re.match(r'^[^@]+@[^@]+\.[^@]+$', address):
            raise ValueError("Email non valida")
        return address.lower() if address else address

    @validates('codice_fiscale')
    def validate_codice_fiscale(self, key, cf):
        if cf:
            cf_clean = cf.replace(' ', '').upper()
            if len(cf_clean) != 16:
                raise ValueError("Codice fiscale deve essere di 16 caratteri")
            return cf_clean
        return cf

    @validates('cap')
    def validate_cap(self, key, cap):
        if cap and (not cap.isdigit() or len(cap) != 5):
            raise ValueError("CAP deve essere di 5 cifre")
        return cap

    @validates('provincia')
    def validate_provincia(self, key, prov):
        if prov:
            prov_clean = prov.upper()
            if len(prov_clean) != 2 or not prov_clean.isalpha():
                raise ValueError("Provincia deve essere la sigla di 2 lettere")
            return prov_clean
        return prov

    @property
    def project_ids(self):
        if self.projects:
            return [project.id for project in self.projects]
        return []


class AziendaClienteProjectLink(Base):
    __tablename__ = "azienda_cliente_projects"

    id = Column(Integer, primary_key=True, index=True)
    azienda_cliente_id = Column(Integer, ForeignKey("aziende_clienti.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    regime_aiuto = Column(String(30), nullable=True)
    cofinanziamento_perc = Column(Numeric(5, 2), nullable=True)
    dichiarazione_de_minimis = Column(String(500), nullable=True)
    plafond_dichiarato = Column(Numeric(12, 2), nullable=True)
    stato = Column(String(30), nullable=True, default='in_attesa')
    note = Column(Text, nullable=True)

    azienda = relationship("AziendaCliente", back_populates="project_links", lazy="select")
    project = relationship("Project", back_populates="azienda_links", lazy="select")

    __table_args__ = (
        UniqueConstraint("azienda_cliente_id", "project_id", name="uq_azienda_cliente_project"),
        Index("idx_azienda_cliente_projects_regime", "regime_aiuto"),
    )


class AziendaClienteSedeOperativa(Base):
    __tablename__ = "azienda_cliente_sedi_operative"

    id = Column(Integer, primary_key=True, index=True)
    azienda_cliente_id = Column(Integer, ForeignKey("aziende_clienti.id", ondelete="CASCADE"), nullable=False, index=True)
    nome = Column(String(150), nullable=False)
    indirizzo = Column(String(255), nullable=True)
    citta = Column(String(100), nullable=True, index=True)
    cap = Column(String(5), nullable=True)
    provincia = Column(String(2), nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    azienda = relationship("AziendaCliente", back_populates="sedi_operative", lazy="select")
    allievi = relationship("Allievo", back_populates="sede_operativa", lazy="select")

    @validates("nome")
    def validate_nome(self, key, value):
        normalized = (value or "").strip()
        if not normalized:
            raise ValueError("Il nome della sede operativa è obbligatorio")
        return normalized

    @validates("cap")
    def validate_cap(self, key, cap):
        if cap and (not cap.isdigit() or len(cap) != 5):
            raise ValueError("CAP deve essere di 5 cifre")
        return cap

    @validates("provincia")
    def validate_provincia(self, key, prov):
        if prov:
            prov_clean = prov.upper()
            if len(prov_clean) != 2 or not prov_clean.isalpha():
                raise ValueError("Provincia deve essere la sigla di 2 lettere")
            return prov_clean
        return prov

    __table_args__ = (
        UniqueConstraint("azienda_cliente_id", "nome", name="uq_azienda_sede_operativa_nome"),
        Index("idx_azienda_sede_operativa_citta", "azienda_cliente_id", "citta"),
    )


class AziendaClienteFundMembership(Base):
    __tablename__ = "azienda_cliente_fund_memberships"

    id = Column(Integer, primary_key=True, index=True)
    azienda_cliente_id = Column(Integer, ForeignKey("aziende_clienti.id", ondelete="CASCADE"), nullable=False, index=True)
    fondo = Column(String(100), nullable=False, index=True)
    data_inizio = Column(DateTime, nullable=False, index=True)
    data_fine = Column(DateTime, nullable=True, index=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    azienda = relationship("AziendaCliente", back_populates="fund_memberships", lazy="select")

    @validates("fondo")
    def validate_fondo(self, key, value):
        normalized = (value or "").strip()
        if not normalized:
            raise ValueError("Il fondo interprofessionale è obbligatorio")
        return normalized

    @hybrid_property
    def is_current(self):
        return self.data_fine is None

    __table_args__ = (
        Index("idx_azienda_fund_period", "azienda_cliente_id", "data_inizio", "data_fine"),
    )


# ─────────────────────────────────────────────
# BLOCCO 4 — Preventivi + Ordini
# ─────────────────────────────────────────────

class Preventivo(Base):
    """Preventivo commerciale verso un'azienda cliente."""
    __tablename__ = "preventivi"

    STATI_VALIDI = ['bozza', 'inviato', 'accettato', 'rifiutato']

    id = Column(Integer, primary_key=True, index=True)
    numero = Column(String(20), nullable=False, unique=True, index=True)
    anno = Column(Integer, nullable=False, index=True)
    numero_progressivo = Column(Integer, nullable=False)
    azienda_cliente_id = Column(Integer, ForeignKey("aziende_clienti.id", ondelete="RESTRICT"), nullable=True, index=True)
    listino_id = Column(Integer, ForeignKey("listini.id", ondelete="SET NULL"), nullable=True, index=True)
    consulente_id = Column(Integer, ForeignKey("consulenti.id", ondelete="SET NULL"), nullable=True, index=True)
    stato = Column(String(20), nullable=False, default='bozza', index=True)
    data_scadenza = Column(DateTime(timezone=False), nullable=True)
    oggetto = Column(String(300))
    note = Column(Text)
    attivo = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    azienda_cliente = relationship("AziendaCliente", lazy="select")
    listino = relationship("Listino", lazy="select")
    consulente = relationship("Consulente", lazy="select")
    righe = relationship("PreventivoRiga", back_populates="preventivo", lazy="select",
                         cascade="all, delete-orphan", order_by="PreventivoRiga.ordine")
    ordine = relationship("Ordine", back_populates="preventivo", lazy="select", uselist=False)

    @hybrid_property
    def totale(self):
        return round(sum(r.importo for r in self.righe), 2) if self.righe else 0.0

    @validates('stato')
    def validate_stato(self, key, val):
        if val not in self.STATI_VALIDI:
            raise ValueError(f"stato deve essere uno di: {self.STATI_VALIDI}")
        return val

    __table_args__ = (
        Index('idx_preventivo_anno_prog', 'anno', 'numero_progressivo', unique=True),
    )


class PreventivoRiga(Base):
    """Riga di un preventivo (snapshot di prodotto + quantità + prezzo)."""
    __tablename__ = "preventivo_righe"

    id = Column(Integer, primary_key=True, index=True)
    preventivo_id = Column(Integer, ForeignKey("preventivi.id", ondelete="CASCADE"), nullable=False, index=True)
    prodotto_id = Column(Integer, ForeignKey("prodotti.id", ondelete="RESTRICT"), nullable=True, index=True)
    descrizione_custom = Column(String(400))
    quantita = Column(Numeric(10, 2), nullable=False, default=1.0)
    prezzo_unitario = Column(Numeric(12, 2), nullable=False, default=0.0)   # snapshot al momento della creazione
    sconto_percentuale = Column(Numeric(5, 2), nullable=False, default=0.0)
    importo = Column(Numeric(12, 2), nullable=False, default=0.0)           # calcolato: qty * prezzo * (1 - sconto/100)
    ordine = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    preventivo = relationship("Preventivo", back_populates="righe", lazy="select")
    prodotto = relationship("Prodotto", lazy="select")

    @validates('quantita')
    def validate_quantita(self, key, val):
        if val is not None and val <= 0:
            raise ValueError("La quantità deve essere > 0")
        return val

    @validates('sconto_percentuale')
    def validate_sconto(self, key, val):
        if val is not None and (val < 0 or val > 100):
            raise ValueError("Sconto deve essere tra 0 e 100")
        return val


class Ordine(Base):
    """Ordine generato da un preventivo accettato."""
    __tablename__ = "ordini"

    STATI_VALIDI = ['in_lavorazione', 'completato', 'annullato']

    id = Column(Integer, primary_key=True, index=True)
    numero = Column(String(20), nullable=False, unique=True, index=True)
    anno = Column(Integer, nullable=False, index=True)
    numero_progressivo = Column(Integer, nullable=False)
    preventivo_id = Column(Integer, ForeignKey("preventivi.id", ondelete="SET NULL"), nullable=True, index=True)
    azienda_cliente_id = Column(Integer, ForeignKey("aziende_clienti.id", ondelete="RESTRICT"), nullable=True, index=True)
    stato = Column(String(30), nullable=False, default='in_lavorazione', index=True)
    note = Column(Text)
    progetto_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    preventivo = relationship("Preventivo", back_populates="ordine", lazy="select")
    azienda_cliente = relationship("AziendaCliente", lazy="select")
    progetto = relationship("Project", lazy="select")

    @validates('stato')
    def validate_stato(self, key, val):
        if val not in self.STATI_VALIDI:
            raise ValueError(f"stato deve essere uno di: {self.STATI_VALIDI}")
        return val

    __table_args__ = (
        Index('idx_ordine_anno_prog', 'anno', 'numero_progressivo', unique=True),
    )


class DocumentCounter(Base):
    """Contatore persistente per numerazioni documentali concorrenti."""
    __tablename__ = "document_counters"

    id = Column(Integer, primary_key=True, index=True)
    document_type = Column(String(20), nullable=False)
    anno = Column(Integer, nullable=False, index=True)
    last_number = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("document_type", "anno", name="uq_document_counter_type_anno"),
        Index("idx_document_counter_type_anno", "document_type", "anno", unique=True),
    )


class ContractTemplate(Base):
    """
    TEMPLATE DI CONTRATTI

    Tabella per gestire i template personalizzabili dei contratti.
    Ogni template può essere associato a un tipo di contratto specifico
    (Professionale, Occasionale, Ordine di servizio, Contratto a progetto)
    e può includere il logo dell'ente attuatore.

    I template supportano variabili dinamiche per l'inserimento automatico
    dei dati del collaboratore, progetto, ente attuatore e mansione.

    Variabili disponibili:
    - {{collaboratore_nome}}, {{collaboratore_cognome}}, {{collaboratore_nome_completo}}
    - {{collaboratore_codice_fiscale}}, {{collaboratore_luogo_nascita}}, {{collaboratore_data_nascita}}
    - {{collaboratore_indirizzo}}, {{collaboratore_citta}}, {{collaboratore_titolo_studio}}
    - {{progetto_nome}}, {{progetto_descrizione}}, {{progetto_cup}}, {{progetto_atto_approvazione}}
    - {{progetto_sede_aziendale_comune}}, {{progetto_sede_aziendale_via}}, {{progetto_sede_aziendale_numero_civico}}
    - {{ente_ragione_sociale}}, {{ente_piva}}, {{ente_indirizzo_completo}}
    - {{ente_sede_comune}}, {{ente_sede_via}}, {{ente_sede_numero_civico}}
    - {{ente_pec}}, {{ente_telefono}}
    - {{ente_legale_rappresentante_nome}}, {{ente_legale_rappresentante_cognome}}, {{ente_legale_rappresentante_nome_completo}}
    - {{ente_legale_rappresentante_luogo_nascita}}, {{ente_legale_rappresentante_data_nascita}}
    - {{ente_legale_rappresentante_comune_residenza}}, {{ente_legale_rappresentante_via_residenza}}
    - {{ente_legale_rappresentante_codice_fiscale}}
    - {{mansione}}, {{ore_previste}}, {{tariffa_oraria}}, {{compenso_totale}}
    - {{data_inizio}}, {{data_fine}}
    - {{data_oggi}}, {{data_firma_contratto}}, {{contract_signed_date}}
    """
    __tablename__ = "contract_templates"

    id = Column(Integer, primary_key=True, index=True)

    # === IDENTIFICAZIONE TEMPLATE ===
    nome_template = Column(String(200), nullable=False, index=True)
    # Es: "Contratto Professionale Standard", "Ordine di Servizio Docenza"

    descrizione = Column(Text)
    # Descrizione del template e del suo utilizzo

    # === CONTESTO DOCUMENTALE ===
    ambito_template = Column(String(50), nullable=False, default="contratto", index=True)
    # Valori: "contratto", "preventivo", "ordine", "generico"

    chiave_documento = Column(String(100), nullable=True, index=True)
    # Es: "contratto_professionale", "preventivo_standard", "ordine_acquisto"

    ente_attuatore_id = Column(Integer, ForeignKey("implementing_entities.id", ondelete="SET NULL"), nullable=True, index=True)
    progetto_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    ente_erogatore = Column(String(100), nullable=True, index=True)
    avviso = Column(String(100), nullable=True, index=True)
    # Se valorizzati, il template è pensato per uno specifico ente/progetto.

    # === TIPO CONTRATTO ===
    tipo_contratto = Column(String(50), nullable=False, index=True)
    # Valori: "professionale", "occasionale", "ordine_servizio", "contratto_progetto"

    # === CONTENUTO TEMPLATE ===
    contenuto_html = Column(Text, nullable=False)
    # Contenuto HTML del contratto con variabili dinamiche
    # Esempio: "<p>Tra {{ente_ragione_sociale}} e {{collaboratore_nome_completo}}...</p>"

    intestazione = Column(Text)
    # Testo dell'intestazione (opzionale)

    pie_pagina = Column(Text)
    # Testo del piè di pagina (opzionale)

    # === CONFIGURAZIONE LAYOUT ===
    include_logo_ente = Column(Boolean, default=True)
    # Se True, include automaticamente il logo dell'ente attuatore

    posizione_logo = Column(String(20), default="header")
    # Valori: "header" (intestazione), "footer" (piè di pagina), "none" (nessuno)

    dimensione_logo = Column(String(20), default="medium")
    # Valori: "small", "medium", "large"

    # === CLAUSOLE STANDARD ===
    include_clausola_privacy = Column(Boolean, default=True)
    include_clausola_riservatezza = Column(Boolean, default=False)
    include_clausola_proprieta_intellettuale = Column(Boolean, default=False)

    # === FORMATO OUTPUT ===
    formato_data = Column(String(20), default="%d/%m/%Y")
    # Formato per le date (es: "%d/%m/%Y" -> 25/12/2024)

    formato_importo = Column(String(20), default="€ {:.2f}")
    # Formato per gli importi (es: "€ {:.2f}" -> € 1.234,56)

    # === STATO E METADATI ===
    is_default = Column(Boolean, default=False, index=True)
    # Se True, questo è il template di default per il tipo_contratto

    is_active = Column(Boolean, default=True, index=True)
    # Se False, il template è archiviato e non utilizzabile

    versione = Column(String(20), default="1.0")
    # Versione del template

    note_interne = Column(Text)
    # Note per uso interno (non appaiono sul contratto)

    # === STATISTICHE UTILIZZO ===
    numero_utilizzi = Column(Integer, default=0)
    # Contatore di quante volte è stato usato questo template

    ultimo_utilizzo = Column(DateTime)
    # Data dell'ultimo utilizzo

    # === AUDIT ===
    created_by = Column(String(100))
    # Username dell'utente che ha creato il template

    updated_by = Column(String(100))
    # Username dell'ultimo utente che ha modificato il template

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    ente_attuatore = relationship("ImplementingEntity", lazy="joined")
    progetto = relationship("Project", foreign_keys=[progetto_id], lazy="joined")
    avvisi = relationship("Avviso", back_populates="template", lazy="select")

    # === VALIDAZIONI ===

    @validates('ambito_template')
    def validate_ambito_template(self, key, ambito):
        """Valida il perimetro documentale del template"""
        ambiti_validi = ['contratto', 'preventivo', 'ordine', 'generico', 'timesheet', 'piano_finanziario']
        if ambito not in ambiti_validi:
            raise ValueError(f"Ambito template deve essere uno di: {ambiti_validi}")
        return ambito

    @validates('tipo_contratto')
    def validate_tipo_contratto(self, key, tipo):
        """Valida il tipo di contratto"""
        tipi_validi = ['professionale', 'occasionale', 'ordine_servizio', 'contratto_progetto', 'documento_generico']
        if tipo not in tipi_validi:
            raise ValueError(f"Tipo contratto deve essere uno di: {tipi_validi}")
        return tipo

    @validates('posizione_logo')
    def validate_posizione_logo(self, key, posizione):
        """Valida la posizione del logo"""
        posizioni_valide = ['header', 'footer', 'none']
        if posizione and posizione not in posizioni_valide:
            raise ValueError(f"Posizione logo deve essere una di: {posizioni_valide}")
        return posizione

    @validates('dimensione_logo')
    def validate_dimensione_logo(self, key, dimensione):
        """Valida la dimensione del logo"""
        dimensioni_valide = ['small', 'medium', 'large']
        if dimensione and dimensione not in dimensioni_valide:
            raise ValueError(f"Dimensione logo deve essere una di: {dimensioni_valide}")
        return dimensione

    # === METODI UTILITY ===

    def increment_usage(self):
        """Incrementa il contatore utilizzi"""
        from datetime import datetime
        self.numero_utilizzi += 1
        self.ultimo_utilizzo = datetime.now()

    def get_available_variables(self) -> dict:
        """Restituisce le variabili disponibili per questo template"""
        return {
            'collaboratore': [
                '{{collaboratore_nome}}',
                '{{collaboratore_cognome}}',
                '{{collaboratore_nome_completo}}',
                '{{collaboratore_codice_fiscale}}',
                '{{collaboratore_luogo_nascita}}',
                '{{collaboratore_data_nascita}}',
                '{{collaboratore_indirizzo}}',
                '{{collaboratore_citta}}',
                '{{collaboratore_titolo_studio}}'
            ],
            'progetto': [
                '{{progetto_nome}}',
                '{{progetto_descrizione}}',
                '{{progetto_cup}}',
                '{{progetto_atto_approvazione}}',
                '{{progetto_sede_aziendale_comune}}',
                '{{progetto_sede_aziendale_via}}',
                '{{progetto_sede_aziendale_numero_civico}}',
                '{{progetto_sede_aziendale_completa}}'
            ],
            'ente': [
                '{{ente_ragione_sociale}}',
                '{{ente_piva}}',
                '{{ente_indirizzo_completo}}',
                '{{ente_sede_comune}}',
                '{{ente_sede_via}}',
                '{{ente_sede_numero_civico}}',
                '{{ente_pec}}',
                '{{ente_telefono}}',
                '{{ente_legale_rappresentante_nome}}',
                '{{ente_legale_rappresentante_cognome}}',
                '{{ente_legale_rappresentante_nome_completo}}',
                '{{ente_legale_rappresentante_luogo_nascita}}',
                '{{ente_legale_rappresentante_data_nascita}}',
                '{{ente_legale_rappresentante_comune_residenza}}',
                '{{ente_legale_rappresentante_via_residenza}}',
                '{{ente_legale_rappresentante_codice_fiscale}}'
            ],
            'contratto': [
                '{{mansione}}',
                '{{ore_previste}}',
                '{{tariffa_oraria}}',
                '{{compenso_totale}}',
                '{{data_inizio}}',
                '{{data_fine}}'
            ],
            'sistema': [
                '{{data_oggi}}',
                '{{data_firma_contratto}}',
                '{{data_sottoscrizione_contratto}}',
                '{{contract_signed_date}}'
            ]
        }

    # === INDICI ===
    __table_args__ = (
        # Indice per ricerca per tipo e stato
        Index('idx_tipo_contratto_attivo', 'tipo_contratto', 'is_active'),
        # Indice per trovare template di default
        Index('idx_tipo_default', 'tipo_contratto', 'is_default'),
        # Constraint unicità: solo un template di default per tipo
        Index('idx_unique_default_per_tipo', 'tipo_contratto', 'is_default', unique=True,
              sqlite_where=Column('is_default') == True,
              postgresql_where=text('is_default = true')),
    )


class AuditLog(Base):
    """
    Audit log immutabile per variazioni di dominio.

    NOTE:
    - append-only: update/delete bloccati da event listener SQLAlchemy.
    - old_value/new_value memorizzati come JSON serializzato in stringa.
    """
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    entity = Column(String(100), nullable=False, index=True)
    action = Column(String(50), nullable=False, index=True)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    user_id = Column(Integer, nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


@event.listens_for(AuditLog, "before_update")
def _prevent_audit_log_update(mapper, connection, target):
    raise ValueError("AuditLog is immutable and cannot be updated")


@event.listens_for(AuditLog, "before_delete")
def _prevent_audit_log_delete(mapper, connection, target):
    raise ValueError("AuditLog is immutable and cannot be deleted")


class GiustificativoSpesa(Base):
    __tablename__ = "giustificativo_spesa"

    id = Column(Integer, primary_key=True, index=True)
    voce_piano_id = Column(Integer, ForeignKey("voci_piano_finanziario.id", ondelete="CASCADE"), nullable=False, index=True)
    tipo = Column(String(50), nullable=False, index=True)
    importo = Column(Numeric(12, 2), nullable=False)
    numero_doc = Column(String(100), nullable=True)
    data_doc = Column(Date, nullable=True)
    fornitore = Column(String(200), nullable=True)
    file_path = Column(String(500), nullable=True)
    validato = Column(Boolean, nullable=False, default=False, server_default=text("false"), index=True)
    note = Column(Text, nullable=True)

    voce_piano = relationship("VocePianoFinanziario", backref="giustificativi_spesa")


class AgentRun(Base):
    """Traccia una singola esecuzione di un agente AI."""
    __tablename__ = "agent_runs"

    id = Column(Integer, primary_key=True, index=True)
    # Workflow system fields
    entity_type = Column(String(50), nullable=True, index=True)
    entity_id = Column(Integer, nullable=True, index=True)
    requested_by_user_id = Column(Integer, nullable=True, index=True)
    input_payload = Column(Text, nullable=True)
    result_summary = Column(Text, nullable=True)
    suggestions_count = Column(Integer, nullable=False, default=0)
    # Registry system fields
    agent_type = Column(String(100), nullable=False, index=True)
    agent_version = Column(String(20), nullable=False, default="1.0")
    status = Column(String(20), nullable=False, default="running", index=True)
    started_at = Column(DateTime(timezone=True), nullable=False, default=func.now(), index=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    triggered_by = Column(String(50), nullable=True)
    trigger_details = Column(Text, nullable=True)
    items_processed = Column(Integer, nullable=False, default=0)
    items_with_issues = Column(Integer, nullable=False, default=0)
    suggestions_created = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=True)
    execution_time_ms = Column(Integer, nullable=True)
    metadata_json = Column("agent_metadata", Text, nullable=True)
    idempotency_key = Column(String(64), nullable=True, unique=True, index=True)

    suggestions = relationship(
        "AgentSuggestion",
        back_populates="run",
        lazy="select",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_agent_type_status", "agent_type", "status"),
        Index("idx_started_at", "started_at"),
    )

    @property
    def agent_name(self) -> str:
        return self.agent_type

    @agent_name.setter
    def agent_name(self, value: str) -> None:
        self.agent_type = value


class AgentSuggestion(Base):
    """Suggerimento generato da un agente AI."""
    __tablename__ = "agent_suggestions"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    # Workflow system fields
    severity = Column(String(20), nullable=True, index=True)
    payload = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by_user_id = Column(Integer, nullable=True, index=True)
    # Shared fields
    suggestion_type = Column(String(50), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="pending", index=True)
    entity_type = Column(String(50), nullable=False, index=True)
    entity_id = Column(Integer, nullable=True, index=True)
    title = Column(String(300), nullable=False)
    description = Column(Text, nullable=True)
    # Registry system fields (legacy)
    priority = Column(String(20), nullable=False, default="medium", index=True)
    suggested_action = Column(Text, nullable=True)
    auto_fix_available = Column(Boolean, nullable=False, default=False)
    auto_fix_payload = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=True)
    expires_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now(), index=True)

    run = relationship("AgentRun", back_populates="suggestions", lazy="select")
    review_actions = relationship(
        "AgentReviewAction",
        back_populates="suggestion",
        lazy="select",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_status_priority", "status", "priority"),
        Index("idx_entity", "entity_type", "entity_id"),
    )

    @property
    def agent_name(self) -> Optional[str]:
        if self.run is not None:
            return self.run.agent_type
        return None

    @property
    def confidence(self) -> Optional[float]:
        return self.confidence_score

    @confidence.setter
    def confidence(self, value: Optional[float]) -> None:
        self.confidence_score = value


class AgentReviewAction(Base):
    """Storico decisioni umane sui suggerimenti agentici."""
    __tablename__ = "agent_review_actions"

    id = Column(Integer, primary_key=True, index=True)
    suggestion_id = Column(Integer, ForeignKey("agent_suggestions.id", ondelete="CASCADE"), nullable=False, index=True)
    action = Column(String(50), nullable=False, index=True)
    reviewed_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    reviewed_at = Column(DateTime, nullable=False, default=func.now(), index=True)
    notes = Column(Text, nullable=True)
    auto_fix_applied = Column(Boolean, nullable=False, default=False)
    result_success = Column(Boolean, nullable=True)
    result_message = Column(Text, nullable=True)

    suggestion = relationship("AgentSuggestion", back_populates="review_actions", lazy="select")

    @property
    def created_at(self):
        return self.reviewed_at


class AgentCommunicationDraft(Base):
    """Bozza comunicazione generata da agente, da revisionare prima dell'invio."""
    __tablename__ = "agent_communication_drafts"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    suggestion_id = Column(Integer, ForeignKey("agent_suggestions.id", ondelete="SET NULL"), nullable=True, index=True)
    agent_name = Column(String(100), nullable=False, index=True)
    channel = Column(String(20), nullable=False, default="email", index=True)
    recipient_type = Column(String(50), nullable=False, index=True)
    recipient_id = Column(Integer, nullable=True, index=True)
    recipient_email = Column(String(150), nullable=False, index=True)
    recipient_name = Column(String(200), nullable=True)
    subject = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="draft", index=True)
    meta_payload = Column(Text, nullable=True)
    created_by_user_id = Column(Integer, nullable=True, index=True)
    reviewed_by_user_id = Column(Integer, nullable=True, index=True)
    sent_at = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    run = relationship("AgentRun", lazy="select")
    suggestion = relationship("AgentSuggestion", lazy="select")


class EmailInboxItem(Base):
    __tablename__ = "email_inbox_items"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(String(500), unique=True, nullable=False, index=True)
    received_at = Column(DateTime(timezone=True), nullable=False)
    sender_email = Column(String(255), nullable=False, index=True)
    subject = Column(String(500), nullable=True)
    entity_type = Column(String(50), nullable=True)
    entity_id = Column(Integer, nullable=True)
    attachment_path = Column(String(1000), nullable=True)
    attachment_name = Column(String(255), nullable=True)
    processing_status = Column(String(50), nullable=False)
    llm_result = Column(Text, nullable=True)
    reply_sent = Column(Boolean, server_default=text("false"), nullable=False)
    reply_sent_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    archived = Column(Boolean, server_default=text("false"), nullable=False, index=True)
    archived_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    __table_args__ = (
        Index("ix_email_inbox_items_status", "processing_status"),
        Index("ix_email_inbox_items_entity", "entity_type", "entity_id"),
    )


class TimesheetGenerato(Base):
    """Timesheet PDF generato per un assignment. Bloccato dopo generazione."""
    __tablename__ = "timesheet_generati"

    id = Column(Integer, primary_key=True, index=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False, index=True)
    pdf_path = Column(String(500), nullable=False)
    pdf_filename = Column(String(255), nullable=False)
    generato_il = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    generato_da = Column(String(100), nullable=True)
    generato_da_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    bloccato = Column(Boolean, nullable=False, default=True)
    sbloccato_da = Column(String(100), nullable=True)
    sbloccato_da_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    sbloccato_il = Column(DateTime(timezone=True), nullable=True)
    sblocco_motivo = Column(Text, nullable=True)
    totale_ore = Column(Numeric(8, 2), nullable=False, default=0, server_default="0")
    presenze_count = Column(Integer, nullable=False, default=0, server_default="0")
    note = Column(Text, nullable=True)

    assignment = relationship("Assignment", backref="timesheet_generati", lazy="select")
    righe = relationship("TimesheetRiga", back_populates="timesheet", cascade="all, delete-orphan", lazy="select")


class TimesheetRiga(Base):
    """Snapshot immutabile di una presenza inclusa in un timesheet."""
    __tablename__ = "timesheet_righe"

    id = Column(Integer, primary_key=True, index=True)
    timesheet_id = Column(Integer, ForeignKey("timesheet_generati.id", ondelete="CASCADE"), nullable=False, index=True)
    attendance_id = Column(Integer, ForeignKey("attendances.id", ondelete="SET NULL"), nullable=True, index=True)
    date = Column("data", DateTime, nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    hours = Column(Numeric(6, 2), nullable=False)
    notes = Column(Text, nullable=True)

    timesheet = relationship("TimesheetGenerato", back_populates="righe")


class DatiRetributivi(Base):
    """Dati retributivi di un allievo per un progetto specifico."""
    __tablename__ = "dati_retributivi"

    id = Column(Integer, primary_key=True, index=True)
    allievo_id = Column(Integer, ForeignKey("allievi.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    ral_annua = Column(Numeric(12, 2), nullable=True)
    costo_orario = Column(Numeric(10, 2), nullable=True)
    ore_1720 = Column(Numeric(8, 2), nullable=True, default=1720)
    busta_paga_path = Column(String(500), nullable=True)
    busta_paga_filename = Column(String(255), nullable=True)
    periodo_riferimento = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True)

    allievo = relationship("Allievo", backref="dati_retributivi", lazy="select")
    project = relationship("Project", backref="dati_retributivi", lazy="select")

    __table_args__ = (
        UniqueConstraint("allievo_id", "project_id", name="uq_dati_retributivi_allievo_project"),
    )


class ModuloFormativo(Base):
    """Modulo formativo estratto dal formulario FAPI di un progetto."""
    __tablename__ = "moduli_formativi"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    azienda_beneficiaria_id = Column(Integer, ForeignKey("aziende_clienti.id", ondelete="SET NULL"), nullable=True, index=True)
    codice_progetto_fapi = Column(String(30), nullable=True, index=True)
    titolo_modulo = Column(String(300), nullable=False)
    materia = Column(String(200), nullable=True)
    modalita_erogazione = Column(String(30), nullable=True, index=True)
    # aula | fad_sincrona | fad_asincrona | training_on_job | propedeutica
    tipo_attivita = Column(String(20), nullable=False, default="formativa", index=True)
    # formativa | propedeutica
    ore_previste = Column(Numeric(8, 2), nullable=True)
    obiettivo = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    project = relationship("Project", backref="moduli_formativi", lazy="select")
    azienda_beneficiaria = relationship("AziendaCliente", backref="moduli_formativi", lazy="select")

    __table_args__ = (
        Index("idx_modulo_project_codice", "project_id", "codice_progetto_fapi"),
    )


class Playbook(Base):
    __tablename__ = "playbooks"

    id = Column(Integer, primary_key=True)
    nome = Column(String(200), nullable=False)
    fondo = Column(String(20), nullable=False, default="altro", server_default="altro")
    ente_erogatore = Column(String(100), nullable=True, index=True)
    descrizione = Column(Text, nullable=True)
    versione_corrente_id = Column(
        Integer, ForeignKey("playbook_versioni.id", ondelete="SET NULL", use_alter=True), nullable=True
    )
    is_active = Column(Boolean, nullable=False, default=True, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    versione_corrente = relationship(
        "PlaybookVersione", foreign_keys=[versione_corrente_id], post_update=True, lazy="select"
    )
    versioni = relationship(
        "PlaybookVersione", foreign_keys="PlaybookVersione.playbook_id", back_populates="playbook",
        cascade="all, delete-orphan", lazy="select"
    )

    __table_args__ = (
        UniqueConstraint("fondo", "ente_erogatore", "nome", name="uq_playbooks_identita"),
        CheckConstraint("fondo IN ('fondimpresa','formazienda','fapi','regionale','altro')", name="ck_playbooks_fondo"),
    )


class PlaybookVersione(Base):
    __tablename__ = "playbook_versioni"

    id = Column(Integer, primary_key=True)
    playbook_id = Column(Integer, ForeignKey("playbooks.id", ondelete="RESTRICT"), nullable=False, index=True)
    numero_versione = Column(Integer, nullable=False)
    versione_precedente_id = Column(Integer, ForeignKey("playbook_versioni.id", ondelete="SET NULL"), nullable=True)
    note = Column(Text, nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    playbook = relationship("Playbook", foreign_keys=[playbook_id], back_populates="versioni")
    precedente = relationship("PlaybookVersione", remote_side=[id], lazy="select")
    voci = relationship("PlaybookVoce", back_populates="versione", cascade="all, delete-orphan", lazy="select")

    __table_args__ = (
        UniqueConstraint("playbook_id", "numero_versione", name="uq_playbook_versioni_numero"),
        CheckConstraint("numero_versione > 0", name="ck_playbook_versioni_numero_positivo"),
    )


class PlaybookVoce(Base):
    __tablename__ = "playbook_voci"

    id = Column(Integer, primary_key=True)
    playbook_versione_id = Column(Integer, ForeignKey("playbook_versioni.id", ondelete="RESTRICT"), nullable=False)
    fase = Column(String(20), nullable=False)
    ordine = Column(Integer, nullable=False, default=0, server_default="0")
    titolo = Column(String(300), nullable=False)
    descrizione = Column(Text, nullable=True)
    contenuto = Column(AVVISO_JSON_TYPE, nullable=False)
    schema_version = Column(Integer, nullable=False, default=1, server_default="1")
    applicabilita = Column(AVVISO_JSON_TYPE, nullable=True)
    origine = Column(String(20), nullable=False, default="manuale", server_default="manuale")
    testo_originale = Column(Text, nullable=True)
    riferimento_articolo = Column(String(100), nullable=True)
    stato = Column(String(20), nullable=False, default="proposta", server_default="proposta")
    confidence = Column(Numeric(5, 4), nullable=True)
    needs_careful_review = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    origin_suggestion_id = Column(Integer, ForeignKey("agent_suggestions.id", ondelete="SET NULL"), nullable=True)
    carried_from_voce_id = Column(Integer, ForeignKey("playbook_voci.id", ondelete="SET NULL"), nullable=True)
    validata_da_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    validata_il = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    versione = relationship("PlaybookVersione", back_populates="voci")
    carried_from = relationship("PlaybookVoce", remote_side=[id], lazy="select")

    __table_args__ = (
        Index("ix_playbook_voci_playbook_versione_id_fase_stato", "playbook_versione_id", "fase", "stato"),
        UniqueConstraint("playbook_versione_id", "fase", "titolo", name="uq_playbook_voci_titolo"),
        CheckConstraint("fase IN ('presentazione','avvio','gestione','rendicontazione')", name="ck_playbook_voci_fase"),
        CheckConstraint("length(trim(titolo)) > 0", name="ck_playbook_voci_titolo_non_vuoto"),
        CheckConstraint("origine IN ('manuale','vademecum','regola')", name="ck_playbook_voci_origine"),
        CheckConstraint("stato IN ('proposta','validata','rifiutata','superata')", name="ck_playbook_voci_stato"),
        CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 1)", name="ck_playbook_voci_confidence"),
        CheckConstraint("(stato <> 'validata') OR (validata_da_user_id IS NOT NULL AND validata_il IS NOT NULL)", name="ck_playbook_voci_validazione_completa"),
    )


class AttivitaOperativa(Base):
    __tablename__ = "attivita_operative"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False)
    avviso_revisione_id = Column(Integer, ForeignKey("avviso_revisioni.id", ondelete="SET NULL"), nullable=True)
    playbook_voce_id = Column(Integer, ForeignKey("playbook_voci.id", ondelete="SET NULL"), nullable=True)
    avviso_scadenza_id = Column(Integer, ForeignKey("avviso_scadenze.id", ondelete="SET NULL"), nullable=True)
    fase = Column(String(20), nullable=False)
    ordine = Column(Integer, nullable=False, default=0, server_default="0")
    titolo = Column(String(300), nullable=False)
    descrizione = Column(Text, nullable=True)
    stato = Column(String(20), nullable=False, default="da_fare", server_default="da_fare")
    scadenza = Column(Date, nullable=True)
    tassativa = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    assegnatario_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    origin_suggestion_id = Column(Integer, ForeignKey("agent_suggestions.id", ondelete="SET NULL"), nullable=True)
    completata_da_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    completata_il = Column(DateTime(timezone=True), nullable=True)
    note = Column(Text, nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    eventi = relationship(
        "AttivitaEvento",
        back_populates="attivita",
        cascade="all, delete-orphan",
        lazy="select",
        order_by="AttivitaEvento.id",
    )

    __table_args__ = (
        Index("ix_attivita_operative_project_id_fase_stato_scadenza", "project_id", "fase", "stato", "scadenza"),
        UniqueConstraint("project_id", "fase", "titolo", name="uq_attivita_operative_titolo"),
        CheckConstraint("fase IN ('presentazione','avvio','gestione','rendicontazione')", name="ck_attivita_operative_fase"),
        CheckConstraint("length(trim(titolo)) > 0", name="ck_attivita_operative_titolo_non_vuoto"),
        CheckConstraint("stato IN ('da_fare','in_corso','completata','non_applicabile')", name="ck_attivita_operative_stato"),
        CheckConstraint("(stato <> 'completata') OR (completata_da_user_id IS NOT NULL AND completata_il IS NOT NULL)", name="ck_attivita_completamento"),
    )


class AttivitaEvento(Base):
    __tablename__ = "attivita_eventi"

    id = Column(Integer, primary_key=True)
    attivita_id = Column(Integer, ForeignKey("attivita_operative.id", ondelete="CASCADE"), nullable=False)
    tipo_evento = Column(String(30), nullable=False)
    payload = Column(AVVISO_JSON_TYPE, nullable=True)
    actor_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    actor_agente = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    attivita = relationship("AttivitaOperativa", back_populates="eventi")

    __table_args__ = (
        Index("ix_attivita_eventi_attivita_id_tipo_evento_created_at", "attivita_id", "tipo_evento", "created_at"),
        CheckConstraint("tipo_evento IN ('creata','stato_cambiato','scadenza_modificata','assegnata','nota','riaperta')", name="ck_attivita_eventi_tipo"),
        CheckConstraint("actor_user_id IS NOT NULL OR actor_agente IS NOT NULL", name="ck_attivita_eventi_actor"),
    )
