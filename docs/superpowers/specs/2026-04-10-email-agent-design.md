# Email Agent — Design Spec
_Data: 2026-04-10_

## Contesto

La piattaforma PythonPro ha già:
- `EmailSender` (`backend/services/email_sender.py`) — invio SMTP via Gmail
- `mail_recovery.py` + `llm.py` (`backend/ai_agents/`) — agenti LLM per bozze email
- `agent_communication_drafts` — tabella DB per le bozze
- LLM configurabile: Ollama o OpenClaw via env vars (`AI_AGENT_LLM_PROVIDER`)
- Template Jinja2 per email (`backend/templates/email/`)

Quello che manca è la **ricezione** email e il pipeline di document processing automatico.

---

## Obiettivo

Agente che:
1. Riceve email con allegati da collaboratori/allievi via Gmail IMAP
2. Analizza il documento con LLM (completo? corretto tipo? cosa manca?)
3. Se valido → salva nel profilo + notifica operatore
4. Se non valido → risponde automaticamente chiedendo integrazioni
5. Audit trail completo in DB

---

## Architettura

```
EmailInboxWorker (loop 5 min)
    │
    ├── IMAP connect (Gmail, app password)
    ├── fetch unread emails
    │
    └── per ogni email →
            InboxRouter
                ↓ trova collaboratore/allievo per sender email
            AttachmentHandler
                ↓ scarica allegato → uploads/
            DocumentProcessor (LLM)
                ├── valido → salva profilo + crea notifica operatore
                └── non valido → InboxReplyComposer → EmailSender → risposta automatica
            ↓
        salva record in email_inbox_items
```

Il worker è indipendente da ARQ — gira come thread/process separato avviato da `main.py` o come container separato in `docker-compose.yml`.

---

## Componenti

### 1. `EmailInboxWorker` (`backend/services/email_inbox_worker.py`)

Loop che si connette a Gmail IMAP (`imap.gmail.com:993`) ogni 5 minuti.

- Configurazione da env vars: `GMAIL_IMAP_USER`, `GMAIL_IMAP_APP_PASSWORD`, `INBOX_POLL_INTERVAL_SECONDS` (default 300)
- Seleziona cartella `INBOX`, filtra `UNSEEN`
- Per ogni email: chiama la pipeline, marca come letta (`\Seen`) solo a pipeline completata con successo
- Se la pipeline fallisce: lascia l'email unread + log error (verrà riprovata al ciclo successivo)
- Deduplication: controlla `email_inbox_items.message_id` prima di processare

### 2. `InboxRouter` (`backend/services/inbox_router.py`)

Abbina il mittente dell'email a un'entità nel DB.

- Cerca `sender_email` in `collaborators.email` e `allievi.email`
- Restituisce `(entity_type, entity_id)` o `None` se non trovato
- Se non trovato: email ignorata + log (no risposta automatica per evitare loop con spam)

### 3. `AttachmentHandler` (`backend/services/attachment_handler.py`)

Scarica e persiste gli allegati dell'email.

- Supporta tipi: PDF, JPG, PNG, DOCX (whitelist esplicita)
- Salva in `uploads/<entity_type>/<entity_id>/<timestamp>_<filename>`
- Usa il sistema `file_upload.py` esistente dove possibile
- Dimensione massima allegato: 10MB (configurabile via env `MAX_ATTACHMENT_MB`)
- Se nessun allegato: pipeline continua senza processing documento (solo salva record)

### 4. `DocumentProcessor` (`backend/ai_agents/document_processor.py`)

Analizza il documento con LLM.

- Estrae testo da PDF (via `pdfplumber`) o immagine (via `pytesseract` se disponibile), fallback su nome file e metadati
- Prompt LLM strutturato:
  ```
  Analizza questo documento allegato da [nome] per [tipo richiesto].
  Rispondi in JSON: {"valid": bool, "doc_type": str, "issues": [str], "extracted_data": {}}
  ```
- Usa `get_agent_llm_config()` da `llm.py` — stesso provider (Ollama/OpenClaw)
- Se LLM disabilitato o timeout: `valid=None` (indeterminato) → tratta come caso da revisione manuale
- Salva raw LLM output in `email_inbox_items.llm_result` per audit

### 5. `InboxReplyComposer` (`backend/services/inbox_reply_composer.py`)

Genera il testo della risposta automatica quando il documento non è valido.

- Estende il pattern di `mail_recovery.py`
- Input: `issues` list dal `DocumentProcessor` + nome destinatario
- Usa LLM per generare il corpo (con fallback deterministico come in `mail_recovery.py`)
- Template Jinja2: aggiunge `richiesta_integrazioni.html` + `.txt` in `backend/templates/email/`
- Reply via `EmailSender.send_email()` con `Reply-To` corretto

