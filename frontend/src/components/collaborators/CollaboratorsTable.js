import React, { useState, useEffect, useCallback, useRef } from 'react';
import { getAgentSuggestions, getCollaboratorsPaginated } from '../../services/apiService';
import CollaboratorProjectsRow from './CollaboratorProjectsRow';

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

const DISPONIBILE_OPTIONS = [
  { value: '', label: 'Tutti' },
  { value: 'true', label: 'Disponibili' },
  { value: 'false', label: 'Occupati' },
];

/** Converte i filtri correnti in URLSearchParams */
function filtersToParams(f) {
  const p = new URLSearchParams();
  if (f.search) p.set('search', f.search);
  if (f.competenza) p.set('competenza', f.competenza);
  if (f.disponibile !== '') p.set('disponibile', f.disponibile);
  if (f.citta) p.set('citta', f.citta);
  p.set('page', f.page);
  p.set('limit', f.limit);
  p.set('sort_by', f.sort_by);
  p.set('order', f.order);
  return p;
}

/** Legge i filtri iniziali dall'URL */
function filtersFromURL() {
  const p = new URLSearchParams(window.location.search);
  return {
    search: p.get('search') || '',
    competenza: p.get('competenza') || '',
    disponibile: p.get('disponibile') || '',
    citta: p.get('citta') || '',
    page: parseInt(p.get('page') || '1', 10),
    limit: parseInt(p.get('limit') || '20', 10),
    sort_by: p.get('sort_by') || 'last_name',
    order: p.get('order') || 'asc',
  };
}

/** Genera un avatar colorato basato sulle iniziali */
function AvatarInitials({ name, size = 38 }) {
  const parts = name.trim().split(' ');
  const initials = parts.length >= 2
    ? parts[0][0] + parts[parts.length - 1][0]
    : parts[0].slice(0, 2);
  const colors = ['#4361ee','#3a86ff','#7209b7','#f72585','#4cc9f0','#43aa8b','#f8961e'];
  const idx = name.charCodeAt(0) % colors.length;
  return (
    <span className="avatar-initials" style={{ background: colors[idx], width: size, height: size, fontSize: size * 0.38 }}>
      {initials.toUpperCase()}
    </span>
  );
}

/** Badge stato documento */
function DocBadge({ collaborator }) {
  if (!collaborator.documento_identita_scadenza) {
    return <span className="doc-badge missing">Doc mancante</span>;
  }
  const today = new Date(); today.setHours(0,0,0,0);
  const exp = new Date(collaborator.documento_identita_scadenza); exp.setHours(0,0,0,0);
  const diff = Math.ceil((exp - today) / 86400000);
  if (diff < 0) return <span className="doc-badge expired">Doc scaduto</span>;
  if (diff <= 30) return <span className="doc-badge warning">Scade in {diff}gg</span>;
  return <span className="doc-badge ok">Doc valido</span>;
}

/** Badge stato operativo */
function StateBadge({ collaborator }) {
  const hasActive = (collaborator.projects || []).some(p => p.status === 'active');
  const hasDoc = !!collaborator.documento_identita_scadenza;
  const exp = hasDoc ? new Date(collaborator.documento_identita_scadenza) : null;
  const docOk = exp && exp > new Date();
  if (!hasDoc || !docOk) return <span className="state-pill attention">Attenzione</span>;
  if (!hasActive) return <span className="state-pill unassigned">Senza progetto</span>;
  return <span className="state-pill covered">Operativo</span>;
}

function AgencyBadge({ collaborator }) {
  if (!collaborator.is_agency) {
    return null;
  }
  return <span className="agency-pill">Agenzia</span>;
}

function ConsultantBadge({ collaborator }) {
  if (!collaborator.is_consultant) {
    return null;
  }
  return <span className="agency-pill">Consulente</span>;
}

function AgentTaskBadge({ queue }) {
  if (!queue?.count) {
    return null;
  }
  return (
    <span className={`agent-task-pill ${queue.followupDue ? 'due' : ''}`}>
      {queue.followupDue ? 'Sollecito agente' : `${queue.count} task agente`}
    </span>
  );
}

