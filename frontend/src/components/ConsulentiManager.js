import React, { useState, useEffect, useCallback } from 'react';
import {
  getConsulenti, createConsulente, updateConsulente, deleteConsulente,
  getAgenzie
} from '../services/apiService';
import './ConsulentiManager.css';

const EMPTY_FORM = {
  nome: '', cognome: '', email: '', telefono: '', partita_iva: '',
  agenzia_id: '', zona_competenza: '', provvigione_percentuale: '', note: '', attivo: true
};

export default function ConsulentiManager() {
  const [result, setResult] = useState({ items: [], total: 0, pages: 1 });
  const [agenzie, setAgenzie] = useState([]);
  const [filters, setFilters] = useState({ search: '', page: 1, limit: 20 });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [modal, setModal] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [formErrors, setFormErrors] = useState({});

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = { page: filters.page, limit: filters.limit };
      if (filters.search) params.search = filters.search;
      const data = await getConsulenti(params);
      setResult({
        items: data.items || [],
        total: data.total || 0,
        pages: data.pages || 1,
      });
    } catch {
      setError('Errore nel caricamento consulenti');
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    getAgenzie({ limit: 200 }).then(d => setAgenzie(Array.isArray(d) ? d : d.items || [])).catch(() => {});
  }, []);

  const showToast = (msg, type = 'success') => {
    if (type === 'success') setSuccess(msg);
    else setError(msg);
    setTimeout(() => { setSuccess(null); setError(null); }, 3500);
  };

  const openCreate = () => {
    setForm(EMPTY_FORM);
    setFormErrors({});
    setModal({ mode: 'create' });
  };

  const openEdit = (c) => {
    setForm({
      nome: c.nome, cognome: c.cognome, email: c.email || '',
      telefono: c.telefono || '', partita_iva: c.partita_iva || '',
      agenzia_id: c.agenzia_id || '', zona_competenza: c.zona_competenza || '',
      provvigione_percentuale: c.provvigione_percentuale ?? '', note: c.note || '',
      attivo: c.attivo
    });
    setFormErrors({});
    setModal({ mode: 'edit', data: c });
  };

  const validateForm = () => {
    const errs = {};
    if (!form.nome.trim()) errs.nome = 'Nome obbligatorio';
    if (!form.cognome.trim()) errs.cognome = 'Cognome obbligatorio';
    if (form.email && !/^[^@]+@[^@]+\.[^@]+$/.test(form.email))
      errs.email = 'Email non valida';
    if (form.partita_iva && !/^\d{11}$/.test(form.partita_iva.replace(/\s/g, '')))
      errs.partita_iva = 'P.IVA deve essere di 11 cifre';
    if (form.provvigione_percentuale !== '' && (
      isNaN(form.provvigione_percentuale) ||
      form.provvigione_percentuale < 0 || form.provvigione_percentuale > 100))
      errs.provvigione_percentuale = 'Valore tra 0 e 100';
    setFormErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSave = async () => {
    if (!validateForm()) return;
    setSaving(true);
    const payload = {
      ...form,
      agenzia_id: form.agenzia_id ? Number(form.agenzia_id) : null,
      provvigione_percentuale: form.provvigione_percentuale !== '' ? Number(form.provvigione_percentuale) : null,
      partita_iva: form.partita_iva || null,
      email: form.email || null,
    };
    try {
      if (modal.mode === 'create') {
        await createConsulente(payload);
        showToast('Consulente creato');
      } else {
        await updateConsulente(modal.data.id, payload);
        showToast('Consulente aggiornato');
      }
      setModal(null);
      load();
    } catch (e) {
      const msg = e?.response?.data?.detail || 'Errore nel salvataggio';
      showToast(msg, 'error');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (c) => {
    if (!window.confirm(`Disattivare il consulente "${c.cognome} ${c.nome}"?`)) return;
    try {
      await deleteConsulente(c.id);
      showToast('Consulente disattivato');
      load();
    } catch {
      showToast('Errore nella disattivazione', 'error');
    }
  };

  const field = (key) => ({
    value: form[key],
    onChange: (e) => setForm(f => ({ ...f, [key]: e.target.value })),
  });

  const agenziaNome = (id) => agenzie.find(a => a.id === id)?.nome || '—';

  return (
    <div className="consulenti-manager">
      <div className="consulenti-header">
        <div>
          <h2>Consulenti</h2>
          <span className="count-badge">{result.total} consulenti</span>
        </div>
        <button className="btn-primary" onClick={openCreate}>+ Nuovo Consulente</button>
      </div>

      {success && <div className="toast toast-success">{success}</div>}
      {error && <div className="toast toast-error">{error}</div>}

      <div className="consulenti-toolbar">
        <input
          className="search-input"
          placeholder="Cerca per nome, cognome o email…"
          value={filters.search}
          onChange={e => setFilters(f => ({ ...f, search: e.target.value, page: 1 }))}
        />
      </div>

      {loading ? (
        <div className="loading-spinner">Caricamento…</div>
      ) : (
        <>
          <div className="consulenti-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Cognome / Nome</th>
                  <th>Email</th>
                  <th>Telefono</th>
                  <th>Agenzia</th>
                  <th>Zona</th>
                  <th>Provv. %</th>
                  <th>Stato</th>
                  <th>Azioni</th>
                </tr>
              </thead>
              <tbody>
                {result.items.length === 0 && (
                  <tr><td colSpan={8} className="empty-cell">Nessun consulente trovato.</td></tr>
                )}
                {result.items.map(c => (
                  <tr key={c.id} className={!c.attivo ? 'row-inactive' : ''}>
                    <td><strong>{c.cognome} {c.nome}</strong></td>
                    <td>{c.email || '—'}</td>
                    <td>{c.telefono || '—'}</td>
                    <td>{c.agenzia_id ? agenziaNome(c.agenzia_id) : '—'}</td>
                    <td>{c.zona_competenza || '—'}</td>
                    <td>{c.provvigione_percentuale != null ? `${c.provvigione_percentuale}%` : '—'}</td>
                    <td>
                      <span className={`badge ${c.attivo ? 'badge-active' : 'badge-inactive'}`}>
                        {c.attivo ? 'Attivo' : 'Inattivo'}
                      </span>
                    </td>
                    <td className="action-cell">
                      <button className="btn-sm btn-secondary" onClick={() => openEdit(c)}>Modifica</button>
                      {c.attivo && (
                        <button className="btn-sm btn-danger" onClick={() => handleDelete(c)}>Disattiva</button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {result.pages > 1 && (
            <div className="pagination">
              <button disabled={filters.page <= 1} onClick={() => setFilters(f => ({ ...f, page: f.page - 1 }))}>‹</button>
              <span>Pagina {filters.page} di {result.pages}</span>
              <button disabled={filters.page >= result.pages} onClick={() => setFilters(f => ({ ...f, page: f.page + 1 }))}>›</button>
            </div>
          )}
        </>
      )}

      {modal && (
        <div className="modal-overlay" onClick={() => setModal(null)}>
          <div className="modal-box modal-lg" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{modal.mode === 'create' ? 'Nuovo Consulente' : 'Modifica Consulente'}</h3>
              <button className="modal-close" onClick={() => setModal(null)}>×</button>
            </div>
            <div className="modal-body modal-grid-2">
              <div className={`form-group ${formErrors.nome ? 'has-error' : ''}`}>
                <label>Nome *</label>
                <input {...field('nome')} placeholder="Nome" />
                {formErrors.nome && <span className="field-error">{formErrors.nome}</span>}
              </div>
              <div className={`form-group ${formErrors.cognome ? 'has-error' : ''}`}>
                <label>Cognome *</label>
                <input {...field('cognome')} placeholder="Cognome" />
                {formErrors.cognome && <span className="field-error">{formErrors.cognome}</span>}
              </div>
              <div className={`form-group ${formErrors.email ? 'has-error' : ''}`}>
                <label>Email</label>
                <input {...field('email')} type="email" placeholder="email@example.it" />
                {formErrors.email && <span className="field-error">{formErrors.email}</span>}
              </div>
              <div className="form-group">
                <label>Telefono</label>
                <input {...field('telefono')} placeholder="333 000 0000" />
              </div>
              <div className={`form-group ${formErrors.partita_iva ? 'has-error' : ''}`}>
                <label>Partita IVA</label>
                <input {...field('partita_iva')} placeholder="11 cifre" maxLength={11} />
                {formErrors.partita_iva && <span className="field-error">{formErrors.partita_iva}</span>}
              </div>
              <div className={`form-group ${formErrors.provvigione_percentuale ? 'has-error' : ''}`}>
                <label>Provvigione %</label>
                <input {...field('provvigione_percentuale')} type="number" min={0} max={100} step={0.5} placeholder="0–100" />
                {formErrors.provvigione_percentuale && <span className="field-error">{formErrors.provvigione_percentuale}</span>}
              </div>
              <div className="form-group">
                <label>Agenzia</label>
                <select value={form.agenzia_id} onChange={e => setForm(f => ({ ...f, agenzia_id: e.target.value }))}>
                  <option value="">— Nessuna agenzia —</option>
                  {agenzie.map(a => <option key={a.id} value={a.id}>{a.nome}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>Zona competenza</label>
                <input {...field('zona_competenza')} placeholder="es. Napoli, Caserta" />
              </div>
              <div className="form-group form-group-full">
                <label>Note</label>
                <textarea {...field('note')} rows={2} placeholder="Note interne…" />
              </div>
              <div className="form-group form-check">
                <label>
                  <input
                    type="checkbox"
                    checked={form.attivo}
                    onChange={e => setForm(f => ({ ...f, attivo: e.target.checked }))}
                  />
                  {' '}Attivo
                </label>
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn-secondary" onClick={() => setModal(null)}>Annulla</button>
              <button className="btn-primary" onClick={handleSave} disabled={saving}>
                {saving ? 'Salvataggio…' : 'Salva'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
