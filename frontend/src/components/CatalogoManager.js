import React, { useState, useEffect, useCallback } from 'react';
import {
  getProdotti, createProdotto, updateProdotto, deleteProdotto
} from '../services/apiService';
import './CatalogoManager.css';

const TIPI = ['apprendistato', 'tirocinio', 'formazione', 'altro'];
const UNITA = ['ora', 'giorno', 'mese', 'forfait', 'partecipante'];

const TIPO_LABELS = {
  apprendistato: 'Apprendistato',
  tirocinio: 'Tirocinio',
  formazione: 'Formazione',
  altro: 'Altro',
};

const EMPTY_FORM = {
  codice: '', nome: '', descrizione: '', tipo: 'formazione',
  prezzo_base: '', unita_misura: 'ora', attivo: true,
};

const fmt = (n) => new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR' }).format(n);

export default function CatalogoManager() {
  const [prodotti, setProdotti] = useState([]);
  const [total, setTotal] = useState(0);
  const [filters, setFilters] = useState({ search: '', tipo: '', attivo: '' });
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(null);
  const [error, setError] = useState(null);
  const [modal, setModal] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [formErrors, setFormErrors] = useState({});

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = { limit: 200 };
      if (filters.search) params.search = filters.search;
      if (filters.tipo) params.tipo = filters.tipo;
      if (filters.attivo !== '') params.attivo = filters.attivo === 'true';
      const data = await getProdotti(params);
      setProdotti(Array.isArray(data) ? data : []);
      setTotal(Array.isArray(data) ? data.length : 0);
    } catch { setError('Errore caricamento catalogo'); }
    finally { setLoading(false); }
  }, [filters]);

  useEffect(() => { load(); }, [load]);

  const toast = (msg, type = 'success') => {
    type === 'success' ? setSuccess(msg) : setError(msg);
    setTimeout(() => { setSuccess(null); setError(null); }, 3500);
  };

  const openCreate = () => { setForm(EMPTY_FORM); setFormErrors({}); setModal({ mode: 'create' }); };
  const openEdit = (p) => {
    setForm({
      codice: p.codice || '', nome: p.nome, descrizione: p.descrizione || '',
      tipo: p.tipo, prezzo_base: p.prezzo_base, unita_misura: p.unita_misura || 'ora', attivo: p.attivo,
    });
    setFormErrors({});
    setModal({ mode: 'edit', data: p });
  };

  const validate = () => {
    const e = {};
    if (!form.nome.trim() || form.nome.trim().length < 2) e.nome = 'Nome obbligatorio (min 2 caratteri)';
    if (form.prezzo_base === '' || isNaN(Number(form.prezzo_base)) || Number(form.prezzo_base) < 0)
      e.prezzo_base = 'Prezzo deve essere ≥ 0';
    setFormErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleSave = async () => {
    if (!validate()) return;
    setSaving(true);
    const payload = { ...form, prezzo_base: Number(form.prezzo_base), codice: form.codice || null };
    try {
      if (modal.mode === 'create') { await createProdotto(payload); toast('Prodotto creato'); }
      else { await updateProdotto(modal.data.id, payload); toast('Prodotto aggiornato'); }
      setModal(null); load();
    } catch (e) {
      toast(e?.response?.data?.detail || 'Errore nel salvataggio', 'error');
    } finally { setSaving(false); }
  };

  const handleDelete = async (p) => {
    if (!window.confirm(`Disattivare "${p.nome}"?`)) return;
    try { await deleteProdotto(p.id); toast('Prodotto disattivato'); load(); }
    catch { toast('Errore', 'error'); }
  };

  const f = (key) => ({ value: form[key], onChange: (e) => setForm(f => ({ ...f, [key]: e.target.value })) });

  // Raggruppa per tipo
  const grouped = TIPI.reduce((acc, t) => {
    acc[t] = prodotti.filter(p => p.tipo === t);
    return acc;
  }, {});

  return (
    <div className="catalogo-manager">
      <div className="catalogo-header">
        <div>
          <h2>Catalogo Prodotti / Servizi</h2>
          <span className="count-badge">{total} prodotti</span>
        </div>
        <button className="btn-primary" onClick={openCreate}>+ Nuovo Prodotto</button>
      </div>

      {success && <div className="toast toast-success">{success}</div>}
      {error && <div className="toast toast-error">{error}</div>}

      {/* Filtri */}
      <div className="catalogo-filters">
        <input className="search-input" placeholder="Cerca nome, codice, descrizione…"
          value={filters.search} onChange={e => setFilters(f => ({ ...f, search: e.target.value }))} />
        <select className="filter-select-sm" value={filters.tipo}
          onChange={e => setFilters(f => ({ ...f, tipo: e.target.value }))}>
          <option value="">Tutti i tipi</option>
          {TIPI.map(t => <option key={t} value={t}>{TIPO_LABELS[t]}</option>)}
        </select>
        <select className="filter-select-sm" value={filters.attivo}
          onChange={e => setFilters(f => ({ ...f, attivo: e.target.value }))}>
          <option value="">Tutti</option>
          <option value="true">Solo attivi</option>
          <option value="false">Solo inattivi</option>
        </select>
      </div>

      {loading ? <div className="loading-spinner">Caricamento…</div> : (
        <div className="catalogo-body">
          {TIPI.map(tipo => {
            const items = filters.tipo ? (filters.tipo === tipo ? prodotti : []) : grouped[tipo];
            if (items.length === 0) return null;
            return (
              <section key={tipo} className="catalogo-section">
                <div className="catalogo-section-header">
                  <h3>{TIPO_LABELS[tipo]}</h3>
                  <span className="section-count">{items.length}</span>
                </div>
                <div className="prodotti-grid">
                  {items.map(p => (
                    <div key={p.id} className={`prodotto-card ${!p.attivo ? 'inactive' : ''}`}>
                      <div className="prodotto-top">
                        {p.codice && <span className="prodotto-codice">{p.codice}</span>}
                        <span className={`tipo-badge tipo-${p.tipo}`}>{TIPO_LABELS[p.tipo]}</span>
                        {!p.attivo && <span className="badge badge-inactive">Inattivo</span>}
                      </div>
                      <div className="prodotto-nome">{p.nome}</div>
                      {p.descrizione && <div className="prodotto-desc">{p.descrizione}</div>}
                      <div className="prodotto-price">
                        <strong>{fmt(p.prezzo_base)}</strong>
                        <span className="price-unit">/{p.unita_misura || 'ora'}</span>
                      </div>
                      <div className="prodotto-actions">
                        <button className="btn-sm btn-secondary" onClick={() => openEdit(p)}>Modifica</button>
                        {p.attivo && <button className="btn-sm btn-danger" onClick={() => handleDelete(p)}>Disattiva</button>}
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            );
          })}
          {prodotti.length === 0 && <div className="empty-state">Nessun prodotto trovato.</div>}
        </div>
      )}

      {modal && (
        <div className="modal-overlay" onClick={() => setModal(null)}>
          <div className="modal-box modal-lg" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{modal.mode === 'create' ? 'Nuovo Prodotto' : 'Modifica Prodotto'}</h3>
              <button className="modal-close" onClick={() => setModal(null)}>×</button>
            </div>
            <div className="modal-body modal-grid-2">
              <div className={`form-group ${formErrors.nome ? 'has-error' : ''}`}>
                <label>Nome *</label>
                <input {...f('nome')} placeholder="Nome prodotto/servizio" />
                {formErrors.nome && <span className="field-error">{formErrors.nome}</span>}
              </div>
              <div className="form-group">
                <label>Codice</label>
                <input {...f('codice')} placeholder="es. FORM-001" />
              </div>
              <div className="form-group">
                <label>Tipo *</label>
                <select value={form.tipo} onChange={e => setForm(f => ({ ...f, tipo: e.target.value }))}>
                  {TIPI.map(t => <option key={t} value={t}>{TIPO_LABELS[t]}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>Unità di misura</label>
                <select value={form.unita_misura} onChange={e => setForm(f => ({ ...f, unita_misura: e.target.value }))}>
                  {UNITA.map(u => <option key={u} value={u}>{u}</option>)}
                </select>
              </div>
              <div className={`form-group ${formErrors.prezzo_base ? 'has-error' : ''}`}>
                <label>Prezzo base (€) *</label>
                <input {...f('prezzo_base')} type="number" min={0} step={0.01} placeholder="0.00" />
                {formErrors.prezzo_base && <span className="field-error">{formErrors.prezzo_base}</span>}
              </div>
              <div className="form-group form-check" style={{ alignSelf: 'end' }}>
                <label>
                  <input type="checkbox" checked={form.attivo}
                    onChange={e => setForm(f => ({ ...f, attivo: e.target.checked }))} />
                  {' '}Attivo
                </label>
              </div>
              <div className="form-group form-group-full">
                <label>Descrizione</label>
                <textarea {...f('descrizione')} rows={3} placeholder="Descrizione del prodotto/servizio…" />
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
