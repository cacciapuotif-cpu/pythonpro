import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  assignEmailInboxItem,
  downloadEmailInboxAttachment,
  createAgentCommunication,
  getAgentCommunications,
  getAgentsCatalog,
  getAgentLlmHealth,
  getAgentRuns,
  getAgentSuggestions,
  getEmailInboxItems,
  getAziendeClienti,
  getCollaborators,
  getProjects,
  rejectAgentSuggestion,
  runAgent,
  updateAgentCommunicationStatus,
  workflowAgentSuggestion,
} from '../services/apiService';
import './AgentsManager.css';

const ENTITY_TYPE_LABELS = {
  global: 'Globale',
  project: 'Progetto',
  collaborator: 'Collaboratore',
  azienda_cliente: 'Azienda cliente',
};

const STATUS_LABELS = {
  pending: 'Pending',
  waiting: 'Rimandata',
  approved: 'Approvata',
  accepted: 'Accettato',
  rejected: 'Rifiutato',
  sent: 'Inviata',
  followup_due: 'Sollecito',
  completed: 'Completata',
  draft: 'Bozza',
  failed: 'Fallita',
  running: 'In esecuzione',
};

const SEVERITY_LABELS = {
  low: 'Bassa',
  medium: 'Media',
  high: 'Alta',
  critical: 'Critica',
};

const SEVERITY_RANK = {
  low: 1,
  medium: 2,
  high: 3,
  critical: 4,
};

const AGENT_ICONS = {
  mail_recovery: '📧',
  data_quality: '🔍',
  document_processor: '📄',
};

const formatDateTime = (value) => {
  if (!value) return '—';
  try {
    return new Intl.DateTimeFormat('it-IT', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(value));
  } catch {
    return value;
  }
};

const parsePayload = (value) => {
  if (!value) return null;
  if (typeof value === 'object') return value;
  try { return JSON.parse(value); } catch { return value; }
};

function Avatar({ name }) {
  const letter = (name || '?')[0].toUpperCase();
  return <span className="am-avatar">{letter}</span>;
}

function MissingFields({ fields }) {
  if (!fields || fields.length === 0) return null;
  return (
    <div className="am-missing">
      <span className="am-missing-label">Mancante:</span>
      {fields.map((f) => <span key={f} className="am-missing-chip">{f}</span>)}
    </div>
  );
}

function EmailPreview({ subject, body, lines = 3 }) {
  if (!subject && !body) return null;
  const previewLines = (body || '').split('\n').filter((l) => l.trim()).slice(0, lines).join('\n');
  return (
    <div className="am-email-preview">
      {subject && <div className="am-email-subject">{subject}</div>}
      {previewLines && <div className="am-email-body">{previewLines}</div>}
    </div>
  );
}

function NoteInput({ id, value, onChange }) {
  return (
    <textarea
      className="am-note"
      rows="2"
      placeholder="Nota operatore (opzionale)…"
      value={value || ''}
      onChange={(e) => onChange(id, e.target.value)}
    />
  );
}