---

## Database

### Nuova tabella: `email_inbox_items`

Migration: `backend/alembic/versions/029_add_email_inbox_items.py`

```sql
CREATE TABLE email_inbox_items (
    id              SERIAL PRIMARY KEY,
    message_id      VARCHAR(500) UNIQUE NOT NULL,  -- RFC 2822 Message-ID header
    received_at     TIMESTAMP NOT NULL,
    sender_email    VARCHAR(255) NOT NULL,
    subject         VARCHAR(500),
    entity_type     VARCHAR(50),                   -- 'collaborator' | 'allievo' | NULL
    entity_id       INTEGER,
    attachment_path VARCHAR(1000),
    attachment_name VARCHAR(255),
    processing_status VARCHAR(50) NOT NULL,        -- 'pending' | 'valid' | 'invalid' | 'manual_review' | 'skipped' | 'error'
    llm_result      JSONB,
    reply_sent      BOOLEAN DEFAULT FALSE,
    reply_sent_at   TIMESTAMP,
    error_message   TEXT,
    created_at      TIMESTAMP DEFAULT NOW()
);
CREATE INDEX ix_email_inbox_items_message_id ON email_inbox_items(message_id);
CREATE INDEX ix_email_inbox_items_entity ON email_inbox_items(entity_type, entity_id);
CREATE INDEX ix_email_inbox_items_status ON email_inbox_items(processing_status);
```

---

## API Endpoints

Nuovo router: `backend/routers/email_inbox.py`

| Method | Path | Descrizione |
|--------|------|-------------|
| `GET` | `/api/v1/email-inbox/items` | Lista items (filtrabili per status, entity) |
| `GET` | `/api/v1/email-inbox/items/{id}` | Dettaglio singolo item |
| `POST` | `/api/v1/email-inbox/trigger-poll` | Triggera polling manuale (admin only) |
| `GET` | `/api/v1/email-inbox/status` | Stato worker: ultimo poll, errori recenti |

---

## Variabili d'ambiente

```env
# IMAP (ricezione)
GMAIL_IMAP_USER=noreply@example.com
GMAIL_IMAP_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
INBOX_POLL_INTERVAL_SECONDS=300
MAX_ATTACHMENT_MB=10

# SMTP (già esistente, usato anche per le risposte)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=noreply@example.com
SMTP_PASSWORD=xxxx-xxxx-xxxx-xxxx
SMTP_FROM=noreply@example.com
SMTP_TEST_MODE=false
```

Nota: `GMAIL_IMAP_USER` e `SMTP_USER` sono tipicamente lo stesso account Gmail.

---

## Error Handling

| Scenario | Comportamento |
|----------|---------------|
| IMAP connection fail | Retry al ciclo successivo, log warning |
| Allegato > 10MB | Skippato, record salvato con `status=skipped`, no risposta |
| Tipo file non supportato | Skippato con log |
| Mittente sconosciuto | Ignorato, no risposta (evita spam loop) |
| LLM timeout/error | `status=manual_review`, notifica operatore, nessuna risposta automatica |
| Email già processata (dup message_id) | Skip silenzioso |
| `pdfplumber`/`pytesseract` non installato | Fallback: passa solo nome file e metadata all'LLM |

---

## Testing

- **Unit** `InboxRouter`: mock DB, verifica match per collaboratore, allievo, sconosciuto
- **Unit** `DocumentProcessor`: mock LLM, verifica parsing JSON valido/invalido/malformato
- **Unit** `AttachmentHandler`: mock filesystem, verifica whitelist tipi, limite dimensione
- **Integration** `EmailInboxWorker`: mock IMAP (`imaplib` patchato), email sintetica con PDF allegato, verifica record in DB
- **Integration** risposta automatica: verifica che `EmailSender` venga chiamato solo per documenti non validi
- **Integration** fallback LLM down: verifica `status=manual_review` senza eccezioni

---

## Dipendenze Python da aggiungere

```
pdfplumber>=0.10        # estrazione testo da PDF
pytesseract>=0.3        # OCR immagini (opzionale, solo se tesseract installato nel container)
```

Aggiornare `backend/requirements.txt` e `backend/pyproject.toml`.

---

## Sequenza di sviluppo consigliata

1. Migration DB `029_add_email_inbox_items.py`
2. `AttachmentHandler` + test
3. `InboxRouter` + test
4. `DocumentProcessor` + test (con LLM mock)
5. `InboxReplyComposer` + template Jinja2 + test
6. `EmailInboxWorker` (orchestrazione) + integration test
7. Router API `email_inbox.py`
8. Config docker-compose per avvio worker
