import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  archiveEmailInboxItem,
  downloadEmailInboxAttachment,
  getAgentCommunications,
  getAgentLlmHealth,
  getAgentsSystemHealth,
  getAgentSuggestions,
  getCollaborators,
  getEmailInboxItems,
  manualUpdateCollaborator,
  sendAgentSuggestionEmail,
  sendEmailInboxFollowup,
} from '../services/apiService';
import './AgentsManager.css';

const FIELD_OPTIONS = [
  { value: 'curriculum', label: 'CV' },
  { value: 'documento_identita', label: 'Documento identita' },
  { value: 'documento_identita_scadenza', label: 'Scadenza documento' },
  { value: 'fiscal_code', label: 'Codice fiscale' },
  { value: 'phone', label: 'Telefono' },
];

const formatDateTime = (value) => {
  if (!value) return '-';
  try {
    return new Intl.DateTimeFormat('it-IT', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(value));
  } catch {
    return value;
  }
};

const parsePayload = (value) => {
  if (!value) return {};
  if (typeof value === 'object') return value;
  try {
    return JSON.parse(value);
  } catch {
    return {};
  }
};

const collaboratorName = (collaborator) => {
  if (!collaborator) return null;
  return `${collaborator.first_name || ''} ${collaborator.last_name || ''}`.trim() || `Collaboratore #${collaborator.id}`;
};

function Badge({ tone, children }) {
  return <span className={`am-kanban-badge ${tone}`}>{children}</span>;
}

function Avatar({ name }) {
  return <span className="am-avatar">{(name || '?').slice(0, 1).toUpperCase()}</span>;
}

function CardShell({ itemKey, title, subtitle, badge, meta, children }) {
  return (
    <article key={itemKey} className="am-card am-kanban-card">
      <div className="am-card-header">
        <div className="am-recipient">
          <Avatar name={title} />
          <div className="am-recipient-info">
            <strong>{title}</strong>
            {subtitle && <span className="am-email-addr">{subtitle}</span>}
          </div>
        </div>
        {badge}
      </div>
      {meta && <div className="am-meta">{meta}</div>}
      {children}
    </article>
  );
}

