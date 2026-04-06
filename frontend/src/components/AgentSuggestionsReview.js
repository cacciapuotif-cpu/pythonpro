import React, { useEffect, useMemo, useState } from 'react';
import {
  applyAgentSuggestionFix,
  bulkReviewAgentSuggestions,
  getAgentRuns,
  getAgentSuggestionDetail,
  getAgentSuggestions,
  getCollaborators,
  getPendingAgentSuggestions,
  getProjects,
  reviewAgentSuggestion,
} from '../services/apiService';
import './AgentsManager.css';

const PRIORITY_META = {
  critical: { label: 'Critica', color: '#991b1b', background: '#fee2e2' },
  high: { label: 'Alta', color: '#9a3412', background: '#ffedd5' },
  medium: { label: 'Media', color: '#92400e', background: '#fef3c7' },
  low: { label: 'Bassa', color: '#475569', background: '#e2e8f0' },
};

const STATUS_OPTIONS = ['pending', 'approved', 'rejected', 'implemented'];
const PRIORITY_OPTIONS = ['critical', 'high', 'medium', 'low'];
const ENTITY_OPTIONS = ['collaborator', 'project', 'assignment', 'attendance', 'document'];

const overlayStyle = {
  position: 'fixed',
  inset: 0,
  background: 'rgba(15, 23, 42, 0.45)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  padding: '1.5rem',
  zIndex: 1100,
};

const modalStyle = {
  width: 'min(960px, 100%)',
  maxHeight: '90vh',
  overflow: 'auto',
  background: '#fff',
  borderRadius: '20px',
  border: '1px solid #dbe4f0',
  boxShadow: '0 24px 60px rgba(15, 23, 42, 0.18)',
  padding: '1.5rem',
};

