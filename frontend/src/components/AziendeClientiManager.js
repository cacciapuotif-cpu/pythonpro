import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  getAziendeClienti, createAziendaCliente, updateAziendaCliente, deleteAziendaCliente,
  getConsulenti, getAgenzie
} from '../services/apiService';
import './AziendeClientiManager.css';

const normalizePartitaIva = (value = '') => value.replace(/\s+/g, '').replace(/^IT/i, '');

const isValidPartitaIva = (value = '') => {
  const clean = normalizePartitaIva(value);
  if (!clean) return true;
  if (!/^\d{11}$/.test(clean)) return false;

  let oddSum = 0;
  for (let i = 0; i < 10; i += 2) oddSum += Number(clean[i]);

  let evenSum = 0;
  for (let i = 1; i < 10; i += 2) {
    const doubled = Number(clean[i]) * 2;
    evenSum += doubled < 10 ? doubled : doubled - 9;
  }

  const check = (10 - ((oddSum + evenSum) % 10)) % 10;
  return check === Number(clean[10]);
};

const blankToNull = (value) => {
  if (typeof value !== 'string') return value;
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
};

const EMPTY_FORM = {
  ragione_sociale: '', partita_iva: '', codice_fiscale: '', settore_ateco: '', attivita_erogate: '',
  indirizzo: '', citta: '', cap: '', provincia: '',
  email: '', pec: '', telefono: '', sito_web: '', linkedin_url: '', facebook_url: '', instagram_url: '',
  legale_rappresentante_nome: '', legale_rappresentante_cognome: '', legale_rappresentante_codice_fiscale: '',
  legale_rappresentante_email: '', legale_rappresentante_telefono: '', legale_rappresentante_indirizzo: '', legale_rappresentante_linkedin: '',
  legale_rappresentante_facebook: '', legale_rappresentante_instagram: '', legale_rappresentante_tiktok: '',
  referente_nome: '', referente_cognome: '', referente_ruolo: '', referente_email: '', referente_telefono: '', referente_indirizzo: '',
  referente_luogo_nascita: '', referente_data_nascita: '',
  referente_linkedin: '', referente_facebook: '', referente_instagram: '', referente_tiktok: '',
  agenzia_id: '', consulente_id: '', note: '', attivo: true
};

