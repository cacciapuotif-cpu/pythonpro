from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator, computed_field
from typing import Any, Dict, Generic, List, Optional, TypeVar
from datetime import datetime

T = TypeVar("T")


def _validate_piva_light(v: Optional[str]) -> Optional[str]:
    if v is None or v == "":
        return None
    clean = str(v).replace(" ", "").replace("IT", "").replace("it", "")
    if not clean.isdigit() or len(clean) != 11:
        raise ValueError("Partita IVA deve essere di 11 cifre numeriche")
    return clean


def _normalize_contract_type(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None

    normalized = str(v).strip()
    if not normalized:
        return None

    contract_type_map = {
        "professionale": "professionale",
        "occasionale": "occasionale",
        "ordine_servizio": "ordine_servizio",
        "ordine di servizio": "ordine_servizio",
        "contratto_progetto": "contratto_progetto",
        "contratto a progetto": "contratto_progetto",
        "documento_generico": "documento_generico",
        "documento generico": "documento_generico",
    }

    return contract_type_map.get(normalized.lower(), normalized.lower().replace(" ", "_"))


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    pages: int
    has_next: bool

class CollaboratorBase(BaseModel):
    first_name: str = Field(...)
    last_name: str = Field(...)
    email: EmailStr
    fiscal_code: str = Field(..., min_length=16, max_length=16)
    partita_iva: Optional[str] = Field(None)
    phone: Optional[str] = Field(None)
    position: Optional[str] = Field(None)
    birthplace: Optional[str] = Field(None)
    birth_date: Optional[datetime] = Field(None)
    gender: Optional[str] = Field(None)
    city: Optional[str] = Field(None)
    address: Optional[str] = Field(None)
    education: Optional[str] = Field(None)
    profilo_professionale: Optional[str] = Field(None)
    competenze_principali: Optional[str] = Field(None)
    certificazioni: Optional[str] = Field(None)
    sito_web: Optional[str] = Field(None)
    portfolio_url: Optional[str] = Field(None)
    linkedin_url: Optional[str] = Field(None)
    facebook_url: Optional[str] = Field(None)
    instagram_url: Optional[str] = Field(None)
    tiktok_url: Optional[str] = Field(None)
    is_agency: bool = False
    is_consultant: bool = False
    documento_identita_scadenza: Optional[datetime] = Field(None)

    @field_validator("partita_iva", mode="before")
    @classmethod
    def check_partita_iva(cls, v):
        return _validate_piva_light(v)

class CollaboratorCreate(CollaboratorBase):
    pass

class CollaboratorUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    partita_iva: Optional[str] = None
    phone: Optional[str] = None
    position: Optional[str] = None
    birthplace: Optional[str] = None
    birth_date: Optional[datetime] = None
    gender: Optional[str] = None
    fiscal_code: Optional[str] = Field(None, min_length=16, max_length=16)
    city: Optional[str] = None
    address: Optional[str] = None
    education: Optional[str] = None
    profilo_professionale: Optional[str] = None
    competenze_principali: Optional[str] = None
    certificazioni: Optional[str] = None
    sito_web: Optional[str] = None
    portfolio_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    facebook_url: Optional[str] = None
    instagram_url: Optional[str] = None
    tiktok_url: Optional[str] = None
    is_agency: Optional[bool] = None
    is_consultant: Optional[bool] = None
    documento_identita_scadenza: Optional[datetime] = None

    @field_validator("partita_iva", mode="before")
    @classmethod
    def check_partita_iva(cls, v):
        return _validate_piva_light(v)

class Collaborator(CollaboratorBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    documento_identita_filename: Optional[str] = Field(None)
    documento_identita_uploaded_at: Optional[datetime] = None
    documento_identita_scadenza: Optional[datetime] = None
    curriculum_filename: Optional[str] = Field(None)
    curriculum_uploaded_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, use_enum_values=True)

class ProjectBase(BaseModel):
    name: str = Field(...)
    description: Optional[str] = Field(None)
    start_date: Optional[datetime] = Field(None)
    end_date: Optional[datetime] = Field(None)
    status: str = Field("active")
    ente_erogatore: Optional[str] = None
    cup: Optional[str] = None
    atto_approvazione: Optional[str] = None
    sede_aziendale_comune: Optional[str] = None
    sede_aziendale_via: Optional[str] = None
    sede_aziendale_numero_civico: Optional[str] = None
    avviso: Optional[str] = None
    avviso_id: Optional[int] = None
    avviso_pf_id: Optional[int] = None
    template_piano_finanziario_id: Optional[int] = None

class ProjectCreate(ProjectBase):
    pass

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    status: Optional[str] = None
    ente_erogatore: Optional[str] = None
    cup: Optional[str] = None
    atto_approvazione: Optional[str] = None
    sede_aziendale_comune: Optional[str] = None
    sede_aziendale_via: Optional[str] = None
    sede_aziendale_numero_civico: Optional[str] = None
    avviso: Optional[str] = None
    avviso_id: Optional[int] = None
    avviso_pf_id: Optional[int] = None
    template_piano_finanziario_id: Optional[int] = None

class Project(ProjectBase):
    id: int
    ente_attuatore_id: Optional[int] = None
    avviso_rel: Optional["Avviso"] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, use_enum_values=True)


class AvvisoBase(BaseModel):
    codice: str
    ente_erogatore: str
    descrizione: Optional[str] = None
    template_id: Optional[int] = None
    is_active: bool = True


class AvvisoCreate(AvvisoBase):
    pass


class AvvisoUpdate(BaseModel):
    codice: Optional[str] = None
    ente_erogatore: Optional[str] = None
    descrizione: Optional[str] = None
    template_id: Optional[int] = None
    is_active: Optional[bool] = None


