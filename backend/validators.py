# Sistema di validazione avanzato per input sanitization
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, date
from pydantic import BaseModel, validator, Field
import re
import html
from email_validator import validate_email, EmailNotValidError
import logging

logger = logging.getLogger(__name__)

class InputSanitizer:
    """Classe per sanitizzazione input utente"""

    @staticmethod
    def sanitize_string(value: str, max_length: int = 255, allow_html: bool = False) -> str:
        """Sanitizza stringhe rimuovendo caratteri pericolosi"""
        if not value:
            return ""

        # Rimuovi spazi iniziali e finali
        value = value.strip()

        # Limita lunghezza
        if len(value) > max_length:
            value = value[:max_length]

        # Rimuovi o escape HTML se non permesso
        if not allow_html:
            value = html.escape(value)

        # Rimuovi caratteri di controllo pericolosi
        value = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]', '', value)

        # Rimuovi script injection
        dangerous_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'vbscript:',
            r'onload=',
            r'onerror=',
            r'onclick='
        ]

        for pattern in dangerous_patterns:
            value = re.sub(pattern, '', value, flags=re.IGNORECASE)

        return value

    @staticmethod
    def sanitize_email(email: str) -> str:
        """Valida e sanitizza email"""
        try:
            email = email.strip().lower()
            valid = validate_email(email)
            return valid.email
        except EmailNotValidError:
            raise ValueError("Email non valida")

    @staticmethod
    def sanitize_phone(phone: str) -> str:
        """Sanitizza numero di telefono"""
        if not phone:
            return ""

        # Rimuovi tutto tranne numeri, +, spazi e trattini
        phone = re.sub(r'[^\d\+\-\s\(\)]', '', phone.strip())

        # Verifica formato basilare
        if not re.match(r'^[\+]?[\d\s\-\(\)]{8,20}$', phone):
            raise ValueError("Formato telefono non valido")

        return phone

    @staticmethod
    def sanitize_fiscal_code(fiscal_code: str) -> str:
        """Valida e sanitizza codice fiscale italiano"""
        if not fiscal_code:
            return ""

        fiscal_code = fiscal_code.strip().upper()

        # Verifica formato codice fiscale italiano
        if not re.match(r'^[A-Z]{6}[0-9]{2}[A-Z][0-9]{2}[A-Z][0-9]{3}[A-Z]$', fiscal_code):
            raise ValueError("Formato codice fiscale non valido")

        return fiscal_code

class BusinessValidator:
    """Validazioni di logica business"""

    @staticmethod
    def validate_date_range(start_date: datetime, end_date: datetime) -> bool:
        """Valida range di date"""
        if start_date >= end_date:
            raise ValueError("La data di inizio deve essere precedente alla data di fine")

        # Verifica date non troppo nel futuro (max 10 anni)
        from datetime import timedelta
        max_future = datetime.now() + timedelta(days=3650)
        if start_date > max_future or end_date > max_future:
            raise ValueError("Le date non possono essere oltre 10 anni nel futuro")

        return True

    @staticmethod
    def validate_work_hours(hours: float) -> bool:
        """Valida ore di lavoro"""
        if hours < 0:
            raise ValueError("Le ore non possono essere negative")

        if hours > 24:
            raise ValueError("Le ore non possono superare 24 in un giorno")

        if hours > 12:
            logger.warning(f"Ore lavorate superiori a 12: {hours}")

        return True

    @staticmethod
    def validate_hourly_rate(rate: float) -> bool:
        """Valida tariffa oraria"""
        if rate < 0:
            raise ValueError("La tariffa oraria non può essere negativa")

        if rate > 1000:
            logger.warning(f"Tariffa oraria molto alta: {rate}")

        return True

    @staticmethod
    def validate_project_status(status: str) -> bool:
        """Valida stato progetto"""
        valid_statuses = ['active', 'completed', 'paused', 'cancelled']
        if status not in valid_statuses:
            raise ValueError(f"Status deve essere uno di: {valid_statuses}")
        return True

