import React, { useState, useEffect, useCallback } from 'react';
import {
  getAgenzie, createAgenzia, updateAgenzia, deleteAgenzia
} from '../services/apiService';
import './AgenzieManager.css';

const EMPTY_FORM = { nome: '', partita_iva: '', telefono: '', email: '', note: '', attivo: true };

export default function AgenzieManager() {
  const [agenzie, setAgenzie] = useState([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [modal, setModal] = useState(null); // null | { mode: 'create'|'edit', data }
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [formErrors, setFormErrors] = useState({});

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = { limit: 100 };
      if (search) params.search = search;
      const data = await getAgenzie(params);
      setAgenzie(Array.isArray(data) ? data : data.items || []);
      setTotal(Array.isArray(data) ? data.length : data.total || 0);
    } catch {
      setError('Errore nel caricamento agenzie');
    } finally {
      setLoading(false);
    }
  }, [search]);

  useEffect(() => { load(); }, [load]);

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

  const openEdit = (ag) => {
    setForm({ nome: ag.nome, partita_iva: ag.partita_iva || '', telefono: ag.telefono || '', email: ag.email || '',
               note: ag.note || '', attivo: ag.attivo });
    setFormErrors({});
    setModal({ mode: 'edit', data: ag });
  };

  const validateForm = () => {
    const errs = {};
    if (!form.nome.trim() || form.nome.trim().length < 2)
      errs.nome = 'Nome obbligatorio (min 2 caratteri)';
    if (form.partita_iva && !/^\d{11}$/.test(form.partita_iva.replace(/\s/g, '')))
      errs.partita_iva = 'P.IVA: 11 cifre numeriche';
    if (form.email && !/^[^@]+@[^@]+\.[^@]+$/.test(form.email))
      errs.email = 'Email non valida';
    setFormErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSave = async () => {
    if (!validateForm()) return;
    setSaving(true);
    try {
      if (modal.mode === 'create') {
        await createAgenzia(form);
        showToast('Agenzia creata');
      } else {
        await updateAgenzia(modal.data.id, form);
        showToast('Agenzia aggiornata');
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

  const handleDelete = async (ag) => {
    if (!window.confirm(`Disattivare l'agenzia "${ag.nome}"?`)) return;
    try {
      await deleteAgenzia(ag.id);
      showToast('Agenzia disattivata');
      load();
    } catch {
      showToast('Errore nella disattivazione', 'error');
    }
  };

  const field = (key) => ({
    value: form[key],
    onChange: (e) => setForm(f => ({ ...f, [key]: e.target.value })),
  });

  return (
    <div className="agenzie-manager">
      <div className="agenzie-header">
        <div>
          <h2>Agenzie</h2>
          <span className="agenzie-count">{total} agenzie</span>
        </div>
        <button className="btn-primary" onClick={openCreate}>+ Nuova Agenzia</button>
      </div>

      {success && <div className="toast toast-success">{success}</div>}
      {error && <div className="toast toast-error">{error}</div>}

      <div className="agenzie-toolbar">
        <input
          className="search-input"
          placeholder="Cerca per nome…"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
      </div>

      {loading ? (
        <div className="loading-spinner">Caricamento…</div>
      ) : (
        <div className="agenzie-grid">
          {agenzie.length === 0 && (
            <div className="empty-state">Nessuna agenzia trovata.</div>
          )}
          {agenzie.map(ag => (
            <div key={ag.id} className={`agenzia-card ${!ag.attivo ? 'inactive' : ''}`}>
              <div className="agenzia-card-header">
                <strong>{ag.nome}</strong>
                {!ag.attivo && <span className="badge badge-inactive">Inattiva</span>}
              </div>
              {ag.partita_iva && <div className="agenzia-field">P.IVA {ag.partita_iva}</div>}
              {ag.email && <div className="agenzia-field">✉ {ag.email}</div>}
              {ag.telefono && <div className="agenzia-field">📞 {ag.telefono}</div>}
              {ag.note && <div className="agenzia-note">{ag.note}</div>}
              <div className="agenzia-actions">
                <button className="btn-sm btn-secondary" onClick={() => openEdit(ag)}>Modifica</button>
                {ag.attivo && (
                  <button className="btn-sm btn-danger" onClick={() => handleDelete(ag)}>Disattiva</button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {modal && (
        <div className="modal-overlay" onClick={() => setModal(null)}>
          <div className="modal-box" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{modal.mode === 'create' ? 'Nuova Agenzia' : 'Modifica Agenzia'}</h3>
              <button className="modal-close" onClick={() => setModal(null)}>×</button>
            </div>
            <div className="modal-body">
              <div className={`form-group ${formErrors.nome ? 'has-error' : ''}`}>
                <label>Nome *</label>
                <input {...field('nome')} placeholder="Nome agenzia" />
                {formErrors.nome && <span className="field-error">{formErrors.nome}</span>}
              </div>
              <div className={`form-group ${formErrors.partita_iva ? 'has-error' : ''}`}>
                <label>Partita IVA</label>
                <input {...field('partita_iva')} placeholder="12345678901" maxLength={11} />
                {formErrors.partita_iva && <span className="field-error">{formErrors.partita_iva}</span>}
              </div>
              <div className={`form-group ${formErrors.email ? 'has-error' : ''}`}>
                <label>Email</label>
                <input {...field('email')} type="email" placeholder="info@agenzia.it" />
                {formErrors.email && <span className="field-error">{formErrors.email}</span>}
              </div>
              <div className="form-group">
                <label>Telefono</label>
                <input {...field('telefono')} placeholder="081 000 0000" />
              </div>
              <div className="form-group">
                <label>Note</label>
                <textarea {...field('note')} rows={3} placeholder="Note interne…" />
              </div>
              <div className="form-group form-check">
                <label>
                  <input
                    type="checkbox"
                    checked={form.attivo}
                    onChange={e => setForm(f => ({ ...f, attivo: e.target.checked }))}
                  />
                  {' '}Attiva
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