/** Esporta CSV dei collaboratori correnti */
function exportCSV(items) {
  const headers = ['Cognome','Nome','Email','C.F.','Posizione','Città','Progetti attivi'];
  const rows = items.map(c => [
    c.last_name, c.first_name, c.email, c.fiscal_code || '',
    c.position || '', c.city || '',
    (c.projects || []).filter(p => p.status === 'active').length
  ].map(v => `"${String(v).replace(/"/g, '""')}"`).join(','));
  const csv = [headers.join(','), ...rows].join('\n');
  const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a'); a.href = url;
  a.download = `collaboratori_${new Date().toISOString().slice(0,10)}.csv`;
  a.click(); URL.revokeObjectURL(url);
}

// ─────────────────────────────────────────────────────────────────────────────
// Componente principale
// ─────────────────────────────────────────────────────────────────────────────

const CollaboratorsTable = ({
  projects,
  assignments,
  currentUser,
  onEdit,
  onDelete,
  onOpenDocuments,
  onOpenAssignmentModal,
  onAssignProject,
  onRemoveProject,
  onEditAssignment,
  onDownloadContract,
  refreshTrigger,
}) => {
  const canDeleteCollaborators = currentUser?.role === 'admin';

  // ── State ────────────────────────────────────────────────────────────────
  const [filters, setFilters] = useState(filtersFromURL);
  const [viewMode, setViewMode] = useState('list'); // 'list' | 'card'
  const [result, setResult] = useState({ items: [], total: 0, pages: 1 });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [expandedRows, setExpandedRows] = useState(new Set());
  const [agentQueueByCollaborator, setAgentQueueByCollaborator] = useState({});
  const searchTimer = useRef(null);
  const searchInputRef = useRef(null);

  // ── Fetch server-side ────────────────────────────────────────────────────
  const fetchData = useCallback(async (f) => {
    setLoading(true); setError(null);
    try {
      const params = { page: f.page, limit: f.limit, sort_by: f.sort_by, order: f.order };
      if (f.search) params.search = f.search;
      if (f.competenza) params.competenza = f.competenza;
      if (f.disponibile !== '') params.disponibile = f.disponibile === 'true';
      if (f.citta) params.citta = f.citta;
      const data = await getCollaboratorsPaginated(params);
      setResult({ items: data.items || [], total: data.total || 0, pages: data.pages || 1 });

      try {
        const agentSuggestions = await getAgentSuggestions({
          agent_name: 'data_quality',
          entity_type: 'collaborator',
          limit: 300,
        });
        const queueMap = (Array.isArray(agentSuggestions) ? agentSuggestions : [])
          .filter(item => ['pending', 'waiting', 'approved', 'sent', 'followup_due'].includes(item.status))
          .reduce((accumulator, item) => {
            if (!item.entity_id) {
              return accumulator;
            }
            accumulator[item.entity_id] = accumulator[item.entity_id] || { count: 0, followupDue: false };
            accumulator[item.entity_id].count += 1;
            if (item.status === 'followup_due') {
              accumulator[item.entity_id].followupDue = true;
            }
            return accumulator;
          }, {});
        setAgentQueueByCollaborator(queueMap);
      } catch (agentError) {
        console.error('Errore caricamento suggerimenti agenti collaboratori:', agentError);
        setAgentQueueByCollaborator({});
      }

      // Sync URL
      const urlParams = filtersToParams(f);
      window.history.replaceState(null, '', '?' + urlParams.toString());
    } catch (e) {
      setError('Errore nel caricamento collaboratori');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(filters); }, [filters, refreshTrigger, fetchData]);

  // ── Handlers filtri ──────────────────────────────────────────────────────
  const setFilter = (key, value) => setFilters(f => ({ ...f, [key]: value, page: 1 }));

  const handleSearchInput = (e) => {
    const val = e.target.value;
    clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => setFilter('search', val), 300);
  };

  const toggleSort = (col) => {
    setFilters(f => ({
      ...f,
      sort_by: col,
      order: f.sort_by === col && f.order === 'asc' ? 'desc' : 'asc',
      page: 1
    }));
  };

  const toggleRowExpansion = (id) => {
    setExpandedRows(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  // ── Keyboard shortcut Ctrl+F → focus search ──────────────────────────────
  useEffect(() => {
    const handler = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
        e.preventDefault();
        searchInputRef.current?.focus();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  // ── Unique positions (from current result set) ───────────────────────────
  const uniquePositions = [...new Set(
    result.items.map(c => c.position).filter(Boolean)
  )].sort();

  // ── Summary cards ────────────────────────────────────────────────────────
  const summary = result.items.reduce((s, c) => {
    const hasActive = (c.projects || []).some(p => p.status === 'active');
    const hasDoc = !!c.documento_identita_scadenza;
    const exp = hasDoc ? new Date(c.documento_identita_scadenza) : null;
    const docOk = exp && exp > new Date();
    if (!hasDoc || !docOk) s.attention++;
    else if (!hasActive) s.unassigned++;
    else s.covered++;
    return s;
  }, { attention: 0, unassigned: 0, covered: 0 });

  // ── SortIcon ─────────────────────────────────────────────────────────────
  const SortIcon = ({ col }) => {
    if (filters.sort_by !== col) return <span className="sort-icon">↕</span>;
    return <span className="sort-icon active">{filters.order === 'asc' ? '↑' : '↓'}</span>;
  };

  return (
    <div className="smart-collab-root">

      {/* ── Summary Cards ── */}
      <div className="collab-summary-strip">
        <button
          className={`summary-chip ${filters.disponibile === '' && !filters.search ? 'chip-total active-chip' : 'chip-total'}`}
          onClick={() => setFilter('disponibile', '')}
        >
          <span className="chip-num">{result.total}</span>
          <span className="chip-label">Totale</span>
        </button>
        <button className="summary-chip chip-attention" onClick={() => {}}>
          <span className="chip-num">{summary.attention}</span>
          <span className="chip-label">Attenzione</span>
        </button>
        <button
          className={`summary-chip chip-unassigned ${filters.disponibile === 'false' ? 'active-chip' : ''}`}
          onClick={() => setFilter('disponibile', filters.disponibile === 'false' ? '' : 'false')}
        >
          <span className="chip-num">{summary.unassigned}</span>
          <span className="chip-label">Senza progetto</span>
        </button>
        <button
          className={`summary-chip chip-covered ${filters.disponibile === 'true' ? 'active-chip' : ''}`}
          onClick={() => setFilter('disponibile', filters.disponibile === 'true' ? '' : 'true')}
        >
          <span className="chip-num">{summary.covered}</span>
          <span className="chip-label">Operativi</span>
        </button>
      </div>

      {/* ── Sticky Filter Bar ── */}
      <div className="smart-filter-bar">
        <div className="filter-bar-main">
          <div className="search-wrap">
            <span className="search-icon">🔍</span>
            <input
              ref={searchInputRef}
              className="smart-search-input"
              placeholder="Cerca nome, cognome, email, CF, posizione… (Ctrl+F)"
              defaultValue={filters.search}
              onChange={handleSearchInput}
            />
          </div>
          <select className="filter-select-sm" value={filters.competenza}
            onChange={e => setFilter('competenza', e.target.value)}>
            <option value="">Tutte le competenze</option>
            {uniquePositions.map(p => <option key={p} value={p}>{p}</option>)}
          </select>
          <select className="filter-select-sm" value={filters.disponibile}
            onChange={e => setFilter('disponibile', e.target.value)}>
            {DISPONIBILE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
          <input className="filter-select-sm" placeholder="Città…"
            value={filters.citta} onChange={e => setFilter('citta', e.target.value)} />
        </div>
        <div className="filter-bar-right">
          <span className="collab-counter">
            {loading ? '…' : `${result.total} collaboratori`}
          </span>
          <button className="view-toggle-btn" title="Vista lista"
            onClick={() => setViewMode('list')}
            data-active={viewMode === 'list'}>
            ☰
          </button>
          <button className="view-toggle-btn" title="Vista card"
            onClick={() => setViewMode('card')}
            data-active={viewMode === 'card'}>
            ⊞
          </button>
          <button className="btn-export" title="Esporta CSV"
            onClick={() => exportCSV(result.items)}
            disabled={result.items.length === 0}>
            ↓ CSV
          </button>
        </div>
      </div>

      {error && <div className="smart-error">{error}</div>}

      {/* ── Content ── */}
      {loading && result.items.length === 0 ? (
        <div className="smart-loading">Caricamento…</div>
      ) : result.items.length === 0 ? (
        <div className="smart-empty">
          <div>👥</div>
          <p>Nessun collaboratore trovato.</p>
          {(filters.search || filters.competenza || filters.disponibile || filters.citta) && (
            <button className="btn-sm btn-secondary"
              onClick={() => setFilters(f => ({ ...f, search: '', competenza: '', disponibile: '', citta: '', page: 1 }))}>
              Rimuovi filtri
            </button>
          )}
        </div>
      ) : viewMode === 'card' ? (
        <CardView
          items={result.items}
          currentUser={currentUser}
          onEdit={onEdit}
          onOpenAssignmentModal={onOpenAssignmentModal}
          onDelete={onDelete}
          canDelete={canDeleteCollaborators}
          agentQueueByCollaborator={agentQueueByCollaborator}
        />
      ) : (
        <ListView
          items={result.items}
          projects={projects}
          assignments={assignments}
          currentUser={currentUser}
          filters={filters}
          expandedRows={expandedRows}
          canDelete={canDeleteCollaborators}
          onEdit={onEdit}
          onDelete={onDelete}
          onOpenDocuments={onOpenDocuments}
          onOpenAssignmentModal={onOpenAssignmentModal}
          onAssignProject={onAssignProject}
          onRemoveProject={onRemoveProject}
          onEditAssignment={onEditAssignment}
          onDownloadContract={onDownloadContract}
          agentQueueByCollaborator={agentQueueByCollaborator}
          toggleSort={toggleSort}
          toggleRowExpansion={toggleRowExpansion}
          SortIcon={SortIcon}
        />
      )}

      {/* ── Paginazione ── */}
      {result.pages > 1 && (
        <div className="smart-pagination">
          <button disabled={filters.page <= 1}
            onClick={() => setFilters(f => ({ ...f, page: 1 }))}>⏮</button>
          <button disabled={filters.page <= 1}
            onClick={() => setFilters(f => ({ ...f, page: f.page - 1 }))}>‹</button>
          <span>Pag. {filters.page} / {result.pages}</span>
          <button disabled={filters.page >= result.pages}
            onClick={() => setFilters(f => ({ ...f, page: f.page + 1 }))}>›</button>
          <button disabled={filters.page >= result.pages}
            onClick={() => setFilters(f => ({ ...f, page: result.pages }))}>⏭</button>
          <select className="filter-select-sm" value={filters.limit}
            onChange={e => setFilters(f => ({ ...f, limit: Number(e.target.value), page: 1 }))}>
            {[10, 20, 50, 100].map(n => <option key={n} value={n}>{n} per pagina</option>)}
          </select>
        </div>
      )}
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// Card View
// ─────────────────────────────────────────────────────────────────────────────
const CardView = ({ items, currentUser, onEdit, onOpenAssignmentModal, onDelete, canDelete, agentQueueByCollaborator }) => (
  <div className="collab-card-grid">
    {items.map(c => {
      const activeProjects = (c.projects || []).filter(p => p.status === 'active');
      return (
        <div key={c.id} className="collab-card">
          <div className="collab-card-top">
            <AvatarInitials name={`${c.first_name} ${c.last_name}`} size={44} />
            <div className="collab-card-info">
              <strong>{c.last_name} {c.first_name}</strong>
              <AgencyBadge collaborator={c} />
              <ConsultantBadge collaborator={c} />
              <AgentTaskBadge queue={agentQueueByCollaborator[c.id]} />
              {c.position && <span className="position-tag">{c.position}</span>}
            </div>
            <StateBadge collaborator={c} />
          </div>
          {c.city && <div className="collab-card-meta">📍 {c.city}</div>}
          <div className="collab-card-meta">
            📁 {activeProjects.length} progett{activeProjects.length === 1 ? 'o' : 'i'} attiv{activeProjects.length === 1 ? 'o' : 'i'}
          </div>
          <DocBadge collaborator={c} />
          <div className="collab-card-actions">
            {c.email && (
              <a href={`mailto:${c.email}`} className="btn-sm btn-icon" title="Invia email">✉</a>
            )}
            {c.phone && (
              <a href={`tel:${c.phone}`} className="btn-sm btn-icon" title="Chiama">📞</a>
            )}
            <button className="btn-sm btn-secondary" onClick={() => onEdit(c)}>Modifica</button>
            <button className="btn-sm btn-primary" onClick={() => onOpenAssignmentModal(c)}>+ Assegna</button>
            {canDelete && (
              <button className="btn-sm btn-danger" onClick={() => onDelete(c.id)}>🗑</button>
            )}
          </div>
        </div>
      );
    })}
  </div>
);

// ─────────────────────────────────────────────────────────────────────────────
// List View (tabella densa con righe espandibili)
// ─────────────────────────────────────────────────────────────────────────────
const ListView = ({
  items, projects, assignments, currentUser, filters, expandedRows,
  canDelete, onEdit, onDelete, onOpenDocuments, onOpenAssignmentModal, onAssignProject,
  onRemoveProject, onEditAssignment, onDownloadContract, agentQueueByCollaborator,
  toggleSort, toggleRowExpansion, SortIcon
}) => (
  <div className="collab-table-wrap">
    <table className="data-table compact-table">
      <thead>
        <tr>
          <th></th>
          <th className="sortable" onClick={() => toggleSort('last_name')}>
            Cognome / Nome <SortIcon col="last_name" />
          </th>
          <th className="sortable" onClick={() => toggleSort('position')}>
            Posizione <SortIcon col="position" />
          </th>
          <th className="sortable" onClick={() => toggleSort('city')}>
            Città <SortIcon col="city" />
          </th>
          <th>Documenti</th>
          <th>Stato</th>
          <th>Progetti</th>
          <th className="actions-column">Azioni</th>
        </tr>
      </thead>
      <tbody>
        {items.map(c => {
          const isExpanded = expandedRows.has(c.id);
          const activeProjects = (c.projects || []).filter(p => p.status === 'active');
          const assignedIds = (c.projects || []).map(p => p.id);
          const availableProjects = (projects || []).filter(p => !assignedIds.includes(p.id));

          return (
            <React.Fragment key={c.id}>
              <tr className="collaborator-row">
                <td>
                  <AvatarInitials name={`${c.first_name} ${c.last_name}`} size={32} />
                </td>
                <td className="name-cell">
                  <strong>{c.last_name} {c.first_name}</strong>
                  <div className="inline-badges">
                    <AgencyBadge collaborator={c} />
                    <ConsultantBadge collaborator={c} />
                    <AgentTaskBadge queue={agentQueueByCollaborator[c.id]} />
                  </div>
                  <div className="sub-text">{c.email}</div>
                  {c.fiscal_code && <div className="sub-text mono">{c.fiscal_code}</div>}
                </td>
                <td>{c.position || <span className="text-muted">—</span>}</td>
                <td>{c.city || <span className="text-muted">—</span>}</td>
                <td>
                  <DocBadge collaborator={c} />
                  <div className="doc-files-mini">
                    <span className={c.curriculum_filename ? 'file-ok' : 'file-missing'}>CV</span>
                    <span className={c.documento_identita_filename ? 'file-ok' : 'file-missing'}>Doc</span>
                  </div>
                </td>
                <td><StateBadge collaborator={c} /></td>
                <td>
                  <div className="projects-compact">
                    <span>{activeProjects.length} attivi / {(c.projects || []).length} tot</span>
                    {(c.projects || []).length > 0 && (
                      <button className="expand-btn" onClick={() => toggleRowExpansion(c.id)}>
                        {isExpanded ? 'Nascondi' : 'Dettaglio'}
                      </button>
                    )}
                  </div>
                </td>
                <td className="actions-cell">
                  <button className="action-btn assign-btn" onClick={() => onOpenDocuments(c)} title="Documenti">📄</button>
                  <button className="action-btn edit-btn" onClick={() => onEdit(c)}>✏️</button>
                  <button className="action-btn assign-btn" onClick={() => onOpenAssignmentModal(c)}>➕</button>
                  <button className="action-btn delete-btn" onClick={() => onDelete(c.id)}
                    disabled={!canDelete} title={canDelete ? 'Elimina' : 'Solo admin'}>🗑️</button>
                </td>
              </tr>
              {isExpanded && (
                <CollaboratorProjectsRow
                  collaborator={c}
                  projects={projects}
                  assignments={assignments}
                  availableProjects={availableProjects}
                  onAssignProject={onAssignProject}
                  onRemoveProject={onRemoveProject}
                  onOpenAssignmentModal={onOpenAssignmentModal}
                  onEditAssignment={onEditAssignment}
                  onDownloadContract={onDownloadContract}
                  currentUser={currentUser}
                />
              )}
            </React.Fragment>
          );
        })}
      </tbody>
    </table>
  </div>
);

export default CollaboratorsTable;