export default function AziendeClientiManager({ currentUser }) {
  const [result, setResult] = useState({ items: [], total: 0, pages: 1 });
  const [agenzie, setAgenzie] = useState([]);
  const [consulenti, setConsulenti] = useState([]);
  const [filters, setFilters] = useState({ search: '', citta: '', agenzia_id: '', consulente_id: '', page: 1, limit: 20, sort_by: 'ragione_sociale', order: 'asc' });
  const [searchInput, setSearchInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [modal, setModal] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [formErrors, setFormErrors] = useState({});
  const searchTimer = useRef(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = { page: filters.page, limit: filters.limit, sort_by: filters.sort_by, order: filters.order };
      if (filters.search) params.search = filters.search;
      if (filters.citta) params.citta = filters.citta;
      if (filters.agenzia_id) params.agenzia_id = filters.agenzia_id;
      if (filters.consulente_id) params.consulente_id = filters.consulente_id;
      const data = await getAziendeClienti(params);
      setResult({ items: data.items || [], total: data.total || 0, pages: data.pages || 1 });
    } catch {
      setError('Errore nel caricamento aziende clienti');
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    setSearchInput(filters.search);
  }, [filters.search]);

  useEffect(() => {
    getAgenzie({ limit: 100 }).then(d => setAgenzie(d.items || d || [])).catch(() => {});
    getConsulenti({ limit: 100 }).then(d => setConsulenti(d.items || [])).catch(() => {});
  }, []);

  const showToast = (msg, type = 'success') => {
    if (type === 'success') setSuccess(msg);
    else setError(msg);
    setTimeout(() => { setSuccess(null); setError(null); }, 3500);
  };

  const handleSearchChange = (e) => {
    const val = e.target.value;
    setSearchInput(val);
    clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => {
      setFilters(f => ({ ...f, search: val, page: 1 }));
    }, 300);
  };

  const openCreate = () => {
    setForm(EMPTY_FORM);
    setFormErrors({});
    setModal({ mode: 'create' });
  };

  const openEdit = (az) => {
    setForm({
      ragione_sociale: az.ragione_sociale, partita_iva: az.partita_iva || '',
      codice_fiscale: az.codice_fiscale || '', settore_ateco: az.settore_ateco || '', attivita_erogate: az.attivita_erogate || '',
      indirizzo: az.indirizzo || '', citta: az.citta || '', cap: az.cap || '',
      provincia: az.provincia || '', email: az.email || '', pec: az.pec || '',
      telefono: az.telefono || '', sito_web: az.sito_web || '', linkedin_url: az.linkedin_url || '',
      facebook_url: az.facebook_url || '', instagram_url: az.instagram_url || '',
      legale_rappresentante_nome: az.legale_rappresentante_nome || '',
      legale_rappresentante_cognome: az.legale_rappresentante_cognome || '',
      legale_rappresentante_codice_fiscale: az.legale_rappresentante_codice_fiscale || '',
      legale_rappresentante_email: az.legale_rappresentante_email || '',
      legale_rappresentante_telefono: az.legale_rappresentante_telefono || '',
      legale_rappresentante_indirizzo: az.legale_rappresentante_indirizzo || '',
      legale_rappresentante_linkedin: az.legale_rappresentante_linkedin || '',
      legale_rappresentante_facebook: az.legale_rappresentante_facebook || '',
      legale_rappresentante_instagram: az.legale_rappresentante_instagram || '',
      legale_rappresentante_tiktok: az.legale_rappresentante_tiktok || '',
      referente_nome: az.referente_nome || '', referente_cognome: az.referente_cognome || '', referente_ruolo: az.referente_ruolo || '',
      referente_email: az.referente_email || '', referente_telefono: az.referente_telefono || '',
      referente_indirizzo: az.referente_indirizzo || '',
      referente_luogo_nascita: az.referente_luogo_nascita || '',
      referente_data_nascita: az.referente_data_nascita ? `${az.referente_data_nascita}`.slice(0, 10) : '',
      referente_linkedin: az.referente_linkedin || '', referente_facebook: az.referente_facebook || '',
      referente_instagram: az.referente_instagram || '', referente_tiktok: az.referente_tiktok || '',
      agenzia_id: az.agenzia_id || '', consulente_id: az.consulente_id || '',
      note: az.note || '', attivo: az.attivo
    });
    setFormErrors({});
    setModal({ mode: 'edit', data: az });
  };

  const validateForm = () => {
    const errs = {};
    if (!form.ragione_sociale.trim() || form.ragione_sociale.trim().length < 2)
      errs.ragione_sociale = 'Ragione sociale obbligatoria';
    const cleanPartitaIva = normalizePartitaIva(form.partita_iva);
    if (!cleanPartitaIva) errs.partita_iva = 'Partita IVA obbligatoria';
    else if (!/^\d{11}$/.test(cleanPartitaIva)) errs.partita_iva = 'P.IVA: 11 cifre numeriche';
    else if (!isValidPartitaIva(cleanPartitaIva)) errs.partita_iva = 'P.IVA non valida (checksum errato)';
    if (form.cap && !/^\d{5}$/.test(form.cap))
      errs.cap = 'CAP: 5 cifre';
    if (form.provincia && !/^[A-Za-z]{2}$/.test(form.provincia))
      errs.provincia = 'Sigla 2 lettere (es: NA)';
    if (form.email && !/^[^@]+@[^@]+\.[^@]+$/.test(form.email))
      errs.email = 'Email non valida';
    if (form.pec && !/^[^@]+@[^@]+\.[^@]+$/.test(form.pec))
      errs.pec = 'PEC non valida';
    if (form.referente_email && !/^[^@]+@[^@]+\.[^@]+$/.test(form.referente_email))
      errs.referente_email = 'Email referente non valida';
    if (form.legale_rappresentante_email && !/^[^@]+@[^@]+\.[^@]+$/.test(form.legale_rappresentante_email))
      errs.legale_rappresentante_email = 'Email legale rappresentante non valida';
    setFormErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSave = async () => {
    if (!validateForm()) return;
    setSaving(true);
    const payload = {
      ...form,
      agenzia_id: form.agenzia_id ? Number(form.agenzia_id) : null,
      consulente_id: form.consulente_id ? Number(form.consulente_id) : null,
      ragione_sociale: form.ragione_sociale.trim(),
      partita_iva: normalizePartitaIva(form.partita_iva),
      codice_fiscale: blankToNull(form.codice_fiscale),
      settore_ateco: blankToNull(form.settore_ateco),
      attivita_erogate: blankToNull(form.attivita_erogate),
      indirizzo: blankToNull(form.indirizzo),
      citta: blankToNull(form.citta),
      cap: blankToNull(form.cap),
      email: blankToNull(form.email),
      pec: blankToNull(form.pec),
      telefono: blankToNull(form.telefono),
      sito_web: blankToNull(form.sito_web),
      linkedin_url: blankToNull(form.linkedin_url),
      facebook_url: blankToNull(form.facebook_url),
      instagram_url: blankToNull(form.instagram_url),
      legale_rappresentante_nome: blankToNull(form.legale_rappresentante_nome),
      legale_rappresentante_cognome: blankToNull(form.legale_rappresentante_cognome),
      legale_rappresentante_codice_fiscale: blankToNull(form.legale_rappresentante_codice_fiscale),
      legale_rappresentante_email: blankToNull(form.legale_rappresentante_email),
      legale_rappresentante_telefono: blankToNull(form.legale_rappresentante_telefono),
      legale_rappresentante_indirizzo: blankToNull(form.legale_rappresentante_indirizzo),
      legale_rappresentante_linkedin: blankToNull(form.legale_rappresentante_linkedin),
      legale_rappresentante_facebook: blankToNull(form.legale_rappresentante_facebook),
      legale_rappresentante_instagram: blankToNull(form.legale_rappresentante_instagram),
      legale_rappresentante_tiktok: blankToNull(form.legale_rappresentante_tiktok),
      referente_nome: blankToNull(form.referente_nome),
      referente_cognome: blankToNull(form.referente_cognome),
      referente_ruolo: blankToNull(form.referente_ruolo),
      referente_email: blankToNull(form.referente_email),
      referente_telefono: blankToNull(form.referente_telefono),
      referente_indirizzo: blankToNull(form.referente_indirizzo),
      referente_luogo_nascita: blankToNull(form.referente_luogo_nascita),
      referente_data_nascita: form.referente_data_nascita ? `${form.referente_data_nascita}T00:00:00Z` : null,
      referente_linkedin: blankToNull(form.referente_linkedin),
      referente_facebook: blankToNull(form.referente_facebook),
      referente_instagram: blankToNull(form.referente_instagram),
      referente_tiktok: blankToNull(form.referente_tiktok),
      provincia: form.provincia ? form.provincia.toUpperCase() : null,
      note: blankToNull(form.note),
    };
    try {
      if (modal.mode === 'create') {
        const created = await createAziendaCliente(payload);
        showToast(`Azienda cliente creata: ${created.ragione_sociale}`);
        setModal(null);
        setFilters(f => ({
          ...f,
          search: created.ragione_sociale || '',
          citta: '',
          agenzia_id: '',
          consulente_id: '',
          page: 1,
          sort_by: 'created_at',
          order: 'desc'
        }));
      } else {
        await updateAziendaCliente(modal.data.id, payload);
        showToast('Azienda aggiornata');
        setModal(null);
        load();
      }
    } catch (e) {
      const msg = e?.response?.data?.detail || 'Errore nel salvataggio';
      showToast(msg, 'error');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (az) => {
    if (!window.confirm(`Disattivare "${az.ragione_sociale}"?`)) return;
    try {
      await deleteAziendaCliente(az.id);
      showToast('Azienda disattivata');
      load();
    } catch {
      showToast('Errore nella disattivazione', 'error');
    }
  };

  const field = (key) => ({
    value: form[key],
    onChange: (e) => setForm(f => ({ ...f, [key]: e.target.value })),
  });

  const consulenteNome = (id) => {
    const c = consulenti.find(x => x.id === id);
    return c ? `${c.cognome} ${c.nome}` : '—';
  };

  const agenziaNome = (id) => {
    const a = agenzie.find(x => x.id === id);
    return a ? a.nome : '—';
  };

  const toggleSort = (col) => {
    setFilters(f => ({
      ...f,
      sort_by: col,
      order: f.sort_by === col && f.order === 'asc' ? 'desc' : 'asc',
      page: 1
    }));
  };

  const SortIcon = ({ col }) => {
    if (filters.sort_by !== col) return <span className="sort-icon">↕</span>;
    return <span className="sort-icon active">{filters.order === 'asc' ? '↑' : '↓'}</span>;
  };

  return (
    <div className="aziende-clienti-manager">
      <div className="aziende-header">
        <div>
          <h2>Aziende Clienti</h2>
          <span className="count-badge">{result.total} aziende</span>
        </div>
        <button className="btn-primary" onClick={openCreate}>+ Nuova Azienda</button>
      </div>

      {success && <div className="toast toast-success">{success}</div>}
      {error && <div className="toast toast-error">{error}</div>}

      {/* Filtri */}
      <div className="aziende-filters">
        <input
          className="search-input"
          placeholder="Cerca ragione sociale, PEC, P.IVA…"
          value={searchInput}
          onChange={handleSearchChange}
        />
        <input
          className="filter-input"
          placeholder="Filtra per città…"
          value={filters.citta}
          onChange={e => setFilters(f => ({ ...f, citta: e.target.value, page: 1 }))}
        />
        <select
          value={filters.agenzia_id}
          onChange={e => setFilters(f => ({ ...f, agenzia_id: e.target.value, page: 1 }))}
          className="filter-select"
        >
          <option value="">Tutte le agenzie</option>
          {agenzie.map(a => (
            <option key={a.id} value={a.id}>{a.nome}</option>
          ))}
        </select>
        <select
          value={filters.consulente_id}
          onChange={e => setFilters(f => ({ ...f, consulente_id: e.target.value, page: 1 }))}
          className="filter-select"
        >
          <option value="">Tutti i consulenti</option>
          {consulenti.map(c => (
            <option key={c.id} value={c.id}>{c.cognome} {c.nome}</option>
          ))}
        </select>
      </div>

      {loading ? (
        <div className="loading-spinner">Caricamento…</div>
      ) : (
        <>
          <div className="aziende-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th className="sortable" onClick={() => toggleSort('ragione_sociale')}>
                    Ragione Sociale <SortIcon col="ragione_sociale" />
                  </th>
                  <th>P.IVA</th>
                  <th className="sortable" onClick={() => toggleSort('citta')}>
                    Città <SortIcon col="citta" />
                  </th>
                  <th>Referente</th>
                  <th>Agenzia</th>
                  <th>Consulente</th>
                  <th>Stato</th>
                  <th>Azioni</th>
                </tr>
              </thead>
              <tbody>
                {result.items.length === 0 && (
                  <tr><td colSpan={8} className="empty-cell">Nessuna azienda trovata.</td></tr>
                )}
                {result.items.map(az => (
                  <tr key={az.id} className={!az.attivo ? 'row-inactive' : ''}>
                    <td>
                      <strong>{az.ragione_sociale}</strong>
                      {az.settore_ateco && <div className="sub-text">ATECO {az.settore_ateco}</div>}
                    </td>
                    <td>{az.partita_iva || '—'}</td>
                    <td>
                      {az.citta || '—'}
                      {az.provincia && <span className="provincia-badge"> ({az.provincia})</span>}
                    </td>
                    <td>
                      <div>{[az.referente_nome, az.referente_cognome].filter(Boolean).join(' ') || '—'}</div>
                      {az.referente_email && <div className="sub-text">{az.referente_email}</div>}
                    </td>
                    <td>
                      {az.agenzia_id ? agenziaNome(az.agenzia_id) : '—'}
                    </td>
                    <td>
                      {az.consulente_id ? consulenteNome(az.consulente_id) : '—'}
                    </td>
                    <td>
                      <span className={`badge ${az.attivo ? 'badge-active' : 'badge-inactive'}`}>
                        {az.attivo ? 'Attiva' : 'Inattiva'}
                      </span>
                    </td>
                    <td className="action-cell">
                      <button className="btn-sm btn-secondary" onClick={() => openEdit(az)}>Modifica</button>
                      {az.attivo && (
                        <button className="btn-sm btn-danger" onClick={() => handleDelete(az)}>Disattiva</button>
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
              <span>Pagina {filters.page} di {result.pages} — {result.total} totali</span>
              <button disabled={filters.page >= result.pages} onClick={() => setFilters(f => ({ ...f, page: f.page + 1 }))}>›</button>
            </div>
          )}
        </>
      )}

      {modal && (
        <div className="modal-overlay aziende-modal-overlay" onClick={() => setModal(null)}>
          <div className="modal-box modal-xl aziende-modal-box" onClick={e => e.stopPropagation()}>
            <div className="modal-header aziende-modal-header">
              <div>
                <h3>{modal.mode === 'create' ? 'Nuova Azienda Cliente' : 'Modifica Azienda Cliente'}</h3>
                <p className="aziende-modal-subtitle">Ragione sociale e Partita IVA sono obbligatorie. Il resto profila l'azienda e puo essere arricchito nel tempo.</p>
              </div>
              <button className="modal-close" onClick={() => setModal(null)}>×</button>
            </div>
            <div className="modal-body aziende-modal-body">
              <aside className="aziende-modal-sidebar">
                <div className="aziende-modal-card">
                  <span className="aziende-modal-card-eyebrow">Percorso rapido</span>
                  <strong>Anagrafica azienda</strong>
                  <p>Parti da ragione sociale e P.IVA, poi completa solo i contatti davvero utili.</p>
                </div>
                <div className="aziende-modal-card">
                  <span className="aziende-modal-card-eyebrow">Campi chiave</span>
                  <ul className="aziende-modal-checklist">
                    <li>Ragione sociale</li>
                    <li>Partita IVA</li>
                    <li>Attività/servizi erogati</li>
                    <li>Legale rappresentante e referente</li>
                  </ul>
                </div>
              </aside>

              <div className="aziende-modal-content">
                <fieldset className="form-section">
                  <legend>Dati legali</legend>
                  <div className="aziende-form-grid aziende-form-grid-primary">
                    <div className={`form-group aziende-col-span-2 ${formErrors.ragione_sociale ? 'has-error' : ''}`}>
                      <label>Ragione Sociale *</label>
                      <input {...field('ragione_sociale')} placeholder="Ragione sociale" />
                      {formErrors.ragione_sociale && <span className="field-error">{formErrors.ragione_sociale}</span>}
                    </div>
                    <div className={`form-group ${formErrors.partita_iva ? 'has-error' : ''}`}>
                      <label>Partita IVA *</label>
                      <input {...field('partita_iva')} placeholder="11 cifre" maxLength={11} />
                      {formErrors.partita_iva && <span className="field-error">{formErrors.partita_iva}</span>}
                    </div>
                    <div className="form-group">
                      <label>Codice Fiscale</label>
                      <input {...field('codice_fiscale')} placeholder="CF o P.IVA" maxLength={16} />
                    </div>
                    <div className="form-group">
                      <label>Settore ATECO</label>
                      <input {...field('settore_ateco')} placeholder="es. 85.59" maxLength={10} />
                    </div>
                    <div className="form-group aziende-col-span-2">
                      <label>Attività / servizi erogati</label>
                      <textarea {...field('attivita_erogate')} rows={3} placeholder="Formazione, consulenza, Academy interna, politiche attive, upskilling..." />
                    </div>
                  </div>
                </fieldset>

                <div className="aziende-modal-section-grid">
                  <fieldset className="form-section">
                    <legend>Sede</legend>
                    <div className="aziende-form-grid">
                      <div className="form-group aziende-col-span-2">
                        <label>Indirizzo</label>
                        <input {...field('indirizzo')} placeholder="Via, numero civico" />
                      </div>
                      <div className="form-group">
                        <label>Città</label>
                        <input {...field('citta')} placeholder="Città" />
                      </div>
                      <div className={`form-group ${formErrors.cap ? 'has-error' : ''}`}>
                        <label>CAP</label>
                        <input {...field('cap')} placeholder="00000" maxLength={5} />
                        {formErrors.cap && <span className="field-error">{formErrors.cap}</span>}
                      </div>
                      <div className={`form-group ${formErrors.provincia ? 'has-error' : ''}`}>
                        <label>Provincia</label>
                        <input {...field('provincia')} placeholder="NA" maxLength={2} style={{ textTransform: 'uppercase' }} />
                        {formErrors.provincia && <span className="field-error">{formErrors.provincia}</span>}
                      </div>
                    </div>
                  </fieldset>

                  <fieldset className="form-section">
                    <legend>Contatti e social ufficiali azienda</legend>
                    <div className="aziende-form-grid">
                      <div className={`form-group ${formErrors.email ? 'has-error' : ''}`}>
                        <label>Email</label>
                        <input {...field('email')} type="email" placeholder="info@azienda.it" />
                        {formErrors.email && <span className="field-error">{formErrors.email}</span>}
                      </div>
                      <div className={`form-group ${formErrors.pec ? 'has-error' : ''}`}>
                        <label>PEC</label>
                        <input {...field('pec')} type="email" placeholder="azienda@pec.it" />
                        {formErrors.pec && <span className="field-error">{formErrors.pec}</span>}
                      </div>
                      <div className="form-group">
                        <label>Telefono</label>
                        <input {...field('telefono')} placeholder="081 000 0000" />
                      </div>
                      <div className="form-group">
                        <label>Sito web</label>
                        <input {...field('sito_web')} placeholder="https://azienda.it" />
                      </div>
                      <div className="form-group">
                        <label>LinkedIn ufficiale azienda</label>
                        <input {...field('linkedin_url')} placeholder="https://linkedin.com/company/..." />
                      </div>
                      <div className="form-group">
                        <label>Facebook ufficiale azienda</label>
                        <input {...field('facebook_url')} placeholder="https://facebook.com/..." />
                      </div>
                      <div className="form-group">
                        <label>Instagram ufficiale azienda</label>
                        <input {...field('instagram_url')} placeholder="https://instagram.com/..." />
                      </div>
                    </div>
                  </fieldset>

                  <fieldset className="form-section">
                    <legend>Referente operativo</legend>
                    <div className="aziende-form-grid">
                      <div className="form-group">
                        <label>Referente nome</label>
                        <input {...field('referente_nome')} placeholder="Nome referente" />
                      </div>
                      <div className="form-group">
                        <label>Referente cognome</label>
                        <input {...field('referente_cognome')} placeholder="Cognome referente" />
                      </div>
                      <div className="form-group">
                        <label>Ruolo referente</label>
                        <input {...field('referente_ruolo')} placeholder="HR, Operations, Titolare..." />
                      </div>
                      <div className="form-group aziende-col-span-2">
                        <label>Referente email</label>
                        <input {...field('referente_email')} type="email" placeholder="referente@azienda.it" />
                        {formErrors.referente_email && <span className="field-error">{formErrors.referente_email}</span>}
                      </div>
                      <div className="form-group">
                        <label>Referente telefono</label>
                        <input {...field('referente_telefono')} placeholder="333 000 0000" />
                      </div>
                      <div className="form-group aziende-col-span-2">
                        <label>Indirizzo referente</label>
                        <input {...field('referente_indirizzo')} placeholder="Via, numero civico, comune..." />
                      </div>
                      <div className="form-group">
                        <label>Luogo nascita referente</label>
                        <input {...field('referente_luogo_nascita')} placeholder="Napoli, Roma..." />
                      </div>
                      <div className="form-group">
                        <label>Data nascita referente</label>
                        <input {...field('referente_data_nascita')} type="date" />
                      </div>
                      <div className="form-group">
                        <label>LinkedIn referente</label>
                        <input {...field('referente_linkedin')} placeholder="https://linkedin.com/in/..." />
                      </div>
                      <div className="form-group">
                        <label>Facebook referente</label>
                        <input {...field('referente_facebook')} placeholder="https://facebook.com/..." />
                      </div>
                      <div className="form-group">
                        <label>Instagram referente</label>
                        <input {...field('referente_instagram')} placeholder="https://instagram.com/..." />
                      </div>
                      <div className="form-group">
                        <label>TikTok referente</label>
                        <input {...field('referente_tiktok')} placeholder="https://tiktok.com/@..." />
                      </div>
                    </div>
                  </fieldset>
                </div>

                <fieldset className="form-section">
                  <legend>Legale rappresentante</legend>
                  <div className="aziende-form-grid aziende-form-grid-primary">
                    <div className="form-group">
                      <label>Nome</label>
                      <input {...field('legale_rappresentante_nome')} placeholder="Nome" />
                    </div>
                    <div className="form-group">
                      <label>Cognome</label>
                      <input {...field('legale_rappresentante_cognome')} placeholder="Cognome" />
                    </div>
                    <div className="form-group">
                      <label>Codice fiscale</label>
                      <input {...field('legale_rappresentante_codice_fiscale')} placeholder="RSSMRA80A01H501Z" maxLength={16} />
                    </div>
                    <div className={`form-group ${formErrors.legale_rappresentante_email ? 'has-error' : ''}`}>
                      <label>Email</label>
                      <input {...field('legale_rappresentante_email')} type="email" placeholder="legale@azienda.it" />
                      {formErrors.legale_rappresentante_email && <span className="field-error">{formErrors.legale_rappresentante_email}</span>}
                    </div>
                    <div className="form-group">
                      <label>Telefono</label>
                      <input {...field('legale_rappresentante_telefono')} placeholder="333 000 0000" />
                    </div>
                    <div className="form-group aziende-col-span-2">
                      <label>Indirizzo legale rappresentante</label>
                      <input {...field('legale_rappresentante_indirizzo')} placeholder="Via, numero civico, comune..." />
                    </div>
                    <div className="form-group">
                      <label>LinkedIn legale rappresentante</label>
                      <input {...field('legale_rappresentante_linkedin')} placeholder="https://linkedin.com/in/..." />
                    </div>
                    <div className="form-group">
                      <label>Facebook legale rappresentante</label>
                      <input {...field('legale_rappresentante_facebook')} placeholder="https://facebook.com/..." />
                    </div>
                    <div className="form-group">
                      <label>Instagram legale rappresentante</label>
                      <input {...field('legale_rappresentante_instagram')} placeholder="https://instagram.com/..." />
                    </div>
                    <div className="form-group">
                      <label>TikTok legale rappresentante</label>
                      <input {...field('legale_rappresentante_tiktok')} placeholder="https://tiktok.com/@..." />
                    </div>
                  </div>
                </fieldset>

                <fieldset className="form-section">
                  <legend>Gestione</legend>
                  <div className="aziende-form-grid aziende-form-grid-management">
                    <div className="form-group">
                      <label>Agenzia di riferimento</label>
                      <select value={form.agenzia_id} onChange={e => setForm(f => ({ ...f, agenzia_id: e.target.value }))}>
                        <option value="">— Nessuna —</option>
                        {agenzie.map(a => (
                          <option key={a.id} value={a.id}>{a.nome}</option>
                        ))}
                      </select>
                    </div>
                    <div className="form-group">
                      <label>Consulente assegnato</label>
                      <select value={form.consulente_id} onChange={e => setForm(f => ({ ...f, consulente_id: e.target.value }))}>
                        <option value="">— Nessuno —</option>
                        {consulenti.map(c => (
                          <option key={c.id} value={c.id}>{c.cognome} {c.nome}</option>
                        ))}
                      </select>
                    </div>
                    <div className="form-group aziende-col-span-2">
                      <label>Note</label>
                      <textarea {...field('note')} rows={3} placeholder="Note interne…" />
                    </div>
                    <div className="form-group form-check aziende-form-check">
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
                </fieldset>
              </div>
            </div>
            <div className="modal-footer aziende-modal-footer">
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