# Schemi Pydantic potenziati con validazione
class EnhancedCollaboratorCreate(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=50)
    last_name: str = Field(..., min_length=1, max_length=50)
    email: str = Field(..., max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    position: Optional[str] = Field(None, max_length=100)
    birthplace: Optional[str] = Field(None, max_length=100)
    birth_date: Optional[datetime] = None
    gender: Optional[str] = Field(None, pattern=r'^(M|F|Altro)$')
    fiscal_code: Optional[str] = Field(None, max_length=16)
    city: Optional[str] = Field(None, max_length=100)
    address: Optional[str] = Field(None, max_length=200)
    education: Optional[str] = Field(None, max_length=50)

    @validator('first_name', 'last_name')
    def validate_names(cls, v):
        if not v or not v.strip():
            raise ValueError('Nome e cognome sono obbligatori')
        v = InputSanitizer.sanitize_string(v, 50)
        if not re.match(r'^[a-zA-ZÀ-ÿ\s\-\'\.]+$', v):
            raise ValueError('Nome può contenere solo lettere, spazi, apostrofi e trattini')
        return v

    @validator('email')
    def validate_email_field(cls, v):
        return InputSanitizer.sanitize_email(v)

    @validator('phone')
    def validate_phone_field(cls, v):
        if v:
            return InputSanitizer.sanitize_phone(v)
        return v

    @validator('fiscal_code')
    def validate_fiscal_code_field(cls, v):
        if v:
            return InputSanitizer.sanitize_fiscal_code(v)
        return v

    @validator('birth_date')
    def validate_birth_date_field(cls, v):
        if v:
            # Verifica età ragionevole (14-100 anni)
            today = datetime.now()
            age = (today - v).days / 365.25
            if age < 14 or age > 100:
                raise ValueError('Età deve essere tra 14 e 100 anni')
        return v

    @validator('position', 'birthplace', 'city', 'address', 'education')
    def validate_text_fields(cls, v):
        if v:
            return InputSanitizer.sanitize_string(v, 200)
        return v

class EnhancedProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    status: str = Field(default="active")
    cup: Optional[str] = Field(None, max_length=15)
    ente_erogatore: Optional[str] = Field(None, max_length=50)
    budget: Optional[float] = Field(None, ge=0)
    priority: Optional[int] = Field(default=1, ge=1, le=5)

    @validator('name')
    def validate_name(cls, v):
        v = InputSanitizer.sanitize_string(v, 100)
        if len(v.strip()) < 3:
            raise ValueError('Nome progetto deve essere almeno 3 caratteri')
        return v

    @validator('description')
    def validate_description(cls, v):
        if v:
            return InputSanitizer.sanitize_string(v, 1000, allow_html=False)
        return v

    @validator('status')
    def validate_status_field(cls, v):
        BusinessValidator.validate_project_status(v)
        return v

    @validator('end_date')
    def validate_dates(cls, v, values):
        if v and 'start_date' in values and values['start_date']:
            BusinessValidator.validate_date_range(values['start_date'], v)
        return v

    @validator('cup')
    def validate_cup_field(cls, v):
        if v:
            v = v.strip().upper()
            if not re.match(r'^[A-Z][0-9]{2}[A-Z][0-9]{2}[A-Z][0-9]{6}$', v):
                raise ValueError('Formato CUP non valido')
        return v

class EnhancedAttendanceCreate(BaseModel):
    collaborator_id: int = Field(..., gt=0)
    project_id: int = Field(..., gt=0)
    assignment_id: Optional[int] = Field(None, gt=0)
    date: datetime
    start_time: datetime
    end_time: datetime
    hours: Optional[float] = Field(None, ge=0, le=24)
    notes: Optional[str] = Field(None, max_length=500)
    overtime_hours: Optional[float] = Field(default=0.0, ge=0, le=12)
    break_time_minutes: Optional[int] = Field(default=0, ge=0, le=480)

    @validator('end_time')
    def validate_time_range(cls, v, values):
        if 'start_time' in values and values['start_time']:
            if v <= values['start_time']:
                raise ValueError('Ora di fine deve essere successiva all\'ora di inizio')

            # Calcola ore se non fornite
            duration = (v - values['start_time']).total_seconds() / 3600
            BusinessValidator.validate_work_hours(duration)

        return v

    @validator('date')
    def validate_attendance_date(cls, v):
        # Non permettere presenze future oltre 7 giorni
        from datetime import timedelta
        max_future = datetime.now() + timedelta(days=7)
        if v > max_future:
            raise ValueError('Non è possibile registrare presenze oltre 7 giorni nel futuro')

        # Non permettere presenze troppo vecchie (oltre 1 anno)
        min_past = datetime.now() - timedelta(days=365)
        if v < min_past:
            raise ValueError('Non è possibile registrare presenze oltre 1 anno nel passato')

        return v

    @validator('notes')
    def validate_notes_field(cls, v):
        if v:
            return InputSanitizer.sanitize_string(v, 500)
        return v

class EnhancedAssignmentCreate(BaseModel):
    collaborator_id: int = Field(..., gt=0)
    project_id: int = Field(..., gt=0)
    role: str = Field(..., min_length=1, max_length=50)
    assigned_hours: float = Field(..., gt=0, le=10000)
    start_date: datetime
    end_date: datetime
    hourly_rate: float = Field(..., ge=0, le=1000)

    @validator('role')
    def validate_role_field(cls, v):
        v = InputSanitizer.sanitize_string(v, 50)
        if len(v.strip()) < 2:
            raise ValueError('Ruolo deve essere almeno 2 caratteri')
        return v

    @validator('end_date')
    def validate_assignment_dates(cls, v, values):
        if 'start_date' in values and values['start_date']:
            BusinessValidator.validate_date_range(values['start_date'], v)
        return v

    @validator('hourly_rate')
    def validate_rate_field(cls, v):
        BusinessValidator.validate_hourly_rate(v)
        return v

    @validator('assigned_hours')
    def validate_hours_field(cls, v):
        if v > 2000:  # Max 2000 ore per assegnazione
            raise ValueError('Ore assegnate non possono superare 2000')
        return v

# Classe per validazione batch operations
class BatchOperationValidator:
    """Validatore per operazioni in batch"""

    @staticmethod
    def validate_batch_size(items: List[Any], max_size: int = 100) -> bool:
        """Valida dimensione batch"""
        if len(items) > max_size:
            raise ValueError(f"Batch troppo grande. Massimo {max_size} items")
        return True

    @staticmethod
    def validate_unique_ids(items: List[Dict], id_field: str = 'id') -> bool:
        """Valida unicità ID in batch"""
        ids = [item.get(id_field) for item in items if item.get(id_field)]
        if len(ids) != len(set(ids)):
            raise ValueError(f"ID duplicati trovati in {id_field}")
        return True