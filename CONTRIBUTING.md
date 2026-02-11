# 🤝 Contributing to Gestionale Collaboratori

Grazie per il tuo interesse nel contribuire al progetto! Questa guida ti aiuterà a iniziare.

## 📋 Indice

- [Code of Conduct](#code-of-conduct)
- [Come Contribuire](#come-contribuire)
- [Setup Ambiente Sviluppo](#setup-ambiente-sviluppo)
- [Workflow Git](#workflow-git)
- [Standard di Codifica](#standard-di-codifica)
- [Testing](#testing)
- [Pull Request](#pull-request)

---

## 📜 Code of Conduct

Questo progetto adotta un codice di condotta basato sul rispetto reciproco:

- ✅ Sii rispettoso e costruttivo
- ✅ Accetta feedback e critiche costruttive
- ✅ Concentrati su ciò che è meglio per il progetto
- ❌ NO linguaggio offensivo o discriminatorio
- ❌ NO attacchi personali

---

## 🚀 Come Contribuire

Ci sono molti modi per contribuire:

### 1. Segnalare Bug 🐛
- Usa GitHub Issues
- Descrivi chiaramente il problema
- Fornisci passi per riprodurre
- Includi screenshot se utili

### 2. Proporre Nuove Funzionalità 💡
- Apri una Issue di tipo "Feature Request"
- Spiega il caso d'uso
- Discuti l'implementazione

### 3. Scrivere Codice 💻
- Risolvi issue esistenti
- Migliora la documentazione
- Scrivi test
- Ottimizza performance

### 4. Migliorare Documentazione 📝
- README
- Commenti nel codice (in italiano!)
- Guide utente
- API documentation

---

## 🛠️ Setup Ambiente Sviluppo

### Prerequisiti

- **Python 3.11+**
- **Node.js 18+** (per frontend)
- **Docker** e **Docker Compose** (opzionale)
- **Git**
- **PostgreSQL** (o usa Docker)

### Step Iniziali

1. **Fork del repository**
   ```bash
   # Clicca "Fork" su GitHub
   git clone https://github.com/TUO-USERNAME/pythonpro.git
   cd pythonpro
   ```

2. **Setup completo con Make**
   ```bash
   make setup
   ```

   Questo comando:
   - Crea virtual environment
   - Installa tutte le dipendenze
   - Crea directory necessarie
   - Genera file .env da template

3. **Configurazione .env**
   ```bash
   cp .env.example .env
   # Modifica .env con le tue configurazioni
   ```

4. **Avvia database (Docker)**
   ```bash
   docker-compose up -d db redis
   ```

5. **Applica migrazioni**
   ```bash
   make migrate
   ```

6. **Avvia server sviluppo**
   ```bash
   make dev
   ```

7. **Verifica setup**
   ```bash
   make health
   ```

---

## 🔀 Workflow Git

### Branch Strategy

- `main` → Produzione (protetto)
- `develop` → Sviluppo attivo
- `feature/nome-feature` → Nuove funzionalità
- `fix/nome-bug` → Bug fix
- `docs/nome-doc` → Documentazione

### Workflow Consigliato

1. **Crea branch da develop**
   ```bash
   git checkout develop
   git pull origin develop
   git checkout -b feature/mia-nuova-feature
   ```

2. **Lavora sul tuo branch**
   ```bash
   # Fai modifiche
   git add .
   git commit -m "feat: descrizione breve della feature"
   ```

3. **Mantieni il branch aggiornato**
   ```bash
   git fetch origin
   git rebase origin/develop
   ```

4. **Push del branch**
   ```bash
   git push origin feature/mia-nuova-feature
   ```

5. **Apri Pull Request**
   - Su GitHub, apri PR verso `develop`
   - Compila il template
   - Richiedi review

### Commit Messages

Usa [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>: <description>

[optional body]

[optional footer]
```

**Types:**
- `feat`: Nuova funzionalità
- `fix`: Bug fix
- `docs`: Documentazione
- `style`: Formattazione codice
- `refactor`: Refactoring
- `test`: Aggiunta test
- `chore`: Manutenzione

**Esempi:**
```
feat: add collaborator search by fiscal code
fix: correct attendance overlap validation
docs: update API endpoints documentation
test: add unit tests for assignment creation
```

---

## 💻 Standard di Codifica

### Python Backend

#### 1. **Commenti in Italiano** 📝
Tutti i commenti devono essere in italiano, chiari e adatti a principianti:

```python
# ❌ SBAGLIATO
def calc(x, y):
    return x * y

# ✅ CORRETTO
def calcola_costo_totale(ore_lavorate: float, tariffa_oraria: float) -> float:
    """
    Calcola il costo totale moltiplicando ore per tariffa.

    Questa funzione è usata per determinare l'importo da pagare
    a un collaboratore in base alle ore effettivamente lavorate.

    Args:
        ore_lavorate: Numero di ore registrate nelle presenze
        tariffa_oraria: Costo orario del collaboratore in euro

    Returns:
        Il costo totale in euro (ore * tariffa)

    Example:
        >>> calcola_costo_totale(10.5, 25.0)
        262.5
    """
    return ore_lavorate * tariffa_oraria
```

#### 2. **Type Hints** 🔬
Usa sempre type hints completi:

```python
from typing import List, Optional, Dict
from datetime import datetime

def get_attendances(
    db: Session,
    collaborator_id: Optional[int] = None,
    start_date: Optional[datetime] = None
) -> List[Attendance]:
    ...
```

#### 3. **Code Style** ✨
- Usa **Ruff** per linting
- Max line length: **100 caratteri**
- Usa **double quotes** per stringhe
- Segui **PEP 8**

Verifica codice:
```bash
make lint
make format
make typecheck
```

#### 4. **Naming Conventions** 📛
- Variabili/funzioni: `snake_case`
- Classi: `PascalCase`
- Costanti: `UPPER_SNAKE_CASE`
- Privati: `_leading_underscore`

```python
# Costanti
MAX_UPLOAD_SIZE_MB = 10
DEFAULT_TIMEOUT = 30

# Classi
class CollaboratorRepository:
    pass

# Funzioni/variabili
def create_attendance(attendance_data: dict) -> Attendance:
    collaborator_id = attendance_data.get("collaborator_id")
    _internal_cache = {}  # privato
```

---

## 🧪 Testing

### Scrivi Test per Ogni Funzionalità

```python
# tests/test_attendance.py
import pytest
from app.services.attendance import create_attendance

def test_create_attendance_success(db_session, mock_collaborator):
    """
    Test: creazione presenza con dati validi.

    Verifica che una presenza venga creata correttamente
    quando vengono forniti tutti i dati obbligatori.
    """
    data = {
        "collaborator_id": mock_collaborator.id,
        "project_id": 1,
        "date": "2025-01-15",
        "hours": 8.0
    }

    attendance = create_attendance(db_session, data)

    assert attendance.id is not None
    assert attendance.hours == 8.0
    assert attendance.collaborator_id == mock_collaborator.id
```

### Esegui Test

```bash
# Test rapidi
make test

# Test con coverage
make coverage

# Test paralleli (veloci)
make test-fast
```

### Coverage Minima: 85%

Tutti i moduli core devono avere coverage ≥ 85%.

---

## 📬 Pull Request

### Checklist Prima di Aprire PR

- [ ] Codice formattato (`make format`)
- [ ] Lint passa (`make lint`)
- [ ] Type check passa (`make typecheck`)
- [ ] Test passano (`make test`)
- [ ] Coverage ≥ 85% (`make coverage`)
- [ ] Security scan OK (`make security`)
- [ ] Commenti in italiano
- [ ] Documentazione aggiornata
- [ ] CHANGELOG aggiornato
- [ ] Commit messages seguono Conventional Commits

### Template PR

Quando apri una PR, compila il template:

```markdown
## Descrizione
Breve descrizione della modifica

## Tipo di Cambiamento
- [ ] Bug fix
- [ ] Nuova feature
- [ ] Breaking change
- [ ] Documentazione

## Testing
Come è stato testato?

## Checklist
- [ ] Codice formattato
- [ ] Test aggiunti/aggiornati
- [ ] Documentazione aggiornata
- [ ] Security check passato
```

### Review Process

1. Almeno 1 approvazione richiesta
2. CI deve essere verde (tutti check passano)
3. No conflitti con branch di destinazione
4. Codice review costruttivo

---

## 🔒 Sicurezza

### Riporta Vulnerabilità

Se trovi una vulnerabilità di sicurezza:

1. **NON aprire issue pubbliche**
2. Contatta i maintainer privatamente
3. Fornisci dettagli e passi per riprodurre
4. Attendi fix prima di divulgare pubblicamente

### Best Practices

- ❌ NO secret hardcodati nel codice
- ❌ NO password nei commit
- ❌ NO dati sensibili nei log
- ✅ Usa variabili d'ambiente (.env)
- ✅ Valida sempre input utente
- ✅ Sanitizza output
- ✅ Usa HTTPS in produzione

---

## 📚 Risorse Utili

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Pytest Documentation](https://docs.pytest.org/)
- [Python Type Hints](https://docs.python.org/3/library/typing.html)

---

## 💬 Domande?

- Apri una Issue di tipo "Question"
- Contatta i maintainer
- Consulta la documentazione esistente

---

**Grazie per contribuire! 🎉**
