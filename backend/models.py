from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Table, Text, Float, Index, Boolean
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql import func
from sqlalchemy.ext.hybrid import hybrid_property
from database import Base
import re

# TABELLA DI ASSOCIAZIONE per la relazione many-to-many
# Un collaboratore può lavorare su più progetti e un progetto può avere più collaboratori
collaborator_project = Table(
    'collaborator_project',  # Nome della tabella di collegamento
    Base.metadata,
    # Colonna che punta al collaboratore
    Column('collaborator_id', Integer, ForeignKey('collaborators.id'), primary_key=True),
    # Colonna che punta al progetto
    Column('project_id', Integer, ForeignKey('projects.id'), primary_key=True)
)

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
    city = Column(String(100))
    address = Column(String(200))
    education = Column(String(50))

    # Campi per performance e sicurezza
    is_active = Column(Boolean, default=True, index=True)
    last_login = Column(DateTime)

    # Campi per documenti allegati
    documento_identita_filename = Column(String(255))  # Nome file originale
    documento_identita_path = Column(String(500))      # Path storage
    documento_identita_uploaded_at = Column(DateTime)  # Data upload

    curriculum_filename = Column(String(255))          # Nome file originale
    curriculum_path = Column(String(500))              # Path storage
    curriculum_uploaded_at = Column(DateTime)          # Data upload

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relazioni ottimizzate con lazy loading
    projects = relationship("Project", secondary=collaborator_project, back_populates="collaborators", lazy="select")
    attendances = relationship("Attendance", back_populates="collaborator", lazy="select")
    assignments = relationship("Assignment", back_populates="collaborator", lazy="select")

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

class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    description = Column(Text)
    start_date = Column(DateTime, index=True)
    end_date = Column(DateTime, index=True)
    status = Column(String(20), default="active", index=True)
    cup = Column(String(15), index=True)

    # DEPRECATO: Sostituito da ente_attuatore_id (FK)
    # Mantenuto per retrocompatibilità durante la migrazione
    ente_erogatore = Column(String(50), index=True)

    # FK verso ImplementingEntity (Ente Attuatore)
    ente_attuatore_id = Column(Integer, ForeignKey("implementing_entities.id"), nullable=True, index=True)

    # Campi per performance
    priority = Column(Integer, default=1, index=True)
    budget = Column(Float)
    is_active = Column(Boolean, default=True, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relazioni ottimizzate
    collaborators = relationship("Collaborator", secondary=collaborator_project, back_populates="projects", lazy="select")
    attendances = relationship("Attendance", back_populates="project", lazy="select")
    assignments = relationship("Assignment", back_populates="project", lazy="select")
    ente_attuatore = relationship("ImplementingEntity", back_populates="projects", lazy="select")

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
    hours = Column(Float, nullable=False, index=True)

    # Campi aggiuntivi per analisi
    notes = Column(Text)
    overtime_hours = Column(Float, default=0.0)
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

class Assignment(Base):
    __tablename__ = "assignments"

    id = Column(Integer, primary_key=True, index=True)

    # Chiavi esterne con constraint CASCADE
    collaborator_id = Column(Integer, ForeignKey("collaborators.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)

    # Informazioni dell'assegnazione
    role = Column(String(50), nullable=False, index=True)
    assigned_hours = Column(Float, nullable=False)
    start_date = Column(DateTime, nullable=False, index=True)
    end_date = Column(DateTime, nullable=False, index=True)
    hourly_rate = Column(Float, nullable=False)
    contract_type = Column(String(50), nullable=True, index=True)  # Tipo contratto: Professionale, Occasionale, Ordine di servizio, Contratto a progetto

    # Campi per tracking avanzato
    completed_hours = Column(Float, default=0.0)
    progress_percentage = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relazioni
    collaborator = relationship("Collaborator", back_populates="assignments")
    project = relationship("Project", back_populates="assignments")

    # Proprietà calcolate
    @hybrid_property
    def remaining_hours(self):
        return max(0, self.assigned_hours - self.completed_hours)

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
    ore_previste = Column(Float, nullable=False)  # Ore totali previste per la mansione
    ore_effettive = Column(Float, default=0.0)    # Ore effettivamente svolte (calcolate da presenze)

    # === DATI ECONOMICI ===
    tariffa_oraria = Column(Float)  # Tariffa oraria per questa mansione
    budget_totale = Column(Float)   # Budget totale (ore_previste * tariffa_oraria)

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
    - {{collaboratore_indirizzo}}, {{collaboratore_citta}}
    - {{progetto_nome}}, {{progetto_descrizione}}, {{progetto_cup}}
    - {{ente_ragione_sociale}}, {{ente_piva}}, {{ente_indirizzo_completo}}
    - {{ente_referente}}, {{ente_pec}}, {{ente_telefono}}
    - {{mansione}}, {{ore_previste}}, {{tariffa_oraria}}, {{compenso_totale}}
    - {{data_inizio}}, {{data_fine}}
    - {{data_oggi}}
    """
    __tablename__ = "contract_templates"

    id = Column(Integer, primary_key=True, index=True)

    # === IDENTIFICAZIONE TEMPLATE ===
    nome_template = Column(String(200), nullable=False, index=True)
    # Es: "Contratto Professionale Standard", "Ordine di Servizio Docenza"

    descrizione = Column(Text)
    # Descrizione del template e del suo utilizzo

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

    # === VALIDAZIONI ===

    @validates('tipo_contratto')
    def validate_tipo_contratto(self, key, tipo):
        """Valida il tipo di contratto"""
        tipi_validi = ['professionale', 'occasionale', 'ordine_servizio', 'contratto_progetto']
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
                '{{collaboratore_citta}}'
            ],
            'progetto': [
                '{{progetto_nome}}',
                '{{progetto_descrizione}}',
                '{{progetto_cup}}'
            ],
            'ente': [
                '{{ente_ragione_sociale}}',
                '{{ente_piva}}',
                '{{ente_indirizzo_completo}}',
                '{{ente_referente}}',
                '{{ente_pec}}',
                '{{ente_telefono}}'
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
                '{{data_oggi}}'
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
              sqlite_where=Column('is_default') == True),
    )