import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  acceptAgentSuggestion,
  getAgentCommunications,
  getAgentsCatalog,
  getAgentLlmHealth,
  getAgentRuns,
  getAgentSuggestions,
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
  waiting: 'In attesa',
  approved: 'Pronta da inviare',
  accepted: 'Accettato',
  rejected: 'Rifiutato',
  sent: 'Inviata',
  followup_due: 'Sollecito da gestire',
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

const formatDateTime = (value) => {
  if (!value) {
    return '—';
  }
  try {
    return new Intl.DateTimeFormat('it-IT', {
      dateStyle: 'short',
      timeStyle: 'short',
    }).format(new Date(value));
  } catch {
    return value;
  }
};

const parsePayload = (value) => {
  if (!value) {
    return null;
  }
  if (typeof value === 'object') {
    return value;
  }
  try {
    return JSON.parse(value);
  } catch {
    return value;
  }
};

const prettyPayload = (value) => {
  const parsed = parsePayload(value);
  if (!parsed) {
    return '';
  }
  if (typeof parsed === 'string') {
    return parsed;
  }
  return JSON.stringify(parsed, null, 2);
};

export default function AgentsManager({ currentUser }) {
  const [catalog, setCatalog] = useState([]);
  const [runs, setRuns] = useState([]);
  const [suggestions, setSuggestions] = useState([]);
  const [communications, setCommunications] = useState([]);
  const [llmHealth, setLlmHealth] = useState(null);
  const [projects, setProjects] = useState([]);
  const [collaborators, setCollaborators] = useState([]);
  const [aziende, setAziende] = useState([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [actionLoading, setActionLoading] = useState(null);
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);
  const [selectedRunId, setSelectedRunId] = useState('');
  const [notesBySuggestion, setNotesBySuggestion] = useState({});
  const [form, setForm] = useState({
    agent_name: '',
    entity_type: 'global',
    entity_id: '',
    limit: 25,
  });

  const selectedAgent = useMemo(
    () => catalog.find((item) => item.name === form.agent_name) || null,
    [catalog, form.agent_name],
  );
  const supportedEntityTypes = useMemo(
    () => selectedAgent?.supported_entity_types || [],
    [selectedAgent],
  );
  const selectableEntityTypes = useMemo(() => {
    if (!selectedAgent || supportedEntityTypes.length === 0) {
      return Object.entries(ENTITY_TYPE_LABELS);
    }
    return Object.entries(ENTITY_TYPE_LABELS).filter(([value]) => supportedEntityTypes.includes(value));
  }, [selectedAgent, supportedEntityTypes]);

  const entityOptions = useMemo(() => {
    if (form.entity_type === 'project') {
      return projects.map((item) => ({ id: item.id, label: item.name }));
    }
    if (form.entity_type === 'collaborator') {
      return collaborators.map((item) => ({
        id: item.id,
        label: `${item.first_name} ${item.last_name}`.trim(),
      }));
    }
    if (form.entity_type === 'azienda_cliente') {
      return aziende.map((item) => ({ id: item.id, label: item.ragione_sociale }));
    }
    return [];
  }, [aziende, collaborators, form.entity_type, projects]);

  const filteredSuggestions = useMemo(() => {
    if (!selectedRunId) {
      return suggestions;
    }
    return suggestions.filter((item) => String(item.run_id) === String(selectedRunId));
  }, [selectedRunId, suggestions]);

  const filteredCommunications = useMemo(() => {
    if (!selectedRunId) {
      return communications;
    }
    return communications.filter((item) => String(item.run_id) === String(selectedRunId));
  }, [communications, selectedRunId]);

  const operatorQueue = useMemo(() => {
    const communicationsBySuggestionId = communications.reduce((accumulator, item) => {
      if (!item.suggestion_id) {
        return accumulator;
      }
      accumulator[item.suggestion_id] = accumulator[item.suggestion_id] || [];
      accumulator[item.suggestion_id].push(item);
      return accumulator;
    }, {});

    return suggestions
      .filter((item) =>
        item.agent_name === 'data_quality'
        && item.entity_type === 'collaborator'
        && ['pending', 'waiting', 'approved', 'sent', 'followup_due'].includes(item.status))
      .map((item) => ({
        ...item,
        communications: communicationsBySuggestionId[item.id] || [],
      }));
  }, [communications, suggestions]);

  const showToast = useCallback((text, kind = 'success') => {
    setMessage({ text, kind });
    setTimeout(() => setMessage(null), 3500);
  }, []);

  const loadReferenceData = useCallback(async () => {
    const [projectsData, collaboratorsData, aziendeData] = await Promise.all([
      getProjects(0, 200),
      getCollaborators(0, 200),
      getAziendeClienti({ limit: 200 }),
    ]);
    setProjects(Array.isArray(projectsData) ? projectsData : []);
    setCollaborators(Array.isArray(collaboratorsData) ? collaboratorsData : []);
    setAziende(Array.isArray(aziendeData) ? aziendeData : (aziendeData?.items || []));
  }, []);

  const loadAgentData = useCallback(async () => {
    const [catalogData, runsData, suggestionsData, communicationsData, llmHealthData] = await Promise.all([
      getAgentsCatalog(),
      getAgentRuns({ limit: 50 }),
      getAgentSuggestions({ limit: 100 }),
      getAgentCommunications({ limit: 100 }),
      getAgentLlmHealth(),
    ]);

    const catalogItems = Array.isArray(catalogData) ? catalogData : [];
    setCatalog(catalogItems);
    setRuns(Array.isArray(runsData) ? runsData : []);
    setSuggestions(Array.isArray(suggestionsData) ? suggestionsData : []);
    setCommunications(Array.isArray(communicationsData) ? communicationsData : []);
    setLlmHealth(llmHealthData || null);
    setForm((previous) => ({
      ...previous,
      agent_name: previous.agent_name || catalogItems[0]?.name || '',
    }));
  }, []);

  const loadAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      await Promise.all([loadReferenceData(), loadAgentData()]);
    } catch (loadError) {
      setError(loadError?.response?.data?.detail || 'Errore nel caricamento modulo agenti.');
    } finally {
      setLoading(false);
    }
  }, [loadAgentData, loadReferenceData]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  useEffect(() => {
    if (!selectedAgent || supportedEntityTypes.length === 0) {
      return;
    }
    if (!supportedEntityTypes.includes(form.entity_type)) {
      setForm((previous) => ({
        ...previous,
        entity_type: supportedEntityTypes[0],
        entity_id: '',
      }));
    }
  }, [form.entity_type, selectedAgent, supportedEntityTypes]);

  useEffect(() => {
    if (form.entity_type === 'global') {
      if (form.entity_id !== '') {
        setForm((previous) => ({ ...previous, entity_id: '' }));
      }
      return;
    }
    if (entityOptions.length === 0) {
      if (form.entity_id !== '') {
        setForm((previous) => ({ ...previous, entity_id: '' }));
      }
      return;
    }
    const hasSelectedValue = entityOptions.some((item) => String(item.id) === String(form.entity_id));
    if (!hasSelectedValue) {
      setForm((previous) => ({ ...previous, entity_id: String(entityOptions[0].id) }));
    }
  }, [entityOptions, form.entity_id, form.entity_type]);

  const handleRunAgent = async () => {
    if (!form.agent_name) {
      setError('Seleziona un agente da eseguire.');
      return;
    }
    if (selectedAgent && !supportedEntityTypes.includes(form.entity_type)) {
      setError('Il tipo entità selezionato non è supportato da questo agente.');
      return;
    }
    if (form.entity_type !== 'global' && !form.entity_id) {
      setError('Seleziona un record da analizzare.');
      return;
    }

    setRunning(true);
    setError(null);
    try {
      const result = await runAgent({
        agent_name: form.agent_name,
        entity_type: form.entity_type,
        entity_id: form.entity_type === 'global' ? null : Number(form.entity_id),
        requested_by_user_id: currentUser?.id || null,
        input_payload: {
          limit: Number(form.limit) || 25,
        },
      });
      await loadAgentData();
      setSelectedRunId(result?.id ? String(result.id) : '');
      showToast('Agente eseguito con successo.');
    } catch (runError) {
      setError(runError?.response?.data?.detail || 'Esecuzione agente non riuscita.');
    } finally {
      setRunning(false);
    }
  };

  const handleSuggestionReview = async (suggestionId, action) => {
    setActionLoading(`suggestion-${suggestionId}-${action}`);
    setError(null);
    try {
      if (action === 'accept') {
        await acceptAgentSuggestion(suggestionId, {
          action: 'accepted',
          notes: notesBySuggestion[suggestionId] || null,
          reviewed_by_user_id: currentUser?.id || null,
        });
      } else {
        await rejectAgentSuggestion(suggestionId, {
          action: 'rejected',
          notes: notesBySuggestion[suggestionId] || null,
          reviewed_by_user_id: currentUser?.id || null,
        });
      }
      await loadAgentData();
      showToast(`Suggerimento ${action === 'accept' ? 'accettato' : 'rifiutato'}.`);
    } catch (reviewError) {
      setError(reviewError?.response?.data?.detail || 'Aggiornamento suggerimento non riuscito.');
    } finally {
      setActionLoading(null);
    }
  };

  const handleCommunicationStatus = async (draftId, status) => {
    setActionLoading(`communication-${draftId}-${status}`);
    setError(null);
    try {
      await updateAgentCommunicationStatus(draftId, {
        status,
        reviewed_by_user_id: currentUser?.id || null,
      });
      await loadAgentData();
      showToast(`Bozza aggiornata a stato "${STATUS_LABELS[status] || status}".`);
    } catch (updateError) {
      setError(updateError?.response?.data?.detail || 'Aggiornamento bozza non riuscito.');
    } finally {
      setActionLoading(null);
    }
  };

  const handleWorkflowAction = async (suggestionId, action) => {
    setActionLoading(`workflow-${suggestionId}-${action}`);
    setError(null);
    try {
      await workflowAgentSuggestion(suggestionId, {
        action,
        notes: notesBySuggestion[suggestionId] || null,
        reviewed_by_user_id: currentUser?.id || null,
      });
      await loadAgentData();
      showToast('Workflow aggiornato.');
    } catch (workflowError) {
      setError(workflowError?.response?.data?.detail || 'Aggiornamento workflow non riuscito.');
    } finally {
      setActionLoading(null);
    }
  };

  const totalPendingSuggestions = suggestions.filter((item) => ['pending', 'followup_due'].includes(item.status)).length;
  const totalDraftCommunications = communications.filter((item) => ['draft', 'approved', 'followup_due'].includes(item.status)).length;

  return (
    <div className="agents-manager">
      <div className="agents-hero">
        <div>
          <span className="agents-eyebrow">AI Workflow</span>
          <h2>Agenti Operativi</h2>
          <p>
            Esegui agenti backend già registrati, controlla le analisi prodotte e gestisci
            suggerimenti o bozze email senza uscire dal gestionale.
          </p>
        </div>
        <div className="agents-hero-stats">
          <div className={`agents-stat-card agents-stat-card-llm ${llmHealth?.reachable ? 'is-ok' : 'is-warn'}`}>
            <strong>{llmHealth?.provider || 'none'}</strong>
            <span>{llmHealth?.reachable ? 'LLM raggiungibile' : (llmHealth?.detail || 'LLM non disponibile')}</span>
          </div>
          <div className="agents-stat-card">
            <strong>{catalog.length}</strong>
            <span>Agenti registrati</span>
          </div>
          <div className="agents-stat-card">
            <strong>{totalPendingSuggestions}</strong>
            <span>Suggerimenti pending</span>
          </div>
          <div className="agents-stat-card">
            <strong>{totalDraftCommunications}</strong>
            <span>Bozze da rivedere</span>
          </div>
        </div>
      </div>

      {message ? (
        <div className={`agents-toast agents-toast-${message.kind}`}>{message.text}</div>
      ) : null}
      {error ? <div className="agents-error">{error}</div> : null}

      <div className="agents-grid">
        <section className="agents-panel">
          <div className="agents-panel-header">
            <h3>Inbox operatore</h3>
            <span className="agents-panel-note">{operatorQueue.length} pratiche attive</span>
          </div>

          {operatorQueue.length === 0 ? (
            <div className="agents-empty">Nessuna pratica automatica aperta sui collaboratori.</div>
          ) : (
            <div className="agents-stack">
              {operatorQueue.map((item) => {
                const payload = parsePayload(item.payload);
                const missingFields = Array.isArray(payload?.missing_fields) ? payload.missing_fields : [];
                const emailCommunication = item.communications.find((entry) => entry.channel === 'email') || null;
                const whatsappCommunication = item.communications.find((entry) => entry.channel === 'whatsapp') || null;
                const emailAction = item.status === 'followup_due' ? 'remind_email' : 'approve_email';
                const whatsappAction = item.status === 'followup_due' ? 'remind_whatsapp' : 'approve_whatsapp';

                return (
                  <article key={`queue-${item.id}`} className="agents-card">
                    <div className="agents-card-top">
                      <div>
                        <strong>{item.title}</strong>
                        <div className="agents-meta">
                          Collaboratore ID {item.entity_id} · Run #{item.run_id}
                        </div>
                      </div>
                      <div className="agents-chip-row">
                        <span className={`agents-badge agents-severity-${item.severity}`}>{SEVERITY_LABELS[item.severity] || item.severity}</span>
                        <span className={`agents-badge agents-status-${item.status}`}>{STATUS_LABELS[item.status] || item.status}</span>
                      </div>
                    </div>

                    <p className="agents-description">{item.description}</p>
                    {missingFields.length > 0 ? (
                      <div className="agents-meta">Campi mancanti: <strong>{missingFields.join(', ')}</strong></div>
                    ) : null}
                    {emailCommunication ? (
                      <div className="agents-meta">
                        Email: {STATUS_LABELS[emailCommunication.status] || emailCommunication.status}
                        {emailCommunication.sent_at ? ` · Ultimo invio ${formatDateTime(emailCommunication.sent_at)}` : ''}
                      </div>
                    ) : null}
                    {whatsappCommunication ? (
                      <div className="agents-meta">
                        WhatsApp: {STATUS_LABELS[whatsappCommunication.status] || whatsappCommunication.status}
                        {whatsappCommunication.sent_at ? ` · Ultimo invio ${formatDateTime(whatsappCommunication.sent_at)}` : ''}
                      </div>
                    ) : null}

                    <textarea
                      className="agents-notes"
                      rows="3"
                      placeholder="Note operatore"
                      value={notesBySuggestion[item.id] || ''}
                      onChange={(event) => setNotesBySuggestion((previous) => ({
                        ...previous,
                        [item.id]: event.target.value,
                      }))}
                    />

                    <div className="agents-actions">
                      <button
                        type="button"
                        className="btn-secondary"
                        onClick={() => handleWorkflowAction(item.id, 'wait')}
                        disabled={actionLoading === `workflow-${item.id}-wait`}
                      >
                        {actionLoading === `workflow-${item.id}-wait` ? 'Attendi...' : 'Metti in attesa'}
                      </button>
                      <button
                        type="button"
                        className="btn-secondary"
                        onClick={() => handleWorkflowAction(item.id, 'close')}
                        disabled={actionLoading === `workflow-${item.id}-close`}
                      >
                        {actionLoading === `workflow-${item.id}-close` ? 'Attendi...' : 'Chiudi'}
                      </button>
                      {emailCommunication ? (
                        <button
                          type="button"
                          className="btn-primary"
                          onClick={() => handleWorkflowAction(item.id, emailAction)}
                          disabled={actionLoading === `workflow-${item.id}-${emailAction}`}
                        >
                          {actionLoading === `workflow-${item.id}-${emailAction}`
                            ? 'Attendi...'
                            : item.status === 'followup_due' ? 'Sollecito email' : 'Invia email'}
                        </button>
                      ) : null}
                      {whatsappCommunication ? (
                        <button
                          type="button"
                          className="btn-primary"
                          onClick={() => handleWorkflowAction(item.id, whatsappAction)}
                          disabled={actionLoading === `workflow-${item.id}-${whatsappAction}`}
                        >
                          {actionLoading === `workflow-${item.id}-${whatsappAction}`
                            ? 'Attendi...'
                            : item.status === 'followup_due' ? 'Sollecito WhatsApp' : 'Prepara WhatsApp'}
                        </button>
                      ) : null}
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </section>

        <section className="agents-panel">
          <div className="agents-panel-header">
            <h3>Esegui agente</h3>
            <button type="button" className="btn-secondary" onClick={loadAll} disabled={loading}>
              Aggiorna dati
            </button>
          </div>

          <div className="agents-form-grid">
            <label className="agents-field">
              <span>Agente</span>
              <select
                value={form.agent_name}
                onChange={(event) => setForm((previous) => ({
                  ...previous,
                  agent_name: event.target.value,
                  entity_id: '',
                }))}
              >
                <option value="">Seleziona agente</option>
                {catalog.map((item) => (
                  <option key={item.name} value={item.name}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="agents-field">
              <span>Tipo entità</span>
              <select
                value={form.entity_type}
                onChange={(event) => setForm((previous) => ({
                  ...previous,
                  entity_type: event.target.value,
                  entity_id: '',
                }))}
              >
                {selectableEntityTypes.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>

            <label className="agents-field">
              <span>Record</span>
              {form.entity_type === 'global' ? (
                <input value="Analisi trasversale" disabled />
              ) : (
                <select
                  value={form.entity_id}
                  onChange={(event) => setForm((previous) => ({ ...previous, entity_id: event.target.value }))}
                >
                  <option value="">Seleziona record</option>
                  {entityOptions.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.label}
                    </option>
                  ))}
                </select>
              )}
            </label>

            <label className="agents-field">
              <span>Limite risultati</span>
              <input
                type="number"
                min="1"
                max="100"
                value={form.limit}
                onChange={(event) => setForm((previous) => ({ ...previous, limit: event.target.value }))}
              />
            </label>
          </div>

          {selectedAgent ? (
            <div className="agents-definition">
              <div className="agents-definition-title">{selectedAgent.label}</div>
              <p>{selectedAgent.description}</p>
              <div className="agents-chip-row">
                {selectedAgent.supported_entity_types.map((item) => (
                  <span key={item} className="agents-chip">
                    {ENTITY_TYPE_LABELS[item] || item}
                  </span>
                ))}
              </div>
            </div>
          ) : null}

          <div className="agents-actions">
            <button type="button" className="btn-primary" onClick={handleRunAgent} disabled={running || loading}>
              {running ? 'Esecuzione in corso...' : 'Esegui agente'}
            </button>
          </div>
        </section>

        <section className="agents-panel">
          <div className="agents-panel-header">
            <h3>Run recenti</h3>
            <select
              className="agents-run-filter"
              value={selectedRunId}
              onChange={(event) => setSelectedRunId(event.target.value)}
            >
              <option value="">Tutti i run</option>
              {runs.map((item) => (
                <option key={item.id} value={item.id}>
                  #{item.id} · {item.agent_name} · {formatDateTime(item.started_at)}
                </option>
              ))}
            </select>
          </div>

          {loading ? (
            <div className="agents-empty">Caricamento dati agenti…</div>
          ) : runs.length === 0 ? (
            <div className="agents-empty">Nessun run registrato.</div>
          ) : (
            <div className="agents-stack">
              {runs.map((item) => (
                <article key={item.id} className="agents-card">
                  <div className="agents-card-top">
                    <div>
                      <strong>#{item.id} · {item.agent_name}</strong>
                      <div className="agents-meta">
                        {ENTITY_TYPE_LABELS[item.entity_type] || item.entity_type || '—'}
                        {item.entity_id ? ` · ID ${item.entity_id}` : ''}
                      </div>
                    </div>
                    <span className={`agents-badge agents-status-${item.status}`}>{STATUS_LABELS[item.status] || item.status}</span>
                  </div>
                  <div className="agents-meta">
                    Avviato {formatDateTime(item.started_at)} · Completato {formatDateTime(item.completed_at)}
                  </div>
                  <div className="agents-meta">
                    Suggerimenti prodotti: <strong>{item.suggestions_count}</strong>
                  </div>
                  {item.error_message ? <div className="agents-inline-error">{item.error_message}</div> : null}
                  {item.result_summary ? (
                    <pre className="agents-code-block">{prettyPayload(item.result_summary)}</pre>
                  ) : null}
                </article>
              ))}
            </div>
          )}
        </section>
      </div>

      <div className="agents-grid agents-grid-bottom">
        <section className="agents-panel">
          <div className="agents-panel-header">
            <h3>Suggerimenti</h3>
            <span className="agents-panel-note">{filteredSuggestions.length} elementi</span>
          </div>

          {filteredSuggestions.length === 0 ? (
            <div className="agents-empty">Nessun suggerimento disponibile per il filtro corrente.</div>
          ) : (
            <div className="agents-stack">
              {filteredSuggestions.map((item) => (
                <article key={item.id} className="agents-card">
                  <div className="agents-card-top">
                    <div>
                      <strong>{item.title}</strong>
                      <div className="agents-meta">
                        Run #{item.run_id} · {ENTITY_TYPE_LABELS[item.entity_type] || item.entity_type}
                        {item.entity_id ? ` · ID ${item.entity_id}` : ''}
                      </div>
                    </div>
                    <div className="agents-chip-row">
                      <span className={`agents-badge agents-severity-${item.severity}`}>{SEVERITY_LABELS[item.severity] || item.severity}</span>
                      <span className={`agents-badge agents-status-${item.status}`}>{STATUS_LABELS[item.status] || item.status}</span>
                    </div>
                  </div>

                  <p className="agents-description">{item.description}</p>

                  {item.payload ? (
                    <pre className="agents-code-block">{prettyPayload(item.payload)}</pre>
                  ) : null}

                  {item.status === 'pending' ? (
                    <>
                      <textarea
                        className="agents-notes"
                        rows="3"
                        placeholder="Note revisione opzionali"
                        value={notesBySuggestion[item.id] || ''}
                        onChange={(event) => setNotesBySuggestion((previous) => ({
                          ...previous,
                          [item.id]: event.target.value,
                        }))}
                      />
                      <div className="agents-actions">
                        <button
                          type="button"
                          className="btn-secondary"
                          onClick={() => handleSuggestionReview(item.id, 'reject')}
                          disabled={actionLoading === `suggestion-${item.id}-reject`}
                        >
                          {actionLoading === `suggestion-${item.id}-reject` ? 'Attendi...' : 'Rifiuta'}
                        </button>
                        <button
                          type="button"
                          className="btn-primary"
                          onClick={() => handleSuggestionReview(item.id, 'accept')}
                          disabled={actionLoading === `suggestion-${item.id}-accept`}
                        >
                          {actionLoading === `suggestion-${item.id}-accept` ? 'Attendi...' : 'Accetta'}
                        </button>
                      </div>
                    </>
                  ) : (
                    <div className="agents-meta">
                      Revisionato {formatDateTime(item.reviewed_at)}
                    </div>
                  )}
                </article>
              ))}
            </div>
          )}
        </section>

        <section className="agents-panel">
          <div className="agents-panel-header">
            <h3>Bozze comunicazione</h3>
            <span className="agents-panel-note">{filteredCommunications.length} elementi</span>
          </div>

          {filteredCommunications.length === 0 ? (
            <div className="agents-empty">Nessuna bozza comunicazione disponibile.</div>
          ) : (
            <div className="agents-stack">
              {filteredCommunications.map((item) => (
                <article key={item.id} className="agents-card">
                  <div className="agents-card-top">
                    <div>
                      <strong>{item.subject}</strong>
                      <div className="agents-meta">
                        {item.recipient_name || item.recipient_email}
                        {item.recipient_id ? ` · ID ${item.recipient_id}` : ''}
                        {item.channel ? ` · ${item.channel}` : ''}
                      </div>
                    </div>
                    <span className={`agents-badge agents-status-${item.status}`}>{STATUS_LABELS[item.status] || item.status}</span>
                  </div>

                  <div className="agents-meta">
                    Run #{item.run_id || '—'} · Creata {formatDateTime(item.created_at)}
                  </div>

                  <div className="agents-mail-preview">
                    <div><strong>A:</strong> {item.recipient_email}</div>
                    <pre className="agents-code-block">{item.body}</pre>
                  </div>

                  {item.meta_payload ? (
                    <details className="agents-details">
                      <summary>Meta payload</summary>
                      <pre className="agents-code-block">{prettyPayload(item.meta_payload)}</pre>
                    </details>
                  ) : null}

                  <div className="agents-actions">
                    <button
                      type="button"
                      className="btn-secondary"
                      onClick={() => handleCommunicationStatus(item.id, 'approved')}
                      disabled={actionLoading === `communication-${item.id}-approved`}
                    >
                      {actionLoading === `communication-${item.id}-approved` ? 'Attendi...' : 'Approva'}
                    </button>
                    <button
                      type="button"
                      className="btn-primary"
                      onClick={() => handleCommunicationStatus(item.id, 'sent')}
                      disabled={actionLoading === `communication-${item.id}-sent`}
                    >
                      {actionLoading === `communication-${item.id}-sent` ? 'Attendi...' : 'Segna inviata'}
                    </button>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      </div>

      <div className="agents-footer-note">
        Utente sessione: <strong>{currentUser?.full_name || currentUser?.username || 'admin'}</strong>. Le azioni frontend
        {currentUser?.id
          ? ` registrano lo stato operativo degli agenti con audit utente attivo (ID ${currentUser.id}).`
          : ' registrano lo stato operativo degli agenti, ma non hanno ancora un `user_id` numerico disponibile in sessione.'}
      </div>
    </div>
  );
}