export default function AgentsManager({ currentUser }) {
  const [catalog, setCatalog] = useState([]);
  const [runs, setRuns] = useState([]);
  const [suggestions, setSuggestions] = useState([]);
  const [communications, setCommunications] = useState([]);
  const [emailInboxItems, setEmailInboxItems] = useState([]);
  const [llmHealth, setLlmHealth] = useState(null);
  const [projects, setProjects] = useState([]);
  const [collaborators, setCollaborators] = useState([]);
  const [aziende, setAziende] = useState([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [actionLoading, setActionLoading] = useState(null);
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);
  const [notesBySuggestion, setNotesBySuggestion] = useState({});
  const [inboxExpiryByItem, setInboxExpiryByItem] = useState({});
  const [activeTab, setActiveTab] = useState('inbox');
  const [runSelections, setRunSelections] = useState({});
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [draftForm, setDraftForm] = useState({
    agent_name: 'manual_test',
    recipient_type: 'collaborator',
    recipient_id: '',
    suggestion_id: '',
    recipient_email: '',
    recipient_name: '',
    subject: '',
    body: '',
  });

  // ── Derived lookup maps ────────────────────────────────────────────────────
  const collaboratorById = useMemo(() =>
    collaborators.reduce((acc, c) => {
      acc[c.id] = `${c.first_name || ''} ${c.last_name || ''}`.trim() || `#${c.id}`;
      return acc;
    }, {}),
  [collaborators]);

  const collaboratorEmailById = useMemo(() =>
    collaborators.reduce((acc, c) => { acc[c.id] = c.email; return acc; }, {}),
  [collaborators]);

  // ── Filtered views ─────────────────────────────────────────────────────────
  const pendingSuggestions = useMemo(() =>
    suggestions.filter((s) => s.status === 'pending' && !['data_quality', 'mail_recovery'].includes(s.agent_name)),
  [suggestions]);

  const pendingCommunications = useMemo(() =>
    communications.filter((c) => ['draft', 'approved', 'followup_due'].includes(c.status)),
  [communications]);

  const operatorQueue = useMemo(() => {
    const commsBySuggestion = communications.reduce((acc, item) => {
      if (!item.suggestion_id) return acc;
      acc[item.suggestion_id] = acc[item.suggestion_id] || [];
      acc[item.suggestion_id].push(item);
      return acc;
    }, {});

    return suggestions
      .filter((s) =>
        s.agent_name === 'mail_recovery'
        && s.entity_type === 'collaborator'
        && ['pending', 'waiting', 'approved', 'followup_due'].includes(s.status))
      .map((s) => ({ ...s, communications: commsBySuggestion[s.id] || [] }));
  }, [communications, suggestions]);

  const groupedOperatorQueue = useMemo(() => {
    const groups = new Map();

    operatorQueue.forEach((item) => {
      const payload = parsePayload(item.payload);
      const recipientName = payload?.recipient_name || collaboratorById[item.entity_id] || `Collaboratore #${item.entity_id}`;
      const recipientEmail = payload?.recipient_email || collaboratorEmailById[item.entity_id] || '—';
      const key = item.entity_id || `${recipientEmail}-${recipientName}`;
      const current = groups.get(key);

      if (!current) {
        groups.set(key, {
          key,
          entityId: item.entity_id,
          recipientName,
          recipientEmail,
          severity: item.severity,
          items: [item],
        });
        return;
      }

      current.items.push(item);
      if ((SEVERITY_RANK[item.severity] || 0) > (SEVERITY_RANK[current.severity] || 0)) {
        current.severity = item.severity;
      }
    });

    return Array.from(groups.values());
  }, [collaboratorById, collaboratorEmailById, operatorQueue]);

  const representedSuggestionIds = useMemo(() => new Set([
    ...operatorQueue.map((item) => item.id),
    ...pendingSuggestions.map((item) => item.id),
  ]), [operatorQueue, pendingSuggestions]);

  const standaloneCommunications = useMemo(() =>
    pendingCommunications.filter((item) => {
      if (item.agent_name === 'mail_recovery' && item.suggestion_id) {
        return false;
      }
      return !item.suggestion_id || !representedSuggestionIds.has(item.suggestion_id);
    }),
  [pendingCommunications, representedSuggestionIds]);

  const manualReviewItems = useMemo(() =>
    emailInboxItems.filter((item) => item.processing_status === 'manual_review' && item.attachment_path),
  [emailInboxItems]);

  const recentInboxItems = useMemo(() =>
    emailInboxItems.filter((item) => ['valid', 'manual_review', 'invalid'].includes(item.processing_status)),
  [emailInboxItems]);

  const inboxTotal = manualReviewItems.length + groupedOperatorQueue.length + pendingSuggestions.length + standaloneCommunications.length;

  // ── Data loading ───────────────────────────────────────────────────────────
  const loadReferenceData = useCallback(async () => {
    const [proj, collab, az] = await Promise.all([
      getProjects(0, 200),
      getCollaborators(0, 200),
      getAziendeClienti({ limit: 200 }),
    ]);
    setProjects(Array.isArray(proj) ? proj : []);
    setCollaborators(Array.isArray(collab) ? collab : []);
    setAziende(Array.isArray(az) ? az : (az?.items || []));
  }, []);

  const loadAgentData = useCallback(async () => {
    const [cat, runsData, sugg, comms, llm, inbox] = await Promise.all([
      getAgentsCatalog(),
      getAgentRuns({ limit: 50 }),
      getAgentSuggestions({ limit: 100 }),
      getAgentCommunications({ limit: 100 }),
      getAgentLlmHealth(),
      getEmailInboxItems({ limit: 50 }),
    ]);
    setCatalog(Array.isArray(cat) ? cat : []);
    setRuns(Array.isArray(runsData) ? runsData : []);
    setSuggestions(Array.isArray(sugg) ? sugg : []);
    setCommunications(Array.isArray(comms) ? comms : []);
    setLlmHealth(llm || null);
    setEmailInboxItems(Array.isArray(inbox?.items) ? inbox.items : []);
  }, []);

  const loadAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      await Promise.all([loadReferenceData(), loadAgentData()]);
    } catch (e) {
      setError(e?.response?.data?.detail || 'Errore nel caricamento.');
    } finally {
      setLoading(false);
    }
  }, [loadAgentData, loadReferenceData]);

  useEffect(() => { loadAll(); }, [loadAll]);

  const showToast = useCallback((text, kind = 'success') => {
    setMessage({ text, kind });
    setTimeout(() => setMessage(null), 4000);
  }, []);

  // ── Agent execution ────────────────────────────────────────────────────────
  const runAgentDirect = useCallback(async (agentName, entityType, entityId) => {
    if (!agentName) return;
    const normalizedEntityType = entityType && entityType !== 'global' ? entityType : null;
    const normalizedEntityId = normalizedEntityType && entityId ? Number(entityId) : null;
    setRunning(true);
    setError(null);
    try {
      await runAgent({
        agent_name: agentName,
        entity_type: normalizedEntityType,
        entity_id: normalizedEntityId,
        requested_by_user_id: currentUser?.id || null,
        input_payload: { limit: 25 },
      });
      await loadAgentData();
      setActiveTab('inbox');
      showToast('Analisi completata. Controlla le email proposte qui sotto.');
    } catch (e) {
      setError(e?.response?.data?.detail || 'Esecuzione non riuscita.');
    } finally {
      setRunning(false);
    }
  }, [currentUser?.id, loadAgentData, showToast]);

  // ── Review / workflow handlers ─────────────────────────────────────────────
  const handleNote = useCallback((id, value) => {
    setNotesBySuggestion((prev) => ({ ...prev, [id]: value }));
  }, []);

  const handleSuggestionReview = useCallback(async (id, action) => {
    setActionLoading(`suggestion-${id}-${action}`);
    setError(null);
    try {
      if (action === 'accept') {
        await workflowAgentSuggestion(id, {
          action: 'approve_email',
          notes: notesBySuggestion[id] || null,
          reviewed_by_user_id: currentUser?.id || null,
        });
      } else {
        await rejectAgentSuggestion(id, {
          action: 'rejected',
          notes: notesBySuggestion[id] || null,
          reviewed_by_user_id: currentUser?.id || null,
        });
      }
      await loadAgentData();
      showToast(action === 'accept' ? 'Richiesta inviata.' : 'Suggerimento rifiutato.');
    } catch (e) {
      setError(e?.response?.data?.detail || 'Aggiornamento non riuscito.');
    } finally {
      setActionLoading(null);
    }
  }, [currentUser?.id, loadAgentData, notesBySuggestion, showToast]);

  const handleCommunicationStatus = useCallback(async (id, status) => {
    setActionLoading(`comm-${id}-${status}`);
    setError(null);
    try {
      await updateAgentCommunicationStatus(id, {
        status,
        reviewed_by_user_id: currentUser?.id || null,
      });
      await loadAgentData();
      showToast(status === 'sent' ? 'Email segnata come inviata.' : 'Bozza aggiornata.');
    } catch (e) {
      setError(e?.response?.data?.detail || 'Aggiornamento non riuscito.');
    } finally {
      setActionLoading(null);
    }
  }, [currentUser?.id, loadAgentData, showToast]);

  const handleWorkflowAction = useCallback(async (id, action) => {
    setActionLoading(`wf-${id}-${action}`);
    setError(null);
    try {
      await workflowAgentSuggestion(id, {
        action,
        notes: notesBySuggestion[id] || null,
        reviewed_by_user_id: currentUser?.id || null,
      });
      await loadAgentData();
      showToast('Azione registrata.');
    } catch (e) {
      setError(e?.response?.data?.detail || 'Aggiornamento non riuscito.');
    } finally {
      setActionLoading(null);
    }
  }, [currentUser?.id, loadAgentData, notesBySuggestion, showToast]);

  const handleCreateDraft = useCallback(async () => {
    if (!draftForm.recipient_email.trim() || !draftForm.subject.trim() || !draftForm.body.trim()) {
      setError('Compila destinatario email, oggetto e corpo.');
      return;
    }
    setActionLoading('draft-create');
    setError(null);
    try {
      await createAgentCommunication({
        agent_name: draftForm.agent_name.trim() || 'manual_test',
        channel: 'email',
        recipient_type: draftForm.recipient_type,
        recipient_id: draftForm.recipient_id ? Number(draftForm.recipient_id) : null,
        recipient_email: draftForm.recipient_email.trim(),
        recipient_name: draftForm.recipient_name.trim() || null,
        subject: draftForm.subject.trim(),
        body: draftForm.body.trim(),
        status: 'draft',
        created_by_user_id: currentUser?.id || null,
        meta_payload: JSON.stringify({ source: 'manual_ui' }),
      });
      await loadAgentData();
      setDraftForm((p) => ({ ...p, recipient_email: '', recipient_name: '', subject: '', body: '' }));
      showToast('Bozza email creata.');
    } catch (e) {
      setError(e?.response?.data?.detail || 'Creazione non riuscita.');
    } finally {
      setActionLoading(null);
    }
  }, [currentUser?.id, draftForm, loadAgentData, showToast]);

  const handleInboxExpiryChange = useCallback((itemId, value) => {
    setInboxExpiryByItem((prev) => ({ ...prev, [itemId]: value }));
  }, []);

  const handleInboxAssignment = useCallback(async (itemId, docType) => {
    setActionLoading(`inbox-${itemId}-${docType}`);
    setError(null);
    try {
      await assignEmailInboxItem(itemId, {
        doc_type: docType,
        expiry_date: docType === 'documento_identita' ? (inboxExpiryByItem[itemId] || null) : null,
        reviewed_by_user_id: currentUser?.id || null,
      });
      await loadAgentData();
      showToast(docType === 'documento_identita' ? 'Documento identita assegnato al collaboratore.' : 'Curriculum assegnato al collaboratore.');
    } catch (e) {
      setError(e?.response?.data?.detail || 'Assegnazione documento non riuscita.');
    } finally {
      setActionLoading(null);
    }
  }, [currentUser?.id, inboxExpiryByItem, loadAgentData, showToast]);

  const handleInboxPreview = useCallback(async (itemId, attachmentName) => {
    const previewWindow = window.open('', '_blank');
    setActionLoading(`inbox-preview-${itemId}`);
    setError(null);
    try {
      const response = await downloadEmailInboxAttachment(itemId);
      const extension = (attachmentName || '').split('.').pop()?.toLowerCase();
      const fallbackType = extension === 'pdf'
        ? 'application/pdf'
        : ['jpg', 'jpeg'].includes(extension)
          ? 'image/jpeg'
          : extension === 'png'
            ? 'image/png'
            : 'application/octet-stream';
      const headerType = response.headers?.['content-type'];
      const contentType = !headerType || headerType === 'application/octet-stream'
        ? fallbackType
        : headerType;
      const url = window.URL.createObjectURL(new Blob([response.data], { type: contentType }));
      if (previewWindow) {
        previewWindow.location.href = url;
      } else {
        window.open(url, '_blank', 'noopener,noreferrer');
      }
      window.setTimeout(() => window.URL.revokeObjectURL(url), 60000);
    } catch (e) {
      if (previewWindow && !previewWindow.closed) previewWindow.close();
      setError(e?.response?.data?.detail || 'Anteprima allegato non riuscita.');
    } finally {
      setActionLoading(null);
    }
  }, []);

  const handleInboxDownload = useCallback(async (itemId, attachmentName) => {
    setActionLoading(`inbox-download-${itemId}`);
    setError(null);
    try {
      const response = await downloadEmailInboxAttachment(itemId);
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', attachmentName || `allegato_${itemId}`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      setError(e?.response?.data?.detail || 'Download allegato non riuscito.');
    } finally {
      setActionLoading(null);
    }
  }, []);

  // ── Helpers ────────────────────────────────────────────────────────────────
  const isLoading = (key) => actionLoading === key;
  const resolveEntityName = (entityType, entityId) => {
    if (!entityId) return null;
    if (entityType === 'collaborator') return collaboratorById[entityId] || `Collaboratore #${entityId}`;
    if (entityType === 'project') {
      const p = projects.find((x) => String(x.id) === String(entityId));
      return p?.name || `Progetto #${entityId}`;
    }
    if (entityType === 'azienda_cliente') {
      const a = aziende.find((x) => String(x.id) === String(entityId));
      return a?.ragione_sociale || `Azienda #${entityId}`;
    }
    return `ID ${entityId}`;
  };

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="am">

      {/* Top bar */}
      <div className="am-topbar">
        <div>
          <h2 className="am-title">Comunicazioni AI</h2>
          <p className="am-subtitle">Richieste documenti e comunicazioni automatiche verso collaboratori</p>
        </div>
        <div className="am-topbar-right">
          <div className={`am-llm-pill ${llmHealth?.reachable ? 'ok' : 'warn'}`}>
            <span className="am-llm-dot" />
            {llmHealth?.reachable ? `AI attiva · ${llmHealth.provider}` : 'AI non disponibile'}
          </div>
          <button className="am-btn-ghost" onClick={loadAll} disabled={loading}>
            {loading ? 'Aggiornamento…' : '↺ Aggiorna'}
          </button>
        </div>
      </div>

      {/* Feedback */}
      {message && (
        <div className={`am-toast am-toast-${message.kind}`}>{message.text}</div>
      )}
      {error && <div className="am-error">{error}</div>}

      {/* Tabs */}
      <div className="am-tabs">
        <button
          className={`am-tab ${activeTab === 'inbox' ? 'active' : ''}`}
          onClick={() => setActiveTab('inbox')}
        >
          Da gestire
          {inboxTotal > 0 && <span className="am-tab-badge">{inboxTotal}</span>}
        </button>
        <button
          className={`am-tab ${activeTab === 'run' ? 'active' : ''}`}
          onClick={() => setActiveTab('run')}
        >
          Esegui analisi
        </button>
        <button
          className={`am-tab ${activeTab === 'history' ? 'active' : ''}`}
          onClick={() => setActiveTab('history')}
        >
          Storico
        </button>
      </div>

      {/* ── TAB: INBOX ─────────────────────────────────────────────────────── */}
      {activeTab === 'inbox' && (
        <div className="am-tab-content">
          {loading ? (
            <div className="am-placeholder">Caricamento…</div>
          ) : inboxTotal === 0 ? (
            <div className="am-empty-state">
              <div className="am-empty-icon">✓</div>
              <h3>Nessuna azione in attesa</h3>
              <p>Tutti i collaboratori sono in regola, oppure non hai ancora eseguito un'analisi.</p>
              <button className="am-btn-primary" onClick={() => setActiveTab('run')}>
                Esegui nuova analisi
              </button>
            </div>
          ) : (
            <div className="am-inbox">

              {recentInboxItems.length > 0 && (
                <section className="am-group">
                  <h3 className="am-group-title">
                    <span className="am-group-dot dot-green" />
                    Documenti ricevuti via email
                    <span className="am-group-count">{recentInboxItems.length}</span>
                  </h3>
                  {recentInboxItems.map((item) => {
                    const entityName = resolveEntityName(item.entity_type, item.entity_id) || 'Mittente non associato';
                    const statusText = item.processing_status === 'valid'
                      ? 'Profilo aggiornato automaticamente'
                      : item.processing_status === 'manual_review'
                        ? 'Da revisionare'
                        : 'Documento non validato';
                    return (
                      <article key={`recent-${item.id}`} className="am-card">
                        <div className="am-card-header">
                          <div className="am-recipient">
                            <Avatar name={entityName} />
                            <div className="am-recipient-info">
                              <strong>{entityName}</strong>
                              <span className="am-email-addr">{item.sender_email}</span>
                            </div>
                          </div>
                          <span className={`am-badge status-${item.processing_status === 'valid' ? 'completed' : item.processing_status === 'invalid' ? 'failed' : 'pending'}`}>
                            {statusText}
                          </span>
                        </div>
                        <div className="am-meta">
                          Ricevuto {formatDateTime(item.received_at)}
                          {item.attachment_name ? ` · Allegato: ${item.attachment_name}` : ''}
                        </div>
                        {item.subject && (
                          <div className="am-email-preview">
                            <div className="am-email-subject">{item.subject}</div>
                          </div>
                        )}
                      </article>
                    );
                  })}
                </section>
              )}

              {/* Manual review inbox */}
              {manualReviewItems.length > 0 && (
                <section className="am-group">
                  <h3 className="am-group-title">
                    <span className="am-group-dot dot-blue" />
                    Documenti ricevuti da revisionare
                    <span className="am-group-count">{manualReviewItems.length}</span>
                  </h3>
                  {manualReviewItems.map((item) => {
                    const entityName = resolveEntityName(item.entity_type, item.entity_id) || 'Collaboratore non identificato';
                    const attachmentName = item.attachment_name || 'allegato senza nome';
                    return (
                      <article key={item.id} className="am-card">
                        <div className="am-card-header">
                          <div className="am-recipient">
                            <Avatar name={entityName} />
                            <div className="am-recipient-info">
                              <strong>{entityName}</strong>
                              <span className="am-email-addr">{item.sender_email}</span>
                            </div>
                          </div>
                          <div className="am-badges">
                            <span className="am-badge status-pending">Revisione manuale</span>
                          </div>
                        </div>

                        <div className="am-meta">
                          Ricevuto {formatDateTime(item.received_at)} · Allegato: {attachmentName}
                        </div>

                        {item.subject && (
                          <div className="am-email-preview">
                            <div className="am-email-subject">{item.subject}</div>
                          </div>
                        )}

                        <div className="am-note" style={{ marginTop: 12 }}>
                          <label className="am-note-label" htmlFor={`expiry-${item.id}`}>Scadenza documento identita (opzionale)</label>
                          <input
                            id={`expiry-${item.id}`}
                            type="date"
                            className="am-note-input"
                            value={inboxExpiryByItem[item.id] || ''}
                            onChange={(event) => handleInboxExpiryChange(item.id, event.target.value)}
                          />
                        </div>

                        <div className="am-actions">
                          <button
                            className="am-btn-ghost-sm"
                            onClick={() => handleInboxPreview(item.id, attachmentName)}
                            disabled={!!actionLoading}
                          >
                            {isLoading(`inbox-preview-${item.id}`) ? 'Apro…' : 'Anteprima'}
                          </button>
                          <button
                            className="am-btn-ghost-sm"
                            onClick={() => handleInboxDownload(item.id, attachmentName)}
                            disabled={!!actionLoading}
                          >
                            {isLoading(`inbox-download-${item.id}`) ? 'Scarico…' : 'Scarica'}
                          </button>
                          <button
                            className="am-btn-primary"
                            onClick={() => handleInboxAssignment(item.id, 'documento_identita')}
                            disabled={!!actionLoading}
                          >
                            {isLoading(`inbox-${item.id}-documento_identita`) ? 'Assegno…' : 'Assegna come documento identita'}
                          </button>
                          <button
                            className="am-btn-primary"
                            onClick={() => handleInboxAssignment(item.id, 'curriculum')}
                            disabled={!!actionLoading}
                          >
                            {isLoading(`inbox-${item.id}-curriculum`) ? 'Assegno…' : 'Assegna come curriculum'}
                          </button>
                        </div>
                      </article>
                    );
                  })}
                </section>
              )}

              {/* Operator queue */}
              {groupedOperatorQueue.length > 0 && (
                <section className="am-group">
                  <h3 className="am-group-title">
                    <span className="am-group-dot dot-orange" />
                    Collaboratori da contattare
                    <span className="am-group-count">{groupedOperatorQueue.length}</span>
                  </h3>
                  {groupedOperatorQueue.map((group) => (
                    <article key={group.key} className={`am-card severity-${group.severity}`}>
                      <div className="am-card-header">
                        <div className="am-recipient">
                          <Avatar name={group.recipientName} />
                          <div className="am-recipient-info">
                            <strong>{group.recipientName}</strong>
                            <span className="am-email-addr">{group.recipientEmail}</span>
                          </div>
                        </div>
                        <div className="am-badges">
                          <span className={`am-badge severity-${group.severity}`}>
                            {SEVERITY_LABELS[group.severity] || group.severity}
                          </span>
                          {group.items.length > 1 && (
                            <span className="am-badge status-pending">{group.items.length} richieste</span>
                          )}
                        </div>
                      </div>

                      {group.items.map((item) => {
                        const payload = parsePayload(item.payload);
                        const missingFields = Array.isArray(payload?.missing_fields) ? payload.missing_fields : [];
                        const emailComm = item.communications.find((c) => c.channel === 'email');
                        const isFollowup = item.status === 'followup_due';
                        const emailAction = isFollowup ? 'remind_email' : 'approve_email';

                        return (
                          <div key={item.id} className="am-subcard">
                            <div className="am-badges" style={{ marginBottom: '8px' }}>
                              <span className={`am-badge severity-${item.severity}`}>
                                {item.title}
                              </span>
                              {isFollowup && (
                                <span className="am-badge status-followup">Sollecito</span>
                              )}
                            </div>

                            <MissingFields fields={missingFields} />

                            {emailComm && (
                              <EmailPreview subject={emailComm.subject} body={emailComm.body} />
                            )}

                            <NoteInput id={item.id} value={notesBySuggestion[item.id]} onChange={handleNote} />

                            <div className="am-actions">
                              <button
                                className="am-btn-ghost-sm"
                                onClick={() => handleWorkflowAction(item.id, 'wait')}
                                disabled={!!actionLoading}
                              >
                                Rimanda
                              </button>
                              <button
                                className="am-btn-ghost-sm"
                                onClick={() => handleWorkflowAction(item.id, 'close')}
                                disabled={!!actionLoading}
                              >
                                Chiudi senza inviare
                              </button>
                              {emailComm && (
                                <button
                                  className="am-btn-primary"
                                  onClick={() => handleWorkflowAction(item.id, emailAction)}
                                  disabled={!!actionLoading}
                                >
                                  {isLoading(`wf-${item.id}-${emailAction}`)
                                    ? 'Invio…'
                                    : isFollowup ? '📧 Invia sollecito ora' : '📧 Invia richiesta ora'}
                                </button>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </article>
                  ))}
                </section>
              )}

              {/* Pending suggestions */}
              {pendingSuggestions.length > 0 && (
                <section className="am-group">
                  <h3 className="am-group-title">
                    <span className="am-group-dot dot-blue" />
                    Proposte generiche — da verificare
                    <span className="am-group-count">{pendingSuggestions.length}</span>
                  </h3>
                  {pendingSuggestions.map((item) => {
                    const payload = parsePayload(item.payload);
                    const missingFields = Array.isArray(payload?.missing_fields) ? payload.missing_fields : [];
                    const recipientName = payload?.recipient_name || collaboratorById[item.entity_id] || `Collaboratore #${item.entity_id}`;
                    const recipientEmail = payload?.recipient_email || collaboratorEmailById[item.entity_id] || '—';
                    const subject = payload?.subject || item.title || '';
                    const body = payload?.body || '';

                    return (
                      <article key={item.id} className={`am-card severity-${item.severity}`}>
                        <div className="am-card-header">
                          <div className="am-recipient">
                            <Avatar name={recipientName} />
                            <div className="am-recipient-info">
                              <strong>{recipientName}</strong>
                              <span className="am-email-addr">{recipientEmail}</span>
                            </div>
                          </div>
                          <span className={`am-badge severity-${item.severity}`}>
                            {SEVERITY_LABELS[item.severity] || item.severity}
                          </span>
                        </div>

                        <MissingFields fields={missingFields} />
                        <EmailPreview subject={subject} body={body} lines={4} />

                        <NoteInput id={item.id} value={notesBySuggestion[item.id]} onChange={handleNote} />

                        <div className="am-actions">
                          <button
                            className="am-btn-ghost-sm danger"
                            onClick={() => handleWorkflowAction(item.id, 'close')}
                            disabled={!!actionLoading}
                          >
                            {isLoading(`wf-${item.id}-close`) ? 'Chiusura…' : 'Chiudi senza inviare'}
                          </button>
                          <button
                            className="am-btn-primary"
                            onClick={() => handleWorkflowAction(item.id, 'approve_email')}
                            disabled={!!actionLoading}
                          >
                            {isLoading(`wf-${item.id}-approve_email`) ? 'Invio in corso…' : '📧 Invia richiesta ora'}
                          </button>
                        </div>
                      </article>
                    );
                  })}
                </section>
              )}

              {/* Draft communications */}
              {standaloneCommunications.length > 0 && (
                <section className="am-group">
                  <h3 className="am-group-title">
                    <span className="am-group-dot dot-green" />
                    Bozze email pronte — conferma invio
                    <span className="am-group-count">{standaloneCommunications.length}</span>
                  </h3>
                  {standaloneCommunications.map((item) => (
                    <article key={item.id} className="am-card">
                      <div className="am-card-header">
                        <div className="am-recipient">
                          <Avatar name={item.recipient_name || item.recipient_email} />
                          <div className="am-recipient-info">
                            <strong>{item.recipient_name || item.recipient_email}</strong>
                            <span className="am-email-addr">{item.recipient_email}</span>
                          </div>
                        </div>
                        <span className={`am-badge status-${item.status}`}>
                          {STATUS_LABELS[item.status] || item.status}
                        </span>
                      </div>

                      <EmailPreview subject={item.subject} body={item.body} lines={4} />

                      <div className="am-actions">
                        <button
                          className="am-btn-ghost-sm"
                          onClick={() => handleCommunicationStatus(item.id, 'approved')}
                          disabled={!!actionLoading}
                        >
                          Segna come approvata
                        </button>
                        <button
                          className="am-btn-primary"
                          onClick={() => {
                            if (item.suggestion_id) {
                              handleWorkflowAction(item.suggestion_id, 'approve_email');
                            } else {
                              handleCommunicationStatus(item.id, 'sent');
                            }
                          }}
                          disabled={!!actionLoading}
                        >
                          {isLoading(`comm-${item.id}-sent`) ? 'Invio…' : '📧 Invia email ora'}
                        </button>
                      </div>
                    </article>
                  ))}
                </section>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── TAB: ESEGUI ANALISI ────────────────────────────────────────────── */}
      {activeTab === 'run' && (
        <div className="am-tab-content">
          {catalog.length === 0 ? (
            <div className="am-placeholder">Nessun agente disponibile.</div>
          ) : (
            <div className="am-agents-grid">
              {catalog.map((agent) => {
                const icon = AGENT_ICONS[agent.name] || '🤖';
                const supportsCollaborator = agent.supported_entity_types?.includes('collaborator');
                const sel = runSelections[agent.name] || {};

                return (
                  <div key={agent.name} className="am-agent-card">
                    <div className="am-agent-icon">{icon}</div>
                    <h3 className="am-agent-name">{agent.label}</h3>
                    <p className="am-agent-desc">{agent.description || 'Analisi automatica'}</p>

                    <div className="am-agent-chips">
                      {(agent.supported_entity_types || []).map((t) => (
                        <span key={t} className="am-chip">
                          {ENTITY_TYPE_LABELS[t] || t}
                        </span>
                      ))}
                    </div>

                    {supportsCollaborator ? (
                      <div className="am-agent-form">
                        <label className="am-field">
                          <span>Collaboratore</span>
                          <select
                            value={sel.entity_id || ''}
                            onChange={(e) => setRunSelections((p) => ({
                              ...p,
                              [agent.name]: { entity_id: e.target.value },
                            }))}
                          >
                            <option value="">Tutti i collaboratori</option>
                            {collaborators.map((c) => (
                              <option key={c.id} value={c.id}>
                                {c.first_name} {c.last_name}
                              </option>
                            ))}
                          </select>
                        </label>
                        <button
                          className="am-btn-primary am-btn-full"
                          onClick={() => {
                            const entityId = sel.entity_id || null;
                            runAgentDirect(
                              agent.name,
                              entityId ? 'collaborator' : 'global',
                              entityId,
                            );
                          }}
                          disabled={running || loading}
                        >
                          {running ? 'Analisi in corso…' : sel.entity_id
                            ? `Analizza ${collaboratorById[sel.entity_id] || 'selezionato'}`
                            : 'Analizza tutti'}
                        </button>
                      </div>
                    ) : (
                      <button
                        className="am-btn-primary am-btn-full"
                        onClick={() => runAgentDirect(agent.name, 'global', null)}
                        disabled={running || loading}
                      >
                        {running ? 'Analisi in corso…' : 'Avvia analisi'}
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {/* Advanced: manual draft creation */}
          <div className="am-advanced">
            <button
              className="am-advanced-toggle"
              onClick={() => setShowAdvanced((v) => !v)}
            >
              {showAdvanced ? '▾' : '▸'} Crea bozza manuale
            </button>
            {showAdvanced && (
              <div className="am-advanced-body">
                <div className="am-form-grid">
                  <label className="am-field">
                    <span>Tipo destinatario</span>
                    <select
                      value={draftForm.recipient_type}
                      onChange={(e) => setDraftForm((p) => ({ ...p, recipient_type: e.target.value, recipient_id: '', recipient_email: '', recipient_name: '' }))}
                    >
                      {Object.entries(ENTITY_TYPE_LABELS).map(([v, l]) => (
                        <option key={v} value={v}>{l}</option>
                      ))}
                    </select>
                  </label>
                  <label className="am-field">
                    <span>Destinatario</span>
                    {draftForm.recipient_type === 'collaborator' ? (
                      <select
                        value={draftForm.recipient_id}
                        onChange={(e) => {
                          const c = collaborators.find((x) => String(x.id) === e.target.value);
                          setDraftForm((p) => ({
                            ...p,
                            recipient_id: e.target.value,
                            recipient_name: c ? `${c.first_name} ${c.last_name}`.trim() : p.recipient_name,
                            recipient_email: c?.email || p.recipient_email,
                          }));
                        }}
                      >
                        <option value="">Seleziona collaboratore</option>
                        {collaborators.map((c) => (
                          <option key={c.id} value={c.id}>{c.first_name} {c.last_name}</option>
                        ))}
                      </select>
                    ) : (
                      <input
                        value={draftForm.recipient_email}
                        onChange={(e) => setDraftForm((p) => ({ ...p, recipient_email: e.target.value }))}
                        placeholder="email@destinatario.it"
                        type="email"
                      />
                    )}
                  </label>
                  <label className="am-field am-field-full">
                    <span>Oggetto</span>
                    <input
                      value={draftForm.subject}
                      onChange={(e) => setDraftForm((p) => ({ ...p, subject: e.target.value }))}
                      placeholder="Oggetto dell'email…"
                    />
                  </label>
                  <label className="am-field am-field-full">
                    <span>Corpo email</span>
                    <textarea
                      className="am-note"
                      rows="5"
                      value={draftForm.body}
                      onChange={(e) => setDraftForm((p) => ({ ...p, body: e.target.value }))}
                      placeholder="Testo dell'email…"
                    />
                  </label>
                </div>
                <div className="am-actions">
                  <button
                    className="am-btn-primary"
                    onClick={handleCreateDraft}
                    disabled={isLoading('draft-create')}
                  >
                    {isLoading('draft-create') ? 'Creazione…' : 'Crea bozza'}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── TAB: STORICO ──────────────────────────────────────────────────── */}
      {activeTab === 'history' && (
        <div className="am-tab-content">
          {runs.length === 0 ? (
            <div className="am-empty-state">
              <div className="am-empty-icon">📋</div>
              <h3>Nessuna analisi eseguita</h3>
              <p>Vai su "Esegui analisi" per avviare la prima analisi.</p>
            </div>
          ) : (
            <div className="am-history-list">
              {runs.map((item) => {
                const entityName = resolveEntityName(item.entity_type, item.entity_id);
                return (
                  <article key={item.id} className="am-history-card">
                    <div className="am-history-header">
                      <div>
                        <strong className="am-history-agent">
                          {AGENT_ICONS[item.agent_name] || '🤖'} {item.agent_name}
                        </strong>
                        <span className="am-history-target">
                          {entityName || ENTITY_TYPE_LABELS[item.entity_type] || 'Globale'}
                        </span>
                      </div>
                      <div className="am-history-right">
                        <span className={`am-badge status-${item.status}`}>
                          {STATUS_LABELS[item.status] || item.status}
                        </span>
                        <span className="am-meta">{formatDateTime(item.started_at)}</span>
                      </div>
                    </div>
                    <div className="am-meta">
                      {item.suggestions_count || 0} email proposte · Completata {formatDateTime(item.completed_at)}
                    </div>
                    {item.error_message && (
                      <div className="am-inline-error">{item.error_message}</div>
                    )}
                  </article>
                );
              })}
            </div>
          )}
        </div>
      )}

      <div className="am-footer">
        Utente: <strong>{currentUser?.full_name || currentUser?.username || 'admin'}</strong>
      </div>
    </div>
  );
}
