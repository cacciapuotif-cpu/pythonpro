from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import List, Optional
from datetime import datetime

class CollaboratorBase(BaseModel):
    first_name: str = Field(...)
    last_name: str = Field(...)
    email: EmailStr
    fiscal_code: Optional[str] = Field(None)  # Codice fiscale opzionale - se fornito deve essere 16 caratteri, unico, normalizzato uppercase
    phone: Optional[str] = Field(None)
    position: Optional[str] = Field(None)
    birthplace: Optional[str] = Field(None)
    birth_date: Optional[datetime] = Field(None)
    gender: Optional[str] = Field(None)
    city: Optional[str] = Field(None)
    address: Optional[str] = Field(None)
    education: Optional[str] = Field(None)

class CollaboratorCreate(CollaboratorBase):
    pass

class CollaboratorUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    position: Optional[str] = None
    birthplace: Optional[str] = None
    birth_date: Optional[datetime] = None
    gender: Optional[str] = None
    fiscal_code: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    education: Optional[str] = None

class Collaborator(CollaboratorBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    documento_identita_filename: Optional[str] = Field(None)
    documento_identita_uploaded_at: Optional[datetime] = None
    curriculum_filename: Optional[str] = Field(None)
    curriculum_uploaded_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, use_enum_values=True)

class ProjectBase(BaseModel):
    name: str = Field(...)
    description: Optional[str] = Field(None)
    start_date: Optional[datetime] = Field(None)
    end_date: Optional[datetime] = Field(None)
    status: str = Field("active")
    cup: Optional[str] = None
    ente_erogatore: Optional[str] = None

class ProjectCreate(ProjectBase):
    pass

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    status: Optional[str] = None
    cup: Optional[str] = None
    ente_erogatore: Optional[str] = None

class Project(ProjectBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, use_enum_values=True)

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
    assigned_hours: float  # Ore assegnate
    start_date: datetime  # Inizio attività
    end_date: datetime  # Fine attività
    hourly_rate: float  # Importo orario
    contract_type: Optional[str] = None  # Tipo contratto: Professionale, Occasionale, Ordine di servizio, Contratto a progetto

class AssignmentCreate(AssignmentBase):
    pass

class AssignmentUpdate(BaseModel):
    role: Optional[str] = None
    assigned_hours: Optional[float] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    hourly_rate: Optional[float] = None
    contract_type: Optional[str] = None

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
    pass

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
# SCHEMI PER TEMPLATE CONTRATTI
# ========================================

class ContractTemplateBase(BaseModel):
    """Schema base per Template Contratto"""
    nome_template: str
    descrizione: Optional[str] = None
    tipo_contratto: str  # "professionale", "occasionale", "ordine_servizio", "contratto_progetto"
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
    is_default: bool = False
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

    # Template da usare (opzionale, altrimenti usa il default per tipo_contratto)
    template_id: Optional[int] = None
    tipo_contratto: Optional[str] = None  # Se template_id non fornito

    # Note aggiuntive opzionali
    note_personalizzate: Optional[str] = None