export default function AgentsManager({ currentUser }) {
  const [suggestions, setSuggestions] = useState([]);
  const [communications, setCommunications] = useState([]);
  const [emailInboxItems, setEmailInboxItems] = useState([]);
  const [collaborators, setCollaborators] = useState([]);
  const [llmHealth, setLlmHealth] = useState(null);
  const [systemHealth, setSystemHealth] = useState(null);
  const [healthOpen, setHealthOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(null);
  const [error, setError] = useState(null);
  const [message, setMessage] = useState(null);
  const [manualFields, setManualFields] = useState({});
  const [followupFields, setFollowupFields] = useState({});
  const [archiveOpen, setArchiveOpen] = useState(false);
  const [archiveFilters, setArchiveFilters] = useState({ collaborator: '', date: '' });

  const collaboratorById = useMemo(() => {
    return collaborators.reduce((acc, item) => {
      acc[item.id] = item;
      return acc;
    }, {});
  }, [collaborators]);

  const communicationsBySuggestion = useMemo(() => {
    return communications.reduce((acc, item) => {
      if (!item.suggestion_id) return acc;
      acc[item.suggestion_id] = acc[item.suggestion_id] || [];
      acc[item.suggestion_id].push(item);
      return acc;
    }, {});
  }, [communications]);

  const sentSuggestionIds = useMemo(() => new Set(
    communications
      .filter((item) => item.status === 'sent' && item.suggestion_id)
      .map((item) => item.suggestion_id),
  ), [communications]);

  const latestInboxByCollaborator = useMemo(() => {
    const map = {};
    emailInboxItems.forEach((item) => {
      if (item.entity_type !== 'collaborator' || !item.entity_id || item.archived) return;
      if (!map[item.entity_id] || new Date(item.received_at) > new Date(map[item.entity_id].received_at)) {
        map[item.entity_id] = item;
      }
    });
    return map;
  }, [emailInboxItems]);

  const toSendItems = useMemo(() => suggestions.filter((item) => {
    const drafts = communicationsBySuggestion[item.id] || [];
    return item.status === 'pending' && !drafts.some((draft) => draft.status === 'sent');
  }), [communicationsBySuggestion, suggestions]);

  const waitingItems = useMemo(() => {
    return suggestions
      .filter((item) => sentSuggestionIds.has(item.id) || item.status === 'sent')
      .filter((item) => !latestInboxByCollaborator[item.entity_id])
      .map((item) => ({
        ...item,
        sentDraft: (communicationsBySuggestion[item.id] || []).find((draft) => draft.status === 'sent'),
      }));
  }, [communicationsBySuggestion, latestInboxByCollaborator, sentSuggestionIds, suggestions]);

  const manualReviewItems = useMemo(() =>
    emailInboxItems.filter((item) => item.processing_status === 'manual_review' && !item.archived),
  [emailInboxItems]);

  const completedItems = useMemo(() =>
    emailInboxItems.filter((item) => ['auto_processed', 'valid'].includes(item.processing_status) && !item.archived),
  [emailInboxItems]);

  const archivedItems = useMemo(() => {
    return emailInboxItems
      .filter((item) => item.archived)
      .filter((item) => {
        const name = collaboratorName(collaboratorById[item.entity_id]) || '';
        const byName = !archiveFilters.collaborator || name.toLowerCase().includes(archiveFilters.collaborator.toLowerCase());
        const byDate = !archiveFilters.date || (item.archived_at || item.received_at || '').slice(0, 10) === archiveFilters.date;
        return byName && byDate;
      });
  }, [archiveFilters, collaboratorById, emailInboxItems]);

  const totalOpen = toSendItems.length + waitingItems.length + manualReviewItems.length + completedItems.length;

  const showToast = useCallback((text, kind = 'success') => {
    setMessage({ text, kind });
    window.setTimeout(() => setMessage(null), 3500);
  }, []);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [sugg, comms, inbox, archived, collab, llm, health] = await Promise.all([
        getAgentSuggestions({ limit: 200 }),
        getAgentCommunications({ limit: 200 }),
        getEmailInboxItems({ limit: 200, archived: false }),
        getEmailInboxItems({ limit: 200, archived: true }),
        getCollaborators({}, { limit: 300 }),
        getAgentLlmHealth(),
        getAgentsSystemHealth().catch(() => null),
      ]);
      setSuggestions(Array.isArray(sugg) ? sugg : []);
      setCommunications(Array.isArray(comms) ? comms : []);
      setEmailInboxItems([...(inbox?.items || []), ...(archived?.items || [])]);
      setCollaborators(Array.isArray(collab) ? collab : []);
      setLlmHealth(llm || null);
      setSystemHealth(health || null);
    } catch (e) {
      setError(e?.response?.data?.detail || 'Errore nel caricamento della sezione Agenti.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const isLoading = (key) => actionLoading === key;

  const itemCollaborator = (item) => collaboratorById[item.entity_id] || null;
  const itemName = (item) => collaboratorName(itemCollaborator(item)) || `Collaboratore #${item.entity_id || '-'}`;
  const missingFields = (item) => {
    const payload = parsePayload(item.payload);
    if (Array.isArray(payload.missing_fields)) return payload.missing_fields;
    if (Array.isArray(payload.fields_requested)) return payload.fields_requested;
    return [];
  };

  const handleSendEmail = useCallback(async (suggestionId) => {
    if (actionLoading) return;
    setActionLoading(`send-${suggestionId}`);
    setError(null);
    try {
      await sendAgentSuggestionEmail(suggestionId, {
        action: 'approve_email',
        reviewed_by_user_id: currentUser?.id || null,
      });
      await loadData();
      showToast('Email inviata. La pratica passa in attesa risposta.');
    } catch (e) {
      setError(e?.response?.data?.detail || 'Invio email non riuscito.');
    } finally {
      setActionLoading(null);
    }
  }, [actionLoading, currentUser?.id, loadData, showToast]);

  const handleManualField = useCallback((itemId, field, value) => {
    setManualFields((prev) => ({
      ...prev,
      [itemId]: { ...(prev[itemId] || {}), [field]: value },
    }));
  }, []);

  const handleSaveManual = useCallback(async (item) => {
    const fields = manualFields[item.id] || {};
    const payloadFields = {};
    if (fields.documento_identita_scadenza) {
      payloadFields.documento_identita_scadenza = fields.documento_identita_scadenza;
    }
    if (!Object.keys(payloadFields).length) {
      setError('Inserisci almeno un campo manuale da salvare.');
      return;
    }
    setActionLoading(`manual-save-${item.id}`);
    setError(null);
    try {
      await manualUpdateCollaborator(item.entity_id, {
        fields: payloadFields,
        reviewed_by_user_id: currentUser?.id || null,
        source_item_id: item.id,
      });
      await loadData();
      showToast('Dati collaboratore aggiornati.');
    } catch (e) {
      setError(e?.response?.data?.detail || 'Salvataggio manuale non riuscito.');
    } finally {
      setActionLoading(null);
    }
  }, [currentUser?.id, loadData, manualFields, showToast]);

  const handleFollowupField = useCallback((itemId, value) => {
    setFollowupFields((prev) => {
      const selected = new Set(prev[itemId] || []);
      if (selected.has(value)) selected.delete(value);
      else selected.add(value);
      return { ...prev, [itemId]: Array.from(selected) };
    });
  }, []);

  const handleSendFollowup = useCallback(async (item) => {
    const fields = followupFields[item.id] || [];
    if (!fields.length) {
      setError('Seleziona cosa richiedere nel sollecito.');
      return;
    }
    setActionLoading(`followup-${item.id}`);
    setError(null);
    try {
      await sendEmailInboxFollowup(item.id, {
        fields_requested: fields,
        reviewed_by_user_id: currentUser?.id || null,
      });
      await loadData();
      showToast('Sollecito inviato. La pratica torna in attesa risposta.');
    } catch (e) {
      setError(e?.response?.data?.detail || 'Invio sollecito non riuscito.');
    } finally {
      setActionLoading(null);
    }
  }, [currentUser?.id, followupFields, loadData, showToast]);

  const handleArchive = useCallback(async (itemId) => {
    setActionLoading(`archive-${itemId}`);
    setError(null);
    try {
      await archiveEmailInboxItem(itemId);
      await loadData();
      showToast('Pratica archiviata.');
    } catch (e) {
      setError(e?.response?.data?.detail || 'Archiviazione non riuscita.');
    } finally {
      setActionLoading(null);
    }
  }, [loadData, showToast]);

  const handleResolveManual = useCallback(async (item) => {
    setActionLoading(`resolve-${item.id}`);
    setError(null);
    try {
      await archiveEmailInboxItem(item.id);
      await loadData();
      showToast('Pratica risolta manualmente e archiviata.');
    } catch (e) {
      setError(e?.response?.data?.detail || 'Chiusura manuale non riuscita.');
    } finally {
      setActionLoading(null);
    }
  }, [loadData, showToast]);

  const handleAttachmentPreview = useCallback(async (item) => {
    const previewWindow = window.open('', '_blank');
    setActionLoading(`preview-${item.id}`);
    setError(null);
    try {
      const response = await downloadEmailInboxAttachment(item.id);
      const contentType = response.headers?.['content-type'] || 'application/octet-stream';
      const url = window.URL.createObjectURL(new Blob([response.data], { type: contentType }));
      if (previewWindow) previewWindow.location.href = url;
      else window.open(url, '_blank', 'noopener,noreferrer');
      window.setTimeout(() => window.URL.revokeObjectURL(url), 60000);
    } catch (e) {
      if (previewWindow && !previewWindow.closed) previewWindow.close();
      setError(e?.response?.data?.detail || 'Anteprima allegato non riuscita.');
    } finally {
      setActionLoading(null);
    }
  }, []);

  return (
    <div className="am">
      <div className="am-topbar">
        <div>
          <h2 className="am-title">Agenti</h2>
          <p className="am-subtitle">Comunicazioni, risposte e revisioni documentali</p>
        </div>
        <div className="am-topbar-right">
          <div className={`am-llm-pill ${llmHealth?.reachable ? 'ok' : 'warn'}`}>
            <span className="am-llm-dot" />
            {llmHealth?.reachable ? `AI attiva - ${llmHealth.provider}` : 'AI non disponibile'}
          </div>
          <button className="am-btn-ghost" onClick={loadData} disabled={loading}>
            {loading ? 'Aggiorno...' : 'Aggiorna'}
          </button>
        </div>
      </div>

      {message && <div className={`am-toast am-toast-${message.kind}`}>{message.text}</div>}
      {error && <div className="am-error">{error}</div>}

      {systemHealth && (
        <div className="am-card" style={{ marginBottom: 12 }}>
          <button
            className="am-btn-ghost"
            onClick={() => setHealthOpen((prev) => !prev)}
            aria-expanded={healthOpen}
          >
            {healthOpen ? '▾' : '▸'} Stato sistema agenti
            {!systemHealth.agents_enabled && ' — KILL SWITCH GLOBALE ATTIVO'}
            {systemHealth.inbox?.state && systemHealth.inbox.state !== 'connected' && ` — ${systemHealth.inbox.message || systemHealth.inbox.state}`}
          </button>
          {healthOpen && (
            <div style={{ padding: '8px 12px' }}>
              <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ textAlign: 'left' }}>
                    <th>Agente</th>
                    <th>Attivo</th>
                    <th>Schedulazione</th>
                    <th>Ultimo run</th>
                    <th>Esito</th>
                  </tr>
                </thead>
                <tbody>
                  {(systemHealth.agents || []).map((agent) => (
                    <tr key={agent.name}>
                      <td>{agent.name}</td>
                      <td>{agent.enabled ? 'sì' : 'NO'}</td>
                      <td>{agent.schedule || '-'}</td>
                      <td>{formatDateTime(agent.last_run?.completed_at || agent.last_run?.started_at)}</td>
                      <td>
                        {agent.last_run ? agent.last_run.status : 'mai eseguito'}
                        {agent.last_run?.error_message ? ` — ${agent.last_run.error_message}` : ''}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p style={{ fontSize: 13, marginTop: 8 }}>
                {systemHealth.inbox?.message || 'Inbox: stato sconosciuto'}
                {' · '}
                {systemHealth.llm?.reachable ? `LLM ok (${systemHealth.llm.provider})` : 'LLM non raggiungibile'}
                {' · '}
                {systemHealth.arq?.reachable
                  ? `Coda ARQ ok${systemHealth.arq.queue_depth != null ? ` (depth ${systemHealth.arq.queue_depth})` : ''}`
                  : 'Coda ARQ non raggiungibile'}
              </p>
            </div>
          )}
        </div>
      )}

      {loading ? (
        <div className="am-placeholder">Caricamento...</div>
      ) : (
        <>
          <div className="am-kanban-summary">
            <span>{totalOpen} pratiche aperte</span>
            <span>{archivedItems.length} archiviate filtrate</span>
          </div>

          <div className="am-kanban">
            <section className="am-kanban-column">
              <header className="am-kanban-header">
                <Badge tone="blue">Da inviare</Badge>
                <strong>{toSendItems.length}</strong>
              </header>
              {toSendItems.map((item) => (
                <CardShell
                  key={item.id}
                  title={itemName(item)}
                  subtitle={item.title}
                  badge={<Badge tone="blue">Pronta</Badge>}
                  meta={`Creata ${formatDateTime(item.created_at)}`}
                >
                  <p className="am-card-text">{item.description || 'Comunicazione pronta per invio.'}</p>
                  {missingFields(item).length > 0 && (
                    <div className="am-chip-row">
                      {missingFields(item).map((field) => <span key={field} className="am-chip">{field}</span>)}
                    </div>
                  )}
                  <button className="am-btn-primary" onClick={() => handleSendEmail(item.id)} disabled={!!actionLoading}>
                    {isLoading(`send-${item.id}`) ? 'Invio...' : 'Invia email'}
                  </button>
                </CardShell>
              ))}
              {toSendItems.length === 0 && <div className="am-empty-column">Nessuna email da inviare</div>}
            </section>

            <section className="am-kanban-column">
              <header className="am-kanban-header">
                <Badge tone="yellow">In attesa risposta</Badge>
                <strong>{waitingItems.length}</strong>
              </header>
              {waitingItems.map((item) => {
                const draft = item.sentDraft;
                return (
                  <CardShell
                    key={item.id}
                    title={itemName(item)}
                    subtitle={draft?.recipient_email || item.title}
                    badge={<Badge tone="yellow">In attesa</Badge>}
                    meta={`Inviata ${formatDateTime(draft?.sent_at || item.reviewed_at)}`}
                  >
                    <p className="am-card-text">{item.description || 'Risposta del collaboratore non ancora ricevuta.'}</p>
                    {missingFields(item).length > 0 && (
                      <div className="am-chip-row">
                        {missingFields(item).map((field) => <span key={field} className="am-chip">{field}</span>)}
                      </div>
                    )}
                  </CardShell>
                );
              })}
              {waitingItems.length === 0 && <div className="am-empty-column">Nessuna pratica in attesa</div>}
            </section>

            <section className="am-kanban-column">
              <header className="am-kanban-header">
                <Badge tone="orange">Revisione manuale</Badge>
                <strong>{manualReviewItems.length}</strong>
              </header>
              {manualReviewItems.map((item) => (
                <CardShell
                  key={item.id}
                  title={itemName(item)}
                  subtitle={item.sender_email}
                  badge={<Badge tone="orange">Parziale</Badge>}
                  meta={`Ricevuta ${formatDateTime(item.received_at)}${item.attachment_name ? ` - ${item.attachment_name}` : ''}`}
                >
                  {item.subject && <p className="am-card-text">{item.subject}</p>}
                  {item.attachment_name && (
                    <button className="am-btn-ghost-sm" onClick={() => handleAttachmentPreview(item)} disabled={!!actionLoading}>
                      {isLoading(`preview-${item.id}`) ? 'Apro...' : 'Anteprima allegato'}
                    </button>
                  )}
                  <label className="am-field">
                    <span>Scadenza documento ricevuto</span>
                    <input
                      type="date"
                      value={manualFields[item.id]?.documento_identita_scadenza || ''}
                      onChange={(event) => handleManualField(item.id, 'documento_identita_scadenza', event.target.value)}
                    />
                  </label>
                  <button className="am-btn-ghost-sm" onClick={() => handleSaveManual(item)} disabled={!!actionLoading}>
                    {isLoading(`manual-save-${item.id}`) ? 'Salvo...' : 'Salva'}
                  </button>
                  <div className="am-followup-box">
                    <span className="am-small-label">Richiedi ancora</span>
                    {FIELD_OPTIONS.map((option) => (
                      <label key={option.value} className="am-check">
                        <input
                          type="checkbox"
                          checked={(followupFields[item.id] || []).includes(option.value)}
                          onChange={() => handleFollowupField(item.id, option.value)}
                        />
                        <span>{option.label}</span>
                      </label>
                    ))}
                    <button className="am-btn-primary" onClick={() => handleSendFollowup(item)} disabled={!!actionLoading}>
                      {isLoading(`followup-${item.id}`) ? 'Invio...' : 'Invia sollecito'}
                    </button>
                  </div>
                  <button className="am-btn-ghost-sm" onClick={() => handleResolveManual(item)} disabled={!!actionLoading}>
                    {isLoading(`resolve-${item.id}`) ? 'Chiudo...' : 'Risolvi manualmente'}
                  </button>
                </CardShell>
              ))}
              {manualReviewItems.length === 0 && <div className="am-empty-column">Nessuna revisione manuale</div>}
            </section>

            <section className="am-kanban-column">
              <header className="am-kanban-header">
                <Badge tone="green">Completato automaticamente</Badge>
                <strong>{completedItems.length}</strong>
              </header>
              {completedItems.map((item) => (
                <CardShell
                  key={item.id}
                  title={itemName(item)}
                  subtitle={item.sender_email}
                  badge={<Badge tone="green">Completa</Badge>}
                  meta={`Aggiornata ${formatDateTime(item.created_at)}`}
                >
                  <p className="am-card-text">
                    {item.attachment_name ? `Documento processato: ${item.attachment_name}` : 'Risposta processata automaticamente.'}
                  </p>
                  <button className="am-btn-primary" onClick={() => handleArchive(item.id)} disabled={!!actionLoading}>
                    {isLoading(`archive-${item.id}`) ? 'Archivio...' : 'Archivia'}
                  </button>
                </CardShell>
              ))}
              {completedItems.length === 0 && <div className="am-empty-column">Nessun completamento automatico</div>}
            </section>
          </div>

          <section className="am-archive">
            <button className="am-archive-toggle" onClick={() => setArchiveOpen((value) => !value)}>
              Archiviate
              <span>{archiveOpen ? 'Chiudi' : 'Apri'}</span>
            </button>
            {archiveOpen && (
              <div className="am-archive-body">
                <div className="am-archive-filters">
                  <input
                    placeholder="Filtra collaboratore"
                    value={archiveFilters.collaborator}
                    onChange={(event) => setArchiveFilters((prev) => ({ ...prev, collaborator: event.target.value }))}
                  />
                  <input
                    type="date"
                    value={archiveFilters.date}
                    onChange={(event) => setArchiveFilters((prev) => ({ ...prev, date: event.target.value }))}
                  />
                </div>
                {archivedItems.map((item) => (
                  <div key={item.id} className="am-archive-row">
                    <strong>{itemName(item)}</strong>
                    <span>{item.subject || item.attachment_name || item.sender_email}</span>
                    <time>{formatDateTime(item.archived_at || item.received_at)}</time>
                  </div>
                ))}
                {archivedItems.length === 0 && <div className="am-empty-column">Nessuna pratica archiviata per questi filtri</div>}
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