const badgeStyle = (priority) => {
  const meta = PRIORITY_META[priority] || PRIORITY_META.low;
  return {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '0.32rem 0.7rem',
    borderRadius: '999px',
    fontSize: '0.78rem',
    fontWeight: 700,
    color: meta.color,
    background: meta.background,
  };
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

const getEntityLabel = (suggestion, collaboratorsMap, projectsMap) => {
  if (suggestion.entity_type === 'collaborator') {
    const collaborator = collaboratorsMap.get(String(suggestion.entity_id));
    const name = collaborator
      ? `${collaborator.first_name || ''} ${collaborator.last_name || ''}`.trim()
      : `ID ${suggestion.entity_id || 'N/D'}`;
    return { href: '/collaborators', text: `Collaboratore: ${name}` };
  }
  if (suggestion.entity_type === 'project') {
    const project = projectsMap.get(String(suggestion.entity_id));
    return { href: '/projects', text: `Progetto: ${project?.name || `ID ${suggestion.entity_id || 'N/D'}`}` };
  }
  return { href: '#', text: `${suggestion.entity_type || 'Entità'}: ${suggestion.entity_id || 'N/D'}` };
};

const defaultDetailState = {
  note: '',
  action: 'approve',
};

export default function AgentSuggestionsReview({ currentUser = null }) {
  const [suggestions, setSuggestions] = useState([]);
  const [pendingSuggestions, setPendingSuggestions] = useState([]);
  const [runs, setRuns] = useState([]);
  const [collaborators, setCollaborators] = useState([]);
  const [projects, setProjects] = useState([]);
  const [filters, setFilters] = useState({
    status: '',
    priority: '',
    entity_type: '',
    agent_type: '',
  });
  const [selectedIds, setSelectedIds] = useState([]);
  const [detailSuggestion, setDetailSuggestion] = useState(null);
  const [detailForm, setDetailForm] = useState(defaultDetailState);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  const collaboratorsMap = useMemo(
    () => new Map((collaborators || []).map((item) => [String(item.id), item])),
    [collaborators],
  );
  const projectsMap = useMemo(
    () => new Map((projects || []).map((item) => [String(item.id), item])),
    [projects],
  );
  const runsMap = useMemo(
    () => new Map((runs || []).map((item) => [String(item.id), item])),
    [runs],
  );

  const loadData = async () => {
    setLoading(true);
    setError('');
    try {
      const [allSuggestions, onlyPending, runsData, collaboratorsData, projectsData] = await Promise.all([
        getAgentSuggestions({ limit: 300 }),
        getPendingAgentSuggestions(),
        getAgentRuns({ limit: 300 }),
        getCollaborators(0, 300),
        getProjects(0, 300),
      ]);
      setSuggestions(Array.isArray(allSuggestions) ? allSuggestions : []);
      setPendingSuggestions(Array.isArray(onlyPending) ? onlyPending : []);
      setRuns(Array.isArray(runsData) ? runsData : []);
      setCollaborators(Array.isArray(collaboratorsData) ? collaboratorsData : []);
      setProjects(Array.isArray(projectsData) ? projectsData : []);
    } catch (loadError) {
      setError(loadError?.response?.data?.detail || 'Errore nel caricamento suggerimenti agenti.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const enrichedSuggestions = useMemo(() => (
    suggestions.map((suggestion) => ({
      ...suggestion,
      run: suggestion.run || runsMap.get(String(suggestion.run_id)) || null,
      agent_type: suggestion.run?.agent_type || runsMap.get(String(suggestion.run_id))?.agent_type || '',
    }))
  ), [runsMap, suggestions]);

  const filteredSuggestions = useMemo(() => (
    enrichedSuggestions.filter((suggestion) => {
      if (filters.status && suggestion.status !== filters.status) {
        return false;
      }
      if (filters.priority && suggestion.priority !== filters.priority) {
        return false;
      }
      if (filters.entity_type && suggestion.entity_type !== filters.entity_type) {
        return false;
      }
      if (filters.agent_type && suggestion.agent_type !== filters.agent_type) {
        return false;
      }
      return true;
    })
  ), [enrichedSuggestions, filters]);

  const pendingCounters = useMemo(() => {
    const counters = { total: pendingSuggestions.length, critical: 0, high: 0, medium: 0, low: 0 };
    pendingSuggestions.forEach((item) => {
      counters[item.priority] = (counters[item.priority] || 0) + 1;
    });
    return counters;
  }, [pendingSuggestions]);

  const availableAgentTypes = useMemo(
    () => [...new Set(enrichedSuggestions.map((item) => item.agent_type).filter(Boolean))].sort(),
    [enrichedSuggestions],
  );

  const toggleSelection = (suggestionId) => {
    setSelectedIds((current) => (
      current.includes(suggestionId)
        ? current.filter((id) => id !== suggestionId)
        : [...current, suggestionId]
    ));
  };

  const toggleSelectAllVisible = () => {
    const visibleIds = filteredSuggestions.filter((item) => item.status === 'pending').map((item) => item.id);
    if (visibleIds.length && visibleIds.every((id) => selectedIds.includes(id))) {
      setSelectedIds((current) => current.filter((id) => !visibleIds.includes(id)));
      return;
    }
    setSelectedIds((current) => [...new Set([...current, ...visibleIds])]);
  };

  const openDetail = async (suggestionId) => {
    setActionLoading(`detail-${suggestionId}`);
    setError('');
    try {
      const detail = await getAgentSuggestionDetail(suggestionId);
      setDetailSuggestion(detail);
      setDetailForm(defaultDetailState);
    } catch (detailError) {
      setError(detailError?.response?.data?.detail || 'Errore nel caricamento dettaglio suggerimento.');
    } finally {
      setActionLoading('');
    }
  };

  const handleSingleReview = async (suggestionId, action, notes = '') => {
    setActionLoading(`${action}-${suggestionId}`);
    setError('');
    try {
      await reviewAgentSuggestion(suggestionId, {
        action,
        reviewed_by: currentUser?.username || currentUser?.email || 'operator',
        notes: notes || undefined,
      });
      setMessage(`Suggerimento ${action === 'reject' ? 'rifiutato' : 'approvato'} con successo.`);
      await loadData();
      if (detailSuggestion && detailSuggestion.id === suggestionId) {
        const refreshed = await getAgentSuggestionDetail(suggestionId);
        setDetailSuggestion(refreshed);
      }
    } catch (reviewError) {
      setError(reviewError?.response?.data?.detail || 'Errore nella review del suggerimento.');
    } finally {
      setActionLoading('');
    }
  };

  const handleApplyFix = async (suggestionId) => {
    setActionLoading(`fix-${suggestionId}`);
    setError('');
    try {
      await applyAgentSuggestionFix(suggestionId);
      setMessage('Fix automatico applicato con successo.');
      await loadData();
      if (detailSuggestion && detailSuggestion.id === suggestionId) {
        const refreshed = await getAgentSuggestionDetail(suggestionId);
        setDetailSuggestion(refreshed);
      }
    } catch (fixError) {
      setError(fixError?.response?.data?.detail || 'Errore durante l’applicazione del fix automatico.');
    } finally {
      setActionLoading('');
    }
  };

  const handleBulkReview = async (action) => {
    if (!selectedIds.length) {
      return;
    }
    setActionLoading(`bulk-${action}`);
    setError('');
    try {
      await bulkReviewAgentSuggestions({
        suggestion_ids: selectedIds,
        action,
        reviewed_by: currentUser?.username || currentUser?.email || 'operator',
        notes: null,
      });
      setMessage(`Suggerimenti selezionati ${action === 'reject' ? 'rifiutati' : 'approvati'} con successo.`);
      setSelectedIds([]);
      await loadData();
    } catch (bulkError) {
      setError(bulkError?.response?.data?.detail || 'Errore nella review multipla.');
    } finally {
      setActionLoading('');
    }
  };

  const submitDetailReview = async (event) => {
    event.preventDefault();
    if (!detailSuggestion) {
      return;
    }
    await handleSingleReview(detailSuggestion.id, detailForm.action, detailForm.note);
  };

  return (
    <div className="agents-page">
      <div className="agents-header">
        <div>
          <span className="agents-eyebrow">Review suggerimenti AI</span>
          <h2>Agent Suggestions Review</h2>
          <p>Code operative, bulk review e applicazione fix automatici sui suggerimenti agentici.</p>
        </div>
      </div>

      {message ? <div className="agents-banner success">{message}</div> : null}
      {error ? <div className="agents-banner error">{error}</div> : null}

      <section className="agents-grid agents-grid--compact">
        <article className="agents-card">
          <span className="agents-card-label">Pending Totali</span>
          <strong className="agents-card-value">{pendingCounters.total}</strong>
        </article>
        {PRIORITY_OPTIONS.map((priority) => (
          <article className="agents-card" key={priority}>
            <span className="agents-card-label">{PRIORITY_META[priority].label}</span>
            <div style={badgeStyle(priority)}>{pendingCounters[priority] || 0}</div>
          </article>
        ))}
      </section>

      <section className="agents-panel">
        <div className="agents-toolbar">
          <label>
            <span>Status</span>
            <select value={filters.status} onChange={(event) => setFilters((current) => ({ ...current, status: event.target.value }))}>
              <option value="">Tutti</option>
              {STATUS_OPTIONS.map((status) => (
                <option key={status} value={status}>{status}</option>
              ))}
            </select>
          </label>
          <label>
            <span>Priority</span>
            <select value={filters.priority} onChange={(event) => setFilters((current) => ({ ...current, priority: event.target.value }))}>
              <option value="">Tutte</option>
              {PRIORITY_OPTIONS.map((priority) => (
                <option key={priority} value={priority}>{priority}</option>
              ))}
            </select>
          </label>
          <label>
            <span>Entity Type</span>
            <select value={filters.entity_type} onChange={(event) => setFilters((current) => ({ ...current, entity_type: event.target.value }))}>
              <option value="">Tutti</option>
              {ENTITY_OPTIONS.map((entityType) => (
                <option key={entityType} value={entityType}>{entityType}</option>
              ))}
            </select>
          </label>
          <label>
            <span>Agent Type</span>
            <select value={filters.agent_type} onChange={(event) => setFilters((current) => ({ ...current, agent_type: event.target.value }))}>
              <option value="">Tutti</option>
              {availableAgentTypes.map((agentType) => (
                <option key={agentType} value={agentType}>{agentType}</option>
              ))}
            </select>
          </label>
          <button className="btn btn-secondary" type="button" onClick={loadData} disabled={loading}>
            {loading ? 'Aggiornamento...' : 'Aggiorna'}
          </button>
        </div>
      </section>

      <section className="agents-panel">
        <div className="agents-toolbar">
          <div className="agents-bulk-actions">
            <label className="agents-checkbox">
              <input
                type="checkbox"
                checked={filteredSuggestions.filter((item) => item.status === 'pending').length > 0
                  && filteredSuggestions.filter((item) => item.status === 'pending').every((item) => selectedIds.includes(item.id))}
                onChange={toggleSelectAllVisible}
              />
              <span>Seleziona visibili pending</span>
            </label>
            <button className="btn btn-primary" type="button" onClick={() => handleBulkReview('approve')} disabled={!selectedIds.length || Boolean(actionLoading)}>
              Approva selezionati
            </button>
            <button className="btn btn-secondary" type="button" onClick={() => handleBulkReview('reject')} disabled={!selectedIds.length || Boolean(actionLoading)}>
              Rifiuta selezionati
            </button>
          </div>
          <div className="agents-meta">{filteredSuggestions.length} suggerimenti nei filtri correnti</div>
        </div>

        <div className="agents-list">
          {filteredSuggestions.map((suggestion) => {
            const entityLink = getEntityLabel(suggestion, collaboratorsMap, projectsMap);
            return (
              <article className="agents-suggestion-card" key={suggestion.id}>
                <div className="agents-suggestion-header">
                  <label className="agents-checkbox">
                    <input
                      type="checkbox"
                      checked={selectedIds.includes(suggestion.id)}
                      disabled={suggestion.status !== 'pending'}
                      onChange={() => toggleSelection(suggestion.id)}
                    />
                    <span />
                  </label>
                  <div style={badgeStyle(suggestion.priority)}>{PRIORITY_META[suggestion.priority]?.label || suggestion.priority}</div>
                  <span className="agents-status-pill">{suggestion.status}</span>
                  <span className="agents-meta">{suggestion.agent_type || '—'}</span>
                </div>

                <div className="agents-suggestion-content">
                  <h3>{suggestion.title}</h3>
                  <p>{suggestion.description || 'Nessuna descrizione disponibile.'}</p>
                  <a href={entityLink.href} className="agents-inline-link">{entityLink.text}</a>
                  <div className="agents-meta">Creato il {formatDateTime(suggestion.created_at)}</div>
                </div>

                <div className="agents-actions">
                  <button
                    className="btn btn-primary"
                    type="button"
                    disabled={suggestion.status !== 'pending' || Boolean(actionLoading)}
                    onClick={() => handleSingleReview(suggestion.id, 'approve')}
                  >
                    Approva
                  </button>
                  <button
                    className="btn btn-secondary"
                    type="button"
                    disabled={suggestion.status !== 'pending' || Boolean(actionLoading)}
                    onClick={() => handleSingleReview(suggestion.id, 'reject')}
                  >
                    Rifiuta
                  </button>
                  <button
                    className="btn btn-ghost"
                    type="button"
                    disabled={Boolean(actionLoading)}
                    onClick={() => openDetail(suggestion.id)}
                  >
                    {actionLoading === `detail-${suggestion.id}` ? 'Caricamento...' : 'Visualizza dettagli'}
                  </button>
                  {suggestion.auto_fix_available ? (
                    <button
                      className="btn btn-success"
                      type="button"
                      disabled={Boolean(actionLoading)}
                      onClick={() => handleApplyFix(suggestion.id)}
                    >
                      Applica Fix Automatico
                    </button>
                  ) : null}
                </div>
              </article>
            );
          })}

          {!loading && filteredSuggestions.length === 0 ? (
            <div className="agents-empty-state">Nessun suggerimento disponibile per i filtri correnti.</div>
          ) : null}
        </div>
      </section>

      {detailSuggestion ? (
        <div style={overlayStyle}>
          <div style={modalStyle}>
            <div className="agents-modal-header">
              <div>
                <span className="agents-eyebrow">Dettaglio suggerimento</span>
                <h3>{detailSuggestion.title}</h3>
              </div>
              <button className="btn btn-ghost" type="button" onClick={() => setDetailSuggestion(null)}>Chiudi</button>
            </div>

            <div className="agents-detail-grid">
              <div className="agents-detail-card">
                <strong>Meta</strong>
                <p>Tipo: {detailSuggestion.suggestion_type}</p>
                <p>Priority: {detailSuggestion.priority}</p>
                <p>Status: {detailSuggestion.status}</p>
                <p>Agent Type: {detailSuggestion.run?.agent_type || runsMap.get(String(detailSuggestion.run_id))?.agent_type || '—'}</p>
                <p>Entity: {detailSuggestion.entity_type} #{detailSuggestion.entity_id || '—'}</p>
                <p>Creato: {formatDateTime(detailSuggestion.created_at)}</p>
                <p>Confidence: {detailSuggestion.confidence_score ?? '—'}</p>
              </div>
              <div className="agents-detail-card">
                <strong>Descrizione</strong>
                <p>{detailSuggestion.description || 'Nessuna descrizione disponibile.'}</p>
                <strong>Azione suggerita</strong>
                <p>{detailSuggestion.suggested_action || 'Nessuna azione suggerita.'}</p>
                <strong>Auto-fix</strong>
                <p>{detailSuggestion.auto_fix_available ? 'Disponibile' : 'Non disponibile'}</p>
                {detailSuggestion.auto_fix_payload ? (
                  <pre className="agents-code-block">{detailSuggestion.auto_fix_payload}</pre>
                ) : null}
              </div>
            </div>

            <div className="agents-detail-card">
              <strong>Storico Review Actions</strong>
              <div className="agents-review-log">
                {(detailSuggestion.review_actions || []).length === 0 ? (
                  <p>Nessuna review action registrata.</p>
                ) : (
                  detailSuggestion.review_actions.map((action) => (
                    <article key={action.id} className="agents-review-item">
                      <div className="agents-meta">
                        {action.action} · {formatDateTime(action.created_at)}
                      </div>
                      <p>Reviewed by: {action.reviewed_by ?? action.reviewed_by_user_id ?? '—'}</p>
                      <p>Note: {action.notes || '—'}</p>
                    </article>
                  ))
                )}
              </div>
            </div>

            <form className="agents-detail-card" onSubmit={submitDetailReview}>
              <strong>Aggiungi nota e azione</strong>
              <div className="agents-toolbar">
                <label>
                  <span>Azione</span>
                  <select value={detailForm.action} onChange={(event) => setDetailForm((current) => ({ ...current, action: event.target.value }))}>
                    <option value="approve">Approva</option>
                    <option value="reject">Rifiuta</option>
                  </select>
                </label>
                <label className="agents-grow">
                  <span>Nota</span>
                  <textarea
                    rows="4"
                    value={detailForm.note}
                    onChange={(event) => setDetailForm((current) => ({ ...current, note: event.target.value }))}
                  />
                </label>
              </div>
              <div className="agents-actions">
                <button className="btn btn-primary" type="submit" disabled={Boolean(actionLoading)}>
                  Salva review
                </button>
                {detailSuggestion.auto_fix_available ? (
                  <button className="btn btn-success" type="button" disabled={Boolean(actionLoading)} onClick={() => handleApplyFix(detailSuggestion.id)}>
                    Applica Fix Automatico
                  </button>
                ) : null}
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </div>
  );
}
