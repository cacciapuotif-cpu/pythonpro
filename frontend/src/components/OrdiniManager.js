import React, { useState, useEffect, useCallback } from 'react';
import { deleteOrdine, getOrdini, updateOrdine } from '../services/apiService';
import './OrdiniManager.css';

const fmtDate = (d) => d ? new Date(d).toLocaleDateString('it-IT') : '—';

const STATO_CONFIG = {
  in_lavorazione: { label: 'In lavorazione', color: '#d97706', bg: '#fef3c7' },
  completato:     { label: 'Completato',     color: '#16a34a', bg: '#dcfce7' },
  annullato:      { label: 'Annullato',      color: '#dc2626', bg: '#fee2e2' },
};

const StatoBadge = ({ stato }) => {
  const cfg = STATO_CONFIG[stato] || { label: stato, color: '#666', bg: '#f1f5f9' };
  return (
    <span className="stato-badge" style={{ color: cfg.color, background: cfg.bg }}>
      {cfg.label}
    </span>
  );
};

export default function OrdiniManager() {
  const [ordini, setOrdini] = useState([]);
  const [total, setTotal] = useState(0);
  const [filters, setFilters] = useState({ search: '', stato: '', page: 1, limit: 20 });
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(null);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = { limit: filters.limit, skip: (filters.page - 1) * filters.limit };
      if (filters.search) params.search = filters.search;
      if (filters.stato) params.stato = filters.stato;
      const data = await getOrdini(params);
      setOrdini(data.items || []);
      setTotal(data.total || 0);
    } catch { setError('Errore caricamento ordini'); }
    finally { setLoading(false); }
  }, [filters]);

  useEffect(() => { load(); }, [load]);

  const toast = (msg, type = 'success') => {
    type === 'success' ? setSuccess(msg) : setError(msg);
    setTimeout(() => { setSuccess(null); setError(null); }, 3500);
  };

  const handleUpdateStato = async (ordine, nuovoStato) => {
    try {
      await updateOrdine(ordine.id, { stato: nuovoStato });
      toast(`Ordine aggiornato: ${STATO_CONFIG[nuovoStato]?.label}`);
      load();
    } catch (e) { toast(e?.response?.data?.detail || 'Errore', 'error'); }
  };

  const handleDelete = async (ordineId) => {
    if (!window.confirm('Sei sicuro di voler annullare questo ordine?')) {
      return;
    }

    try {
      await deleteOrdine(ordineId);
      toast('Ordine annullato');
      load();
    } catch (e) {
      toast(e?.response?.data?.detail || 'Errore annullamento ordine', 'error');
    }
  };

  const pages = Math.ceil(total / filters.limit) || 1;

  return (
    <div className="ordini-manager">
      <div className="ordini-header">
        <div>
          <h2>Ordini</h2>
          <span className="count-badge">{total} ordini</span>
        </div>
      </div>

      {success && <div className="toast toast-success">{success}</div>}
      {error && <div className="toast toast-error">{error}</div>}

      {/* Filtri */}
      <div className="ordini-filters">
        <input className="search-input" placeholder="Cerca numero…"
          value={filters.search}
          onChange={e => setFilters(f => ({ ...f, search: e.target.value, page: 1 }))} />
        <select className="filter-select-sm" value={filters.stato}
          onChange={e => setFilters(f => ({ ...f, stato: e.target.value, page: 1 }))}>
          <option value="">Tutti gli stati</option>
          <option value="in_lavorazione">In lavorazione</option>
          <option value="completato">Completato</option>
          <option value="annullato">Annullato</option>
        </select>
      </div>

      {loading ? <div className="loading-spinner">Caricamento…</div> : (
        <div className="ordini-table-wrap">
          <table className="ordini-table">
            <thead>
              <tr>
                <th>Numero</th>
                <th>Cliente</th>
                <th>Da preventivo</th>
                <th>Stato</th>
                <th>Creato il</th>
                <th>Note</th>
                <th>Azioni</th>
              </tr>
            </thead>
            <tbody>
              {ordini.length === 0 && (
                <tr><td colSpan={7} className="empty-state">Nessun ordine trovato.</td></tr>
              )}
              {ordini.map(o => (
                <tr key={o.id}>
                  <td><span className="ordine-numero">{o.numero}</span></td>
                  <td>{o.azienda_cliente?.ragione_sociale || <span className="muted">—</span>}</td>
                  <td>
                    {o.preventivo
                      ? <span className="prev-link">{o.preventivo.numero}</span>
                      : <span className="muted">—</span>}
                  </td>
                  <td><StatoBadge stato={o.stato} /></td>
                  <td className="muted">{fmtDate(o.created_at)}</td>
                  <td className="muted note-cell">{o.note || '—'}</td>
                  <td>
                    <div className="row-actions">
                      {o.stato === 'in_lavorazione' && (
                        <button className="btn-sm btn-success"
                          onClick={() => handleUpdateStato(o, 'completato')}>Completa</button>
                      )}
                      {o.stato === 'in_lavorazione' && (
                        <button className="btn-sm btn-danger"
                          onClick={() => handleDelete(o.id)}>Annulla</button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {pages > 1 && (
        <div className="pagination">
          <button disabled={filters.page === 1} onClick={() => setFilters(f => ({ ...f, page: f.page - 1 }))}>‹</button>
          <span>{filters.page} / {pages}</span>
          <button disabled={filters.page >= pages} onClick={() => setFilters(f => ({ ...f, page: f.page + 1 }))}>›</button>
        </div>
      )}
    </div>
  );
}