class Avviso(AvvisoBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class AuditLogBase(BaseModel):
    entity: str
    action: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    user_id: Optional[int] = None


class AuditLogCreate(AuditLogBase):
    pass


class AuditLog(AuditLogBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class PianoFinanziarioContextItem(BaseModel):
    id: int
    anno: int
    ente_erogatore: str
    avviso: str
    totale_consuntivo: float
    totale_preventivo: float
    budget_usage_percentage: float
    is_warning_90_budget: bool


class ProjectCollaboratorHoursContext(BaseModel):
    collaborator_id: int
    collaborator_name: str
    assigned_hours: float
    completed_hours: float
    attendance_hours: float


class ProjectFullContext(BaseModel):
    project: Project
    implementing_entity: Optional["ImplementingEntity"] = None
    active_piani_finanziari: List[PianoFinanziarioContextItem] = []
    collaborator_hours: List[ProjectCollaboratorHoursContext] = []
    generated_at: datetime


class AgentCatalogItem(BaseModel):
    name: str
    label: str
    description: str
    supported_entity_types: List[str] = Field(default_factory=list)


class AgentLlmHealth(BaseModel):
    provider: str
    enabled: bool
    model: Optional[str] = None
    base_url: Optional[str] = None
    reachable: bool
    status_code: Optional[int] = None
    detail: str


class AgentRunRequest(BaseModel):
    agent_name: str
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    requested_by_user_id: Optional[int] = None
    input_payload: Dict[str, Any] = Field(default_factory=dict)


class AgentRunBase(BaseModel):
    agent_name: Optional[str] = None
    agent_type: Optional[str] = None
    agent_version: Optional[str] = None
    status: str
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    requested_by_user_id: Optional[int] = None
    input_payload: Optional[str] = None
    result_summary: Optional[str] = None
    error_message: Optional[str] = None
    suggestions_count: int = 0
    suggestions_created: int = 0
    items_processed: int = 0
    items_with_issues: int = 0


class AgentSuggestionBase(BaseModel):
    agent_name: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    suggestion_type: Optional[str] = None
    severity: Optional[str] = None
    status: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    payload: Optional[str] = None
    confidence: Optional[float] = None
    reviewed_by_user_id: Optional[int] = None


class AgentReviewActionBase(BaseModel):
    action: str
    notes: Optional[str] = None
    reviewed_by_user_id: Optional[int] = None
    reviewed_by: Optional[str] = None


class AgentReviewActionCreate(AgentReviewActionBase):
    pass


class AgentWorkflowActionRequest(BaseModel):
    action: str
    notes: Optional[str] = None
    reviewed_by_user_id: Optional[int] = None


class AgentReviewAction(AgentReviewActionBase):
    id: int
    reviewed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class AgentSuggestion(AgentSuggestionBase):
    id: int
    run_id: int
    reviewed_at: Optional[datetime] = None
    created_at: datetime
    review_actions: List[AgentReviewAction] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class AgentRun(AgentRunBase):
    id: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    suggestions: List[AgentSuggestion] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# AgentRun already includes suggestions, expose as alias for router compatibility
AgentRunWithSuggestions = AgentRun


class AgentSuggestionWithDetails(AgentSuggestion):
    run: Optional["AgentRunShallow"] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class AgentRunShallow(AgentRunBase):
    """AgentRun senza suggestions annidati - usato in AgentSuggestionWithDetails per evitare ricorsione."""
    id: int
    started_at: datetime
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


AgentSuggestionWithDetails.model_rebuild()


class AgentCommunicationDraftBase(BaseModel):
    agent_name: str
    channel: str
    recipient_type: str
    recipient_id: Optional[int] = None
    recipient_email: str
    recipient_name: Optional[str] = None
    subject: str
    body: str
    status: str
    meta_payload: Optional[str] = None
    created_by_user_id: Optional[int] = None
    reviewed_by_user_id: Optional[int] = None


class AgentCommunicationDraftStatusUpdate(BaseModel):
    status: str
    reviewed_by_user_id: Optional[int] = None


class AgentCommunicationDraft(AgentCommunicationDraftBase):
    id: int
    run_id: Optional[int] = None
    suggestion_id: Optional[int] = None
    sent_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

class AttendanceBase(BaseModel):
    collaborator_id: int
    project_id: int
    assignment_id: Optional[int] = None
    date: datetime = Field(...)
    start_time: datetime = Field(...)
    end_time: datetime = Field(...)
    hours: float = Field(...)
    notes: Optional[str] = Field(None)

class AttendanceCreate(AttendanceBase):
    pass

class AttendanceUpdate(BaseModel):
    assignment_id: Optional[int] = None
    date: Optional[datetime] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    hours: Optional[float] = None
    notes: Optional[str] = None

class Attendance(AttendanceBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, use_enum_values=True)

class CollaboratorWithProjects(Collaborator):
    projects: List[Project] = []

class ProjectWithCollaborators(Project):
    collaborators: List[Collaborator] = []

class AttendanceWithDetails(Attendance):
    collaborator: Collaborator
    project: Project

# Schemi per Assignment (Assegnazioni dettagliate)
class AssignmentBase(BaseModel):
    collaborator_id: int
    project_id: int
    role: str  # Mansione
    edizione_label: Optional[str] = None
    assigned_hours: float  # Ore assegnate
    start_date: datetime  # Inizio attività
    end_date: datetime  # Fine attività
    contract_signed_date: Optional[datetime] = None  # Data firma contratto
    hourly_rate: float  # Importo orario
    contract_type: Optional[str] = None  # Tipo contratto: Professionale, Occasionale, Ordine di servizio, Contratto a progetto

class AssignmentCreate(AssignmentBase):
    @field_validator("contract_type", mode="before")
    @classmethod
    def normalize_contract_type(cls, v):
        return _normalize_contract_type(v)

class AssignmentUpdate(BaseModel):
    role: Optional[str] = None
    edizione_label: Optional[str] = None
    assigned_hours: Optional[float] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    contract_signed_date: Optional[datetime] = None
    hourly_rate: Optional[float] = None
    contract_type: Optional[str] = None

    @field_validator("contract_type", mode="before")
    @classmethod
    def normalize_contract_type(cls, v):
        return _normalize_contract_type(v)

class Assignment(AssignmentBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_hours: float  # Ore completate (calcolate dalle presenze)
    progress_percentage: float  # Percentuale di completamento
    is_active: bool  # Se l'assegnazione è attiva

    class Config:
        from_attributes = True

class AssignmentWithDetails(Assignment):
    collaborator: Collaborator
    project: Project

# ========================================
# SCHEMI PER ENTE ATTUATORE (Implementing Entity)
# ========================================

class ImplementingEntityBase(BaseModel):
    """Schema base per Ente Attuatore"""
    # Dati legali
    ragione_sociale: str
    forma_giuridica: Optional[str] = None
    partita_iva: str  # Obbligatorio e unique
    codice_fiscale: Optional[str] = None
    codice_ateco: Optional[str] = None
    rea_numero: Optional[str] = None
    registro_imprese: Optional[str] = None

    # Sede legale
    indirizzo: Optional[str] = None
    cap: Optional[str] = None
    citta: Optional[str] = None
    provincia: Optional[str] = None
    nazione: Optional[str] = "IT"

    # Contatti
    pec: Optional[str] = None
    email: Optional[str] = None
    telefono: Optional[str] = None
    sdi: Optional[str] = None

    # Dati pagamento
    iban: Optional[str] = None
    intestatario_conto: Optional[str] = None

    # Referente
    referente_nome: Optional[str] = None
    referente_cognome: Optional[str] = None
    referente_email: Optional[str] = None
    referente_telefono: Optional[str] = None
    referente_ruolo: Optional[str] = None

    # Legale rappresentante
    legale_rappresentante_nome: Optional[str] = None
    legale_rappresentante_cognome: Optional[str] = None
    legale_rappresentante_luogo_nascita: Optional[str] = None
    legale_rappresentante_data_nascita: Optional[datetime] = None
    legale_rappresentante_comune_residenza: Optional[str] = None
    legale_rappresentante_via_residenza: Optional[str] = None
    legale_rappresentante_codice_fiscale: Optional[str] = None

    # Altro
    note: Optional[str] = None
    is_active: bool = True

class ImplementingEntityCreate(ImplementingEntityBase):
    """Schema per creazione Ente Attuatore"""
    pass

class ImplementingEntityUpdate(BaseModel):
    """Schema per aggiornamento Ente Attuatore - tutti i campi opzionali"""
    ragione_sociale: Optional[str] = None
    forma_giuridica: Optional[str] = None
    partita_iva: Optional[str] = None
    codice_fiscale: Optional[str] = None
    codice_ateco: Optional[str] = None
    rea_numero: Optional[str] = None
    registro_imprese: Optional[str] = None

    indirizzo: Optional[str] = None
    cap: Optional[str] = None
    citta: Optional[str] = None
    provincia: Optional[str] = None
    nazione: Optional[str] = None

    pec: Optional[str] = None
    email: Optional[str] = None
    telefono: Optional[str] = None
    sdi: Optional[str] = None

    iban: Optional[str] = None
    intestatario_conto: Optional[str] = None

    referente_nome: Optional[str] = None
    referente_cognome: Optional[str] = None
    referente_email: Optional[str] = None
    referente_telefono: Optional[str] = None
    referente_ruolo: Optional[str] = None

    legale_rappresentante_nome: Optional[str] = None
    legale_rappresentante_cognome: Optional[str] = None
    legale_rappresentante_luogo_nascita: Optional[str] = None
    legale_rappresentante_data_nascita: Optional[datetime] = None
    legale_rappresentante_comune_residenza: Optional[str] = None
    legale_rappresentante_via_residenza: Optional[str] = None
    legale_rappresentante_codice_fiscale: Optional[str] = None

    note: Optional[str] = None
    is_active: Optional[bool] = None

class ImplementingEntity(ImplementingEntityBase):
    """Schema completo Ente Attuatore con ID e timestamps"""
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    # Dati logo (se uploadato)
    logo_filename: Optional[str] = None
    logo_uploaded_at: Optional[datetime] = None

    # Proprietà calcolate
    indirizzo_completo: Optional[str] = None
    referente_nome_completo: Optional[str] = None
    legale_rappresentante_nome_completo: Optional[str] = None

    class Config:
        from_attributes = True

class ImplementingEntityWithProjects(ImplementingEntity):
    """Schema Ente Attuatore con lista progetti collegati"""
    projects: List[Project] = []

# Aggiornamento schema Project per includere ente_attuatore_id
class ProjectBaseExtended(ProjectBase):
    """Estensione ProjectBase con FK ente_attuatore"""
    ente_attuatore_id: Optional[int] = None

class ProjectCreateExtended(ProjectBaseExtended):
    """Schema creazione progetto con ente"""
    pass

class ProjectUpdateExtended(ProjectUpdate):
    """Schema update progetto con ente"""
    ente_attuatore_id: Optional[int] = None

class ProjectWithEntity(Project):
    """Schema progetto con ente attuatore completo"""
    ente_attuatore_id: Optional[int] = None
    ente_attuatore: Optional[ImplementingEntity] = None

    class Config:
        from_attributes = True

# ========================================
# SCHEMI PER ASSOCIAZIONE PROGETTO-MANSIONE-ENTE
# ========================================

class ProgettoMansioneEnteBase(BaseModel):
    """Schema base per associazione Progetto-Mansione-Ente"""
    progetto_id: int
    ente_attuatore_id: int
    mansione: str
    descrizione_mansione: Optional[str] = None
    data_inizio: datetime
    data_fine: datetime
    ore_previste: float
    ore_effettive: float = 0.0
    tariffa_oraria: Optional[float] = None
    budget_totale: Optional[float] = None
    tipo_contratto: Optional[str] = None
    is_active: bool = True
    note: Optional[str] = None

class ProgettoMansioneEnteCreate(ProgettoMansioneEnteBase):
    """Schema per creazione associazione"""
    @field_validator("tipo_contratto", mode="before")
    @classmethod
    def normalize_contract_type(cls, v):
        return _normalize_contract_type(v)

class ProgettoMansioneEnteUpdate(BaseModel):
    """Schema per aggiornamento associazione - tutti i campi opzionali"""
    progetto_id: Optional[int] = None
    ente_attuatore_id: Optional[int] = None
    mansione: Optional[str] = None
    descrizione_mansione: Optional[str] = None
    data_inizio: Optional[datetime] = None
    data_fine: Optional[datetime] = None
    ore_previste: Optional[float] = None
    ore_effettive: Optional[float] = None
    tariffa_oraria: Optional[float] = None
    budget_totale: Optional[float] = None
    tipo_contratto: Optional[str] = None
    is_active: Optional[bool] = None
    note: Optional[str] = None

    @field_validator("tipo_contratto", mode="before")
    @classmethod
    def normalize_contract_type(cls, v):
        return _normalize_contract_type(v)

class ProgettoMansioneEnte(ProgettoMansioneEnteBase):
    """Schema completo associazione con ID, timestamps e proprietà calcolate"""
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    # Proprietà calcolate
    ore_rimanenti: float
    percentuale_completamento: float
    costo_effettivo: float

    class Config:
        from_attributes = True

class ProgettoMansioneEnteWithDetails(ProgettoMansioneEnte):
    """Schema associazione con dettagli completi di progetto ed ente"""
    progetto: Project
    ente_attuatore: ImplementingEntity

    class Config:
        from_attributes = True


# ========================================
# SCHEMI PER PIANI FINANZIARI
# ========================================

class PianoFinanziarioLegacyBase(BaseModel):
    progetto_id: int
    template_id: Optional[int] = None
    avviso_id: Optional[int] = None
    anno: int = Field(..., ge=2020, le=2100)
    ente_erogatore: str = "Formazienda"
    avviso: str = ""


class PianoFinanziarioLegacyCreate(PianoFinanziarioLegacyBase):
    pass


class PianoFinanziarioLegacy(PianoFinanziarioLegacyBase):
    id: int
    avviso_rel: Optional["Avviso"] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class VocePianoFinanziarioLegacyBase(BaseModel):
    macrovoce: str
    voce_codice: str
    descrizione: str
    progetto_label: Optional[str] = None
    edizione_label: Optional[str] = None
    ore: float = Field(0.0, ge=0)
    importo_consuntivo: float = Field(0.0, ge=0)
    importo_preventivo: float = Field(0.0, ge=0)
    importo_presentato: float = Field(0.0, ge=0)
    collaborator_id: Optional[int] = None


class VocePianoFinanziarioLegacyCreate(VocePianoFinanziarioLegacyBase):
    piano_id: int


class VocePianoFinanziarioUpsert(VocePianoFinanziarioLegacyBase):
    id: Optional[int] = None


class PianoFinanziarioBulkUpdate(BaseModel):
    voci: List[VocePianoFinanziarioUpsert]


class VocePianoFinanziarioLegacy(VocePianoFinanziarioLegacyBase):
    id: int
    piano_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by_user: Optional[str] = None
    totale_consuntivo_riferimento: float = 0.0

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @computed_field(return_type=float)
    @property
    def perc_consuntivo(self) -> float:
        if not self.totale_consuntivo_riferimento:
            return 0.0
        return round((self.importo_consuntivo / self.totale_consuntivo_riferimento) * 100, 2)


class PianoFinanziarioDettaglio(PianoFinanziarioLegacy):
    progetto: "Project"
    voci: List[VocePianoFinanziarioLegacy]
    template_documento: Optional["TemplateDocumentoSelezionato"] = None


class PianoFinanziarioAlert(BaseModel):
    level: str
    code: str
    message: str


class PianoFinanziarioMacrovoceSummary(BaseModel):
    macrovoce: str
    titolo: str
    limite_percentuale: Optional[float] = None
    importo_consuntivo: float = 0.0
    importo_preventivo: float = 0.0
    percentuale_consuntivo: float = 0.0
    percentuale_preventivo: float = 0.0
    alert_level: str = "ok"
    sforata: bool = False


class OreRuoloPianoFinanziario(BaseModel):
    collaborator_id: Optional[int] = None
    collaborator_name: Optional[str] = None
    role: str
    n_presenze: int
    ore_effettive: float
    costo_effettivo: float
    voce_codice: Optional[str] = None
    voce_label: Optional[str] = None


class PianoFinanziarioRiepilogo(BaseModel):
    piano_id: int
    totale_consuntivo: float
    totale_preventivo: float
    contributo_richiesto: float
    cofinanziamento: float
    macrovoci: List[PianoFinanziarioMacrovoceSummary]
    alerts: List[PianoFinanziarioAlert]
    ore_per_ruolo: List[OreRuoloPianoFinanziario] = []
    ore_effettive_totali: float = 0.0


class RigaNominativoFondimpresaBase(BaseModel):
    nominativo: str = ""
    ore: float = Field(0.0, ge=0)
    costo_orario: float = Field(0.0, ge=0)


class RigaNominativoFondimpresaUpsert(RigaNominativoFondimpresaBase):
    id: Optional[int] = None


class RigaNominativoFondimpresa(RigaNominativoFondimpresaBase):
    id: int

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @computed_field(return_type=float)
    @property
    def totale(self) -> float:
        return round((self.ore or 0.0) * (self.costo_orario or 0.0), 2)


class DocumentoFondimpresaBase(BaseModel):
    tipo_documento: Optional[str] = None
    numero_documento: Optional[str] = None
    data_documento: Optional[datetime] = None
    importo_totale: float = Field(0.0, ge=0)
    importo_imputato: float = Field(0.0, ge=0)
    data_pagamento: Optional[datetime] = None

    @field_validator("importo_imputato")
    @classmethod
    def validate_importo_imputato(cls, value, info):
        importo_totale = info.data.get("importo_totale", 0.0) if info.data else 0.0
        if value is not None and importo_totale is not None and value > importo_totale:
            raise ValueError("Importo imputato non può superare l'importo totale del documento")
        return value


class DocumentoFondimpresaUpsert(DocumentoFondimpresaBase):
    id: Optional[int] = None


class DocumentoFondimpresa(DocumentoFondimpresaBase):
    id: int

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class VoceFondimpresaBase(BaseModel):
    sezione: str
    voce_codice: str
    descrizione: str
    note_temporali: Optional[str] = None


class VoceFondimpresaUpsert(VoceFondimpresaBase):
    id: Optional[int] = None
    righe_nominativo: List[RigaNominativoFondimpresaUpsert] = Field(default_factory=list)
    documenti: List[DocumentoFondimpresaUpsert] = Field(default_factory=list)


class VoceFondimpresa(VoceFondimpresaBase):
    id: int
    totale_voce: float = 0.0
    righe_nominativo: List[RigaNominativoFondimpresa] = Field(default_factory=list)
    documenti: List[DocumentoFondimpresa] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class PianoFondimpresaBase(BaseModel):
    progetto_id: int
    avviso_id: Optional[int] = None
    anno: int = Field(..., ge=2020, le=2100)
    ente_erogatore: str = "Fondimpresa"
    tipo_conto: str = "conto_formazione"
    totale_preventivo: float = Field(0.0, ge=0)


class PianoFondimpresaCreate(PianoFondimpresaBase):
    pass


class PianoFondimpresa(PianoFondimpresaBase):
    id: int
    avviso_rel: Optional["Avviso"] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class PianoFondimpresaBulkUpdate(BaseModel):
    voci: List[VoceFondimpresaUpsert]


class PianoFondimpresaDocumentiBulkUpdate(BaseModel):
    voci: List[VoceFondimpresaUpsert]


class BudgetConsulenteFondimpresaBase(BaseModel):
    nominativo: str = ""
    ore: float = Field(0.0, ge=0)
    costo_orario: float = Field(0.0, ge=0)


class BudgetConsulenteFondimpresaUpsert(BudgetConsulenteFondimpresaBase):
    id: Optional[int] = None


class BudgetConsulenteFondimpresa(BudgetConsulenteFondimpresaBase):
    id: int

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @computed_field(return_type=float)
    @property
    def totale(self) -> float:
        return round((self.ore or 0.0) * (self.costo_orario or 0.0), 2)


class BudgetCostoFissoFondimpresaBase(BaseModel):
    tipologia: str = ""
    parametro: Optional[str] = None
    totale: float = Field(0.0, ge=0)


class BudgetCostoFissoFondimpresaUpsert(BudgetCostoFissoFondimpresaBase):
    id: Optional[int] = None


class BudgetCostoFissoFondimpresa(BudgetCostoFissoFondimpresaBase):
    id: int

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class BudgetMargineFondimpresaBase(BaseModel):
    tipologia: str = ""
    percentuale: float = Field(0.0, ge=0)


class BudgetMargineFondimpresaUpsert(BudgetMargineFondimpresaBase):
    id: Optional[int] = None


class BudgetMargineFondimpresa(BudgetMargineFondimpresaBase):
    id: int
    totale_riferimento: float = 0.0

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @computed_field(return_type=float)
    @property
    def totale(self) -> float:
        return round((self.totale_riferimento or 0.0) * ((self.percentuale or 0.0) / 100), 2)


class DettaglioBudgetFondimpresaUpdate(BaseModel):
    consulenti: List[BudgetConsulenteFondimpresaUpsert] = Field(default_factory=list)
    costi_fissi: List[BudgetCostoFissoFondimpresaUpsert] = Field(default_factory=list)
    margini: List[BudgetMargineFondimpresaUpsert] = Field(default_factory=list)


class DettaglioBudgetFondimpresa(BaseModel):
    consulenti: List[BudgetConsulenteFondimpresa] = Field(default_factory=list)
    costi_fissi: List[BudgetCostoFissoFondimpresa] = Field(default_factory=list)
    margini: List[BudgetMargineFondimpresa] = Field(default_factory=list)


class PianoFondimpresaDettaglio(PianoFondimpresa):
    progetto: Project
    voci: List[VoceFondimpresa]
    dettaglio_budget: Optional[DettaglioBudgetFondimpresa] = None


class PianoFondimpresaSezioneSummary(BaseModel):
    sezione: str
    titolo: str
    totale: float = 0.0
    percentuale: float = 0.0
    min_percentuale: Optional[float] = None
    max_percentuale: Optional[float] = None
    alert_level: str = "ok"


class PianoFondimpresaRiepilogo(BaseModel):
    piano_id: int
    totale_a: float
    totale_b: float
    totale_c: float
    totale_d: float
    totale_escluso_cofinanziamento: float
    totale_preventivo: float
    differenza_preventivo_consuntivo: float
    sezioni: List[PianoFondimpresaSezioneSummary]
    alerts: List[PianoFinanziarioAlert]


# ========================================
# SCHEMI PER TEMPLATE CONTRATTI
# ========================================

class ContractTemplateBase(BaseModel):
    """Schema base per Template Contratto"""
    nome_template: str
    descrizione: Optional[str] = None
    ambito_template: str = "contratto"  # "contratto", "timesheet", "piano_finanziario", "preventivo", "ordine", "generico"
    chiave_documento: Optional[str] = None
    ente_attuatore_id: Optional[int] = None
    progetto_id: Optional[int] = None
    ente_erogatore: Optional[str] = None
    avviso: Optional[str] = None
    tipo_contratto: str  # "professionale", "occasionale", "ordine_servizio", "contratto_progetto", "documento_generico"
    contenuto_html: str  # Contenuto HTML con variabili {{variabile}}
    intestazione: Optional[str] = None
    pie_pagina: Optional[str] = None

    # Configurazione layout logo
    include_logo_ente: bool = True
    posizione_logo: str = "header"  # "header", "footer", "none"
    dimensione_logo: str = "medium"  # "small", "medium", "large"

    # Clausole standard
    include_clausola_privacy: bool = True
    include_clausola_riservatezza: bool = False
    include_clausola_proprieta_intellettuale: bool = False

    # Formato output
    formato_data: str = "%d/%m/%Y"
    formato_importo: str = "€ {:.2f}"

    # Stato
    is_default: Optional[bool] = False
    is_active: bool = True
    versione: str = "1.0"
    note_interne: Optional[str] = None


class ContractTemplateCreate(ContractTemplateBase):
    """Schema per creazione Template Contratto"""
    created_by: Optional[str] = None


class ContractTemplateUpdate(BaseModel):
    """Schema per aggiornamento Template Contratto - tutti i campi opzionali"""
    nome_template: Optional[str] = None
    descrizione: Optional[str] = None
    ambito_template: Optional[str] = None
    chiave_documento: Optional[str] = None
    ente_attuatore_id: Optional[int] = None
    progetto_id: Optional[int] = None
    ente_erogatore: Optional[str] = None
    avviso: Optional[str] = None
    tipo_contratto: Optional[str] = None
    contenuto_html: Optional[str] = None
    intestazione: Optional[str] = None
    pie_pagina: Optional[str] = None

    include_logo_ente: Optional[bool] = None
    posizione_logo: Optional[str] = None
    dimensione_logo: Optional[str] = None

    include_clausola_privacy: Optional[bool] = None
    include_clausola_riservatezza: Optional[bool] = None
    include_clausola_proprieta_intellettuale: Optional[bool] = None

    formato_data: Optional[str] = None
    formato_importo: Optional[str] = None

    is_default: Optional[bool] = None
    is_active: Optional[bool] = None
    versione: Optional[str] = None
    note_interne: Optional[str] = None
    updated_by: Optional[str] = None


class ContractTemplate(ContractTemplateBase):
    """Schema completo Template Contratto"""
    id: int
    numero_utilizzi: int
    ultimo_utilizzo: Optional[datetime] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TemplateDocumentoSelezionato(BaseModel):
    id: int
    nome_template: str
    ambito_template: str
    chiave_documento: Optional[str] = None
    ente_erogatore: Optional[str] = None
    avviso: Optional[str] = None
    progetto_id: Optional[int] = None
    ente_attuatore_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ContractTemplateWithVariables(ContractTemplate):
    """Schema Template Contratto con lista variabili disponibili"""
    variabili_disponibili: dict

    class Config:
        from_attributes = True


class ContractGenerationRequest(BaseModel):
    """Schema per richiesta generazione contratto"""
    # ID delle entità
    collaboratore_id: int
    progetto_id: int
    ente_attuatore_id: int
    mansione: str

    # Dati economici e temporali
    ore_previste: float
    tariffa_oraria: float
    data_inizio: datetime
    data_fine: datetime
    contract_signed_date: Optional[datetime] = None

    # Template da usare (opzionale, altrimenti usa il default per tipo_contratto)
    template_id: Optional[int] = None
    tipo_contratto: Optional[str] = None  # Se template_id non fornito

    # Note aggiuntive opzionali
    note_personalizzate: Optional[str] = None


# ─────────────────────────────────────────────
# BLOCCO 1 — ANAGRAFICA ESPANSA
# ─────────────────────────────────────────────

def _validate_piva(v: Optional[str]) -> Optional[str]:
    """Validazione P.IVA italiana: 11 cifre + checksum ufficiale."""
    if v is None:
        return v
    clean = v.replace(" ", "").replace("IT", "").replace("it", "")
    if not clean.isdigit() or len(clean) != 11:
        raise ValueError("Partita IVA deve essere di 11 cifre numeriche")
    # Algoritmo checksum P.IVA italiana
    odd_sum = sum(int(clean[i]) for i in range(0, 10, 2))
    even_sum = 0
    for i in range(1, 10, 2):
        d = int(clean[i]) * 2
        even_sum += d if d < 10 else d - 9
    check = (10 - (odd_sum + even_sum) % 10) % 10
    if check != int(clean[10]):
        raise ValueError("Partita IVA non valida (checksum errato)")
    return clean


# ── Agenzia ──────────────────────────────────

class AgenziaBase(BaseModel):
    nome: str = Field(..., min_length=2, max_length=200)
    partita_iva: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[EmailStr] = None
    note: Optional[str] = None
    collaborator_id: Optional[int] = None
    attivo: bool = True

    @field_validator("partita_iva", mode="before")
    @classmethod
    def check_partita_iva(cls, v):
        return _validate_piva_light(v)


class AgenziaCreate(AgenziaBase):
    pass


class AgenziaUpdate(BaseModel):
    nome: Optional[str] = Field(None, min_length=2, max_length=200)
    partita_iva: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[EmailStr] = None
    note: Optional[str] = None
    collaborator_id: Optional[int] = None
    attivo: Optional[bool] = None

    @field_validator("partita_iva", mode="before")
    @classmethod
    def check_partita_iva(cls, v):
        return _validate_piva_light(v)


class Agenzia(AgenziaBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# ── Consulente ───────────────────────────────

class ConsulenteBase(BaseModel):
    nome: str = Field(..., min_length=1, max_length=100)
    cognome: str = Field(..., min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    telefono: Optional[str] = None
    partita_iva: Optional[str] = None
    agenzia_id: Optional[int] = None
    zona_competenza: Optional[str] = None
    provvigione_percentuale: Optional[float] = Field(None, ge=0, le=100)
    note: Optional[str] = None
    attivo: bool = True

    @field_validator("partita_iva", mode="before")
    @classmethod
    def check_piva(cls, v):
        return _validate_piva(v)


class ConsulenteCreate(ConsulenteBase):
    pass


class ConsulenteUpdate(BaseModel):
    nome: Optional[str] = Field(None, min_length=1, max_length=100)
    cognome: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    telefono: Optional[str] = None
    partita_iva: Optional[str] = None
    agenzia_id: Optional[int] = None
    zona_competenza: Optional[str] = None
    provvigione_percentuale: Optional[float] = Field(None, ge=0, le=100)
    note: Optional[str] = None
    attivo: Optional[bool] = None

    @field_validator("partita_iva", mode="before")
    @classmethod
    def check_piva(cls, v):
        return _validate_piva(v)


class Consulente(ConsulenteBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ConsulenteWithAgenzia(Consulente):
    agenzia: Optional[Agenzia] = None


# ── AziendaCliente ───────────────────────────

class AziendaClienteBase(BaseModel):
    ragione_sociale: str = Field(..., min_length=2, max_length=200)
    partita_iva: str
    codice_fiscale: Optional[str] = None
    settore_ateco: Optional[str] = None
    attivita_erogate: Optional[str] = None
    indirizzo: Optional[str] = None
    citta: Optional[str] = None
    cap: Optional[str] = Field(None, pattern=r"^\d{5}$")
    provincia: Optional[str] = Field(None, min_length=2, max_length=2)
    email: Optional[EmailStr] = None
    pec: Optional[EmailStr] = None
    telefono: Optional[str] = None
    sito_web: Optional[str] = None
    linkedin_url: Optional[str] = None
    facebook_url: Optional[str] = None
    instagram_url: Optional[str] = None
    legale_rappresentante_nome: Optional[str] = None
    legale_rappresentante_cognome: Optional[str] = None
    legale_rappresentante_codice_fiscale: Optional[str] = None
    legale_rappresentante_email: Optional[EmailStr] = None
    legale_rappresentante_telefono: Optional[str] = None
    legale_rappresentante_indirizzo: Optional[str] = None
    legale_rappresentante_linkedin: Optional[str] = None
    legale_rappresentante_facebook: Optional[str] = None
    legale_rappresentante_instagram: Optional[str] = None
    legale_rappresentante_tiktok: Optional[str] = None
    referente_nome: Optional[str] = None
    referente_cognome: Optional[str] = None
    referente_ruolo: Optional[str] = None
    referente_email: Optional[EmailStr] = None
    referente_telefono: Optional[str] = None
    referente_indirizzo: Optional[str] = None
    referente_luogo_nascita: Optional[str] = None
    referente_data_nascita: Optional[datetime] = None
    referente_linkedin: Optional[str] = None
    referente_facebook: Optional[str] = None
    referente_instagram: Optional[str] = None
    referente_tiktok: Optional[str] = None
    agenzia_id: Optional[int] = None
    consulente_id: Optional[int] = None
    note: Optional[str] = None
    attivo: bool = True

    @field_validator("partita_iva", mode="before")
    @classmethod
    def check_piva(cls, v):
        return _validate_piva(v)

    @field_validator("provincia", mode="before")
    @classmethod
    def check_provincia(cls, v):
        if v:
            v = v.upper()
            if not v.isalpha() or len(v) != 2:
                raise ValueError("Provincia deve essere sigla 2 lettere (es: NA, MI)")
        return v


class AziendaClienteCreate(AziendaClienteBase):
    pass


class AziendaClienteUpdate(BaseModel):
    ragione_sociale: Optional[str] = Field(None, min_length=2, max_length=200)
    partita_iva: Optional[str] = None
    codice_fiscale: Optional[str] = None
    settore_ateco: Optional[str] = None
    attivita_erogate: Optional[str] = None
    indirizzo: Optional[str] = None
    citta: Optional[str] = None
    cap: Optional[str] = Field(None, pattern=r"^\d{5}$")
    provincia: Optional[str] = Field(None, min_length=2, max_length=2)
    email: Optional[EmailStr] = None
    pec: Optional[EmailStr] = None
    telefono: Optional[str] = None
    sito_web: Optional[str] = None
    linkedin_url: Optional[str] = None
    facebook_url: Optional[str] = None
    instagram_url: Optional[str] = None
    legale_rappresentante_nome: Optional[str] = None
    legale_rappresentante_cognome: Optional[str] = None
    legale_rappresentante_codice_fiscale: Optional[str] = None
    legale_rappresentante_email: Optional[EmailStr] = None
    legale_rappresentante_telefono: Optional[str] = None
    legale_rappresentante_indirizzo: Optional[str] = None
    legale_rappresentante_linkedin: Optional[str] = None
    legale_rappresentante_facebook: Optional[str] = None
    legale_rappresentante_instagram: Optional[str] = None
    legale_rappresentante_tiktok: Optional[str] = None
    referente_nome: Optional[str] = None
    referente_cognome: Optional[str] = None
    referente_ruolo: Optional[str] = None
    referente_email: Optional[EmailStr] = None
    referente_telefono: Optional[str] = None
    referente_indirizzo: Optional[str] = None
    referente_luogo_nascita: Optional[str] = None
    referente_data_nascita: Optional[datetime] = None
    referente_linkedin: Optional[str] = None
    referente_facebook: Optional[str] = None
    referente_instagram: Optional[str] = None
    referente_tiktok: Optional[str] = None
    agenzia_id: Optional[int] = None
    consulente_id: Optional[int] = None
    note: Optional[str] = None
    attivo: Optional[bool] = None

    @field_validator("partita_iva", mode="before")
    @classmethod
    def check_piva(cls, v):
        return _validate_piva(v)

    @field_validator("provincia", mode="before")
    @classmethod
    def check_provincia(cls, v):
        if v:
            v = v.upper()
            if not v.isalpha() or len(v) != 2:
                raise ValueError("Provincia deve essere sigla 2 lettere")
        return v


class AziendaCliente(AziendaClienteBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class AziendaClienteWithConsulente(AziendaCliente):
    agenzia: Optional[Agenzia] = None
    consulente: Optional[Consulente] = None


# ─────────────────────────────────────────────
# BLOCCO 3 — CATALOGO + LISTINI
# ─────────────────────────────────────────────

from typing import Literal

TIPI_PRODOTTO = Literal['apprendistato', 'tirocinio', 'formazione', 'altro']
TIPI_CLIENTE = Literal['standard', 'apprendistato', 'finanziato', 'gratis']


# ── Prodotto ─────────────────────────────────

class ProdottoBase(BaseModel):
    codice: Optional[str] = Field(None, max_length=50)
    nome: str = Field(..., min_length=2, max_length=200)
    descrizione: Optional[str] = None
    tipo: TIPI_PRODOTTO = 'altro'
    prezzo_base: float = Field(0.0, ge=0)
    unita_misura: str = Field('ora', max_length=50)
    attivo: bool = True


class ProdottoCreate(ProdottoBase):
    pass


class ProdottoUpdate(BaseModel):
    codice: Optional[str] = Field(None, max_length=50)
    nome: Optional[str] = Field(None, min_length=2, max_length=200)
    descrizione: Optional[str] = None
    tipo: Optional[TIPI_PRODOTTO] = None
    prezzo_base: Optional[float] = Field(None, ge=0)
    unita_misura: Optional[str] = None
    attivo: Optional[bool] = None


class Prodotto(ProdottoBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# ── Listino ──────────────────────────────────

class ListinoBase(BaseModel):
    nome: str = Field(..., min_length=2, max_length=200)
    descrizione: Optional[str] = None
    tipo_cliente: TIPI_CLIENTE = 'standard'
    attivo: bool = True


class ListinoCreate(ListinoBase):
    pass


class ListinoUpdate(BaseModel):
    nome: Optional[str] = Field(None, min_length=2, max_length=200)
    descrizione: Optional[str] = None
    tipo_cliente: Optional[TIPI_CLIENTE] = None
    attivo: Optional[bool] = None


class Listino(ListinoBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# ── ListinoVoce ──────────────────────────────

class ListinoVoceBase(BaseModel):
    listino_id: int
    prodotto_id: int
    prezzo_override: Optional[float] = Field(None, ge=0)
    sconto_percentuale: float = Field(0.0, ge=0, le=100)
    note: Optional[str] = None


class ListinoVoceCreate(ListinoVoceBase):
    pass


class ListinoVoceUpdate(BaseModel):
    prezzo_override: Optional[float] = Field(None, ge=0)
    sconto_percentuale: Optional[float] = Field(None, ge=0, le=100)
    note: Optional[str] = None


class ListinoVoce(ListinoVoceBase):
    id: int
    prezzo_finale: Optional[float] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ListinoVoceWithProdotto(ListinoVoce):
    prodotto: Optional[Prodotto] = None


class ListinoWithVoci(Listino):
    voci: List[ListinoVoceWithProdotto] = []


# ── Risposta prezzo calcolato ─────────────────

class PrezzoCalcolatoResponse(BaseModel):
    prodotto_id: int
    listino_id: int
    prezzo_base: float
    prezzo_override: Optional[float]
    sconto_percentuale: float
    prezzo_finale: float
    unita_misura: str


# ═══════════════════════════════════════════════
# BLOCCO 4 — Preventivi + Ordini
# ═══════════════════════════════════════════════

from typing import Literal
from datetime import date

STATI_PREVENTIVO = Literal['bozza', 'inviato', 'accettato', 'rifiutato']
STATI_ORDINE = Literal['in_lavorazione', 'completato', 'annullato']

# ── PreventivoRiga ────────────────────────────

class PreventivoRigaCreate(BaseModel):
    prodotto_id: Optional[int] = None
    descrizione_custom: Optional[str] = None
    quantita: float = Field(1.0, gt=0)
    prezzo_unitario: float = Field(0.0, ge=0)
    sconto_percentuale: float = Field(0.0, ge=0, le=100)
    ordine: int = 0

    @field_validator('descrizione_custom', 'prodotto_id', mode='before')
    @classmethod
    def at_least_one_description(cls, v):
        return v


class PreventivoRigaUpdate(BaseModel):
    descrizione_custom: Optional[str] = None
    quantita: Optional[float] = Field(None, gt=0)
    prezzo_unitario: Optional[float] = Field(None, ge=0)
    sconto_percentuale: Optional[float] = Field(None, ge=0, le=100)
    ordine: Optional[int] = None


class PreventivoRigaRead(BaseModel):
    id: int
    preventivo_id: int
    prodotto_id: Optional[int] = None
    descrizione_custom: Optional[str] = None
    quantita: float
    prezzo_unitario: float
    sconto_percentuale: float
    importo: float
    ordine: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    prodotto: Optional['Prodotto'] = None

    model_config = ConfigDict(from_attributes=True)


# ── Preventivo ────────────────────────────────

class PreventivoCreate(BaseModel):
    azienda_cliente_id: Optional[int] = None
    listino_id: Optional[int] = None
    consulente_id: Optional[int] = None
    oggetto: Optional[str] = None
    data_scadenza: Optional[date] = None
    note: Optional[str] = None
    righe: List[PreventivoRigaCreate] = []


class PreventivoUpdate(BaseModel):
    azienda_cliente_id: Optional[int] = None
    listino_id: Optional[int] = None
    consulente_id: Optional[int] = None
    oggetto: Optional[str] = None
    data_scadenza: Optional[date] = None
    note: Optional[str] = None
    attivo: Optional[bool] = None


class PreventivoRead(BaseModel):
    id: int
    numero: str
    anno: int
    numero_progressivo: int
    azienda_cliente_id: Optional[int] = None
    listino_id: Optional[int] = None
    consulente_id: Optional[int] = None
    stato: str
    oggetto: Optional[str] = None
    data_scadenza: Optional[datetime] = None
    note: Optional[str] = None
    attivo: bool
    totale: float = 0.0
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class PreventivoWithRighe(PreventivoRead):
    righe: List[PreventivoRigaRead] = []
    azienda_cliente: Optional['AziendaCliente'] = None
    consulente: Optional['Consulente'] = None


# ── Ordine ────────────────────────────────────

class OrdineRead(BaseModel):
    id: int
    numero: str
    anno: int
    numero_progressivo: int
    preventivo_id: Optional[int] = None
    azienda_cliente_id: Optional[int] = None
    stato: str
    note: Optional[str] = None
    progetto_id: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    azienda_cliente: Optional['AziendaCliente'] = None
    preventivo: Optional[PreventivoRead] = None

    model_config = ConfigDict(from_attributes=True)


class OrdineUpdate(BaseModel):
    stato: Optional[STATI_ORDINE] = None
    note: Optional[str] = None
    progetto_id: Optional[int] = None


# ── Piano Finanziario ─────────────────────────

from typing import Literal

TIPO_FONDO = Literal['formazienda', 'fapi', 'fondimpresa', 'fse', 'altro']
STATO_PIANO = Literal['bozza', 'inviato', 'approvato', 'in_corso', 'completato', 'rendicontato', 'chiuso', 'respinto']
STATO_AVVISO_PIANO = Literal['bozza', 'aperto', 'chiuso', 'rendicontato']
STATO_VOCE_PIANO = Literal['previsto', 'in_corso', 'rendicontato', 'validato']
CATEGORIA_VOCE = Literal['docenza', 'tutoraggio', 'coordinamento', 'progettazione', 'materiali', 'materiali_didattici', 'aula', 'viaggi', 'attrezzature', 'certificazioni', 'altro']


class TemplatePianoFinanziarioBase(BaseModel):
    codice: str = Field(..., max_length=50)
    nome: str = Field(..., max_length=200)
    tipo_fondo: TIPO_FONDO
    versione: Optional[str] = "1.0"
    descrizione: Optional[str] = None
    note_compilazione: Optional[str] = None
    categorie_spesa: Optional[str] = None
    percentuale_max_docenza: Optional[float] = 100.0
    percentuale_max_coordinamento: Optional[float] = 15.0
    percentuale_max_materiali: Optional[float] = 20.0
    ore_minime_corso: Optional[int] = 8
    ore_massime_corso: Optional[int] = 200
    is_active: Optional[bool] = True


class TemplatePianoFinanziarioCreate(TemplatePianoFinanziarioBase):
    pass


class TemplatePianoFinanziarioUpdate(BaseModel):
    nome: Optional[str] = None
    descrizione: Optional[str] = None
    note_compilazione: Optional[str] = None
    categorie_spesa: Optional[str] = None
    percentuale_max_docenza: Optional[float] = None
    percentuale_max_coordinamento: Optional[float] = None
    percentuale_max_materiali: Optional[float] = None
    ore_minime_corso: Optional[int] = None
    ore_massime_corso: Optional[int] = None
    is_active: Optional[bool] = None


class TemplatePianoFinanziario(TemplatePianoFinanziarioBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class AvvisoPianoFinanziarioBase(BaseModel):
    template_id: int
    codice_avviso: str = Field(..., max_length=100)
    titolo: str = Field(..., max_length=300)
    descrizione: Optional[str] = None
    data_apertura: datetime
    data_chiusura: datetime
    data_rendicontazione: Optional[datetime] = None
    budget_totale_avviso: Optional[float] = None
    budget_max_progetto: Optional[float] = None
    budget_min_progetto: Optional[float] = None
    ore_minime: Optional[int] = None
    ore_massime: Optional[int] = None
    partecipanti_min: Optional[int] = None
    partecipanti_max: Optional[int] = None
    costo_ora_formazione_max: Optional[float] = None
    costo_ora_docenza_max: Optional[float] = None
    costo_ora_tutoraggio_max: Optional[float] = None
    costo_ora_coordinamento_max: Optional[float] = None
    documenti_richiesti: Optional[str] = None
    stato: Optional[STATO_AVVISO_PIANO] = "aperto"
    is_active: Optional[bool] = True


class AvvisoPianoFinanziarioCreate(AvvisoPianoFinanziarioBase):
    pass


class AvvisoPianoFinanziarioUpdate(BaseModel):
    titolo: Optional[str] = None
    descrizione: Optional[str] = None
    data_apertura: Optional[datetime] = None
    data_chiusura: Optional[datetime] = None
    data_rendicontazione: Optional[datetime] = None
    budget_totale_avviso: Optional[float] = None
    budget_max_progetto: Optional[float] = None
    budget_min_progetto: Optional[float] = None
    ore_minime: Optional[int] = None
    ore_massime: Optional[int] = None
    partecipanti_min: Optional[int] = None
    partecipanti_max: Optional[int] = None
    costo_ora_formazione_max: Optional[float] = None
    costo_ora_docenza_max: Optional[float] = None
    costo_ora_tutoraggio_max: Optional[float] = None
    costo_ora_coordinamento_max: Optional[float] = None
    documenti_richiesti: Optional[str] = None
    stato: Optional[STATO_AVVISO_PIANO] = None
    is_active: Optional[bool] = None


class AvvisoPianoFinanziario(AvvisoPianoFinanziarioBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class VocePianoFinanziarioBase(BaseModel):
    piano_id: int
    categoria: Optional[CATEGORIA_VOCE] = None
    sottocategoria: Optional[str] = None
    descrizione: Optional[str] = None
    mansione_riferimento: Optional[str] = None
    assignment_id: Optional[int] = None
    importo_preventivo: float = Field(default=0.0, ge=0)
    importo_approvato: float = Field(default=0.0, ge=0)
    importo_consuntivo: float = Field(default=0.0, ge=0)
    importo_validato: float = Field(default=0.0, ge=0)
    collaborator_id: Optional[int] = None
    ore_previste: float = Field(default=0.0, ge=0)
    ore_effettive: float = Field(default=0.0, ge=0)
    tariffa_oraria: float = Field(default=0.0, ge=0)
    stato: STATO_VOCE_PIANO = 'previsto'
    note: Optional[str] = None


class VocePianoFinanziarioCreate(VocePianoFinanziarioBase):
    pass


class VocePianoFinanziarioUpdate(BaseModel):
    categoria: Optional[CATEGORIA_VOCE] = None
    sottocategoria: Optional[str] = None
    descrizione: Optional[str] = None
    mansione_riferimento: Optional[str] = None
    assignment_id: Optional[int] = None
    importo_preventivo: Optional[float] = Field(default=None, ge=0)
    importo_approvato: Optional[float] = Field(default=None, ge=0)
    importo_consuntivo: Optional[float] = Field(default=None, ge=0)
    importo_validato: Optional[float] = Field(default=None, ge=0)
    collaborator_id: Optional[int] = None
    ore_previste: Optional[float] = Field(default=None, ge=0)
    ore_effettive: Optional[float] = Field(default=None, ge=0)
    tariffa_oraria: Optional[float] = Field(default=None, ge=0)
    stato: Optional[STATO_VOCE_PIANO] = None
    note: Optional[str] = None


class VocePianoFinanziario(VocePianoFinanziarioBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @computed_field
    @property
    def importo_previsto(self) -> float:
        return self.importo_preventivo

    @computed_field
    @property
    def importo_rendicontato(self) -> float:
        return self.importo_consuntivo

    @computed_field
    @property
    def importo_rimanente(self) -> float:
        return self.importo_preventivo - self.importo_consuntivo

    @computed_field
    @property
    def percentuale_utilizzo(self) -> float:
        if not self.importo_preventivo:
            return 0.0
        return (self.importo_consuntivo / self.importo_preventivo) * 100

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class PianoFinanziarioBase(BaseModel):
    progetto_id: int
    template_id: Optional[int] = None
    avviso_id: Optional[int] = None
    nome: str = Field(max_length=200)
    tipo_fondo: TIPO_FONDO
    budget_totale: float = Field(ge=0)
    budget_approvato: float = Field(default=0.0, ge=0)
    budget_utilizzato: float = Field(default=0.0, ge=0)
    budget_rimanente: float = Field(default=0.0, ge=0)
    data_inizio: datetime
    data_fine: datetime
    data_approvazione: Optional[datetime] = None
    data_rendicontazione: Optional[datetime] = None
    stato: STATO_PIANO = 'bozza'
    note: Optional[str] = None
    note_ente: Optional[str] = None

    @field_validator('data_fine')
    @classmethod
    def data_fine_dopo_inizio(cls, v: datetime, info) -> datetime:
        data_inizio = info.data.get('data_inizio')
        if data_inizio and v < data_inizio:
            raise ValueError('data_fine deve essere successiva a data_inizio')
        return v


class PianoFinanziarioCreate(PianoFinanziarioBase):
    pass


class PianoFinanziarioUpdate(BaseModel):
    template_id: Optional[int] = None
    avviso_id: Optional[int] = None
    nome: Optional[str] = Field(default=None, max_length=200)
    tipo_fondo: Optional[TIPO_FONDO] = None
    budget_totale: Optional[float] = Field(default=None, ge=0)
    budget_approvato: Optional[float] = Field(default=None, ge=0)
    budget_utilizzato: Optional[float] = Field(default=None, ge=0)
    budget_rimanente: Optional[float] = Field(default=None, ge=0)
    data_inizio: Optional[datetime] = None
    data_fine: Optional[datetime] = None
    data_approvazione: Optional[datetime] = None
    data_rendicontazione: Optional[datetime] = None
    stato: Optional[STATO_PIANO] = None
    note: Optional[str] = None
    note_ente: Optional[str] = None


class PianoFinanziario(PianoFinanziarioBase):
    id: int
    codice_piano: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class PianoFinanziarioWithVoci(PianoFinanziario):
    voci: List[VocePianoFinanziario] = []
