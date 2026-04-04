import React, { useState, useEffect, useCallback } from 'react';
import {
  getListini, createListino, updateListino, deleteListino,
  getVociListino, addVoceListino, updateVoceListino, deleteVoceListino,
  getProdotti,
} from '../services/apiService';
import './ListiniManager.css';

const TIPI_CLIENTE = ['standard', 'apprendistato', 'finanziato', 'gratis'];
const TIPO_LABELS = { standard: 'Standard', apprendistato: 'Apprendistato', finanziato: 'Finanziato', gratis: 'Gratuito' };
const TIPO_COLORS = { standard: '#4361ee', apprendistato: '#1d4ed8', finanziato: '#065f46', gratis: '#92400e' };

const fmt = (n) => n != null
  ? new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR' }).format(n)
  : '—';

const EMPTY_LISTINO = { nome: '', descrizione: '', tipo_cliente: 'standard', attivo: true };
const EMPTY_VOCE = { prodotto_id: '', prezzo_override: '', sconto_percentuale: '0', note: '' };

export default function ListiniManager() {
  const [listini, setListini] = useState([]);
  const [prodotti, setProdotti] = useState([]);
  const [selected, setSelected] = useState(null);   // listino attivo nel pannello voci
  const [voci, setVoci] = useState([]);
  const [filters, setFilters] = useState({ search: '', tipo_cliente: '', attivo: '' });
  const [loading, setLoading] = useState(false);
  const [vociLoading, setVociLoading] = useState(false);
  const [success, setSuccess] = useState(null);
  const [error, setError] = useState(null);
  const [modal, setModal] = useState(null);         // {mode, data?} per listino
  const [form, setForm] = useState(EMPTY_LISTINO);
  const [saving, setSaving] = useState(false);
  const [formErrors, setFormErrors] = useState({});
  const [voceEdit, setVoceEdit] = useState(null);   // {id?, ...} per inline edit voce
  const [voceForm, setVoceForm] = useState(EMPTY_VOCE);
  const [savingVoce, setSavingVoce] = useState(false);

  const toast = (msg, type = 'success') => {
    type === 'success' ? setSuccess(msg) : setError(msg);
    setTimeout(() => { setSuccess(null); setError(null); }, 3500);
  };

  // ── Carica listini ────────────────────────────────────────────────────────
  const loadListini = useCallback(async () => {
    setLoading(true);
    try {
      const params = { limit: 100 };
      if (filters.search) params.search = filters.search;
      if (filters.tipo_cliente) params.tipo_cliente = filters.tipo_cliente;
      if (filters.attivo !== '') params.attivo = filters.attivo === 'true';
      const data = await getListini(params);
      setListini(Array.isArray(data) ? data : []);
    } catch { setError('Errore caricamento listini'); }
    finally { setLoading(false); }
  }, [filters]);

  // ── Carica voci del listino selezionato ──────────────────────────────────
  const loadVoci = useCallback(async (listinoId) => {
    if (!listinoId) { setVoci([]); return; }
    setVociLoading(true);
    try {
      const data = await getVociListino(listinoId);
      setVoci(Array.isArray(data) ? data : []);
    } catch { setError('Errore caricamento voci'); }
    finally { setVociLoading(false); }
  }, []);

  useEffect(() => { loadListini(); }, [loadListini]);

  useEffect(() => {
    getProdotti({ attivo: true, limit: 200 }).then(d => setProdotti(Array.isArray(d) ? d : [])).catch(() => {});
  }, []);

  useEffect(() => {
    if (selected) loadVoci(selected.id);
    else setVoci([]);
  }, [selected, loadVoci]);

  // ── Listino CRUD ──────────────────────────────────────────────────────────
  const openCreate = () => { setForm(EMPTY_LISTINO); setFormErrors({}); setModal({ mode: 'create' }); };
  const openEdit = (l) => {
    setForm({ nome: l.nome, descrizione: l.descrizione || '', tipo_cliente: l.tipo_cliente, attivo: l.attivo });
    setFormErrors({}); setModal({ mode: 'edit', data: l });
  };

  const validateListino = () => {
    const e = {};
    if (!form.nome.trim() || form.nome.trim().length < 2) e.nome = 'Nome obbligatorio';
    setFormErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleSaveListino = async () => {
    if (!validateListino()) return;
    setSaving(true);
    try {
      if (modal.mode === 'create') { await createListino(form); toast('Listino creato'); }
      else { await updateListino(modal.data.id, form); toast('Listino aggiornato'); }
      setModal(null); loadListini();
      if (selected && modal.mode === 'edit' && modal.data.id === selected.id)
        setSelected(prev => ({ ...prev, ...form }));
    } catch (e) { toast(e?.response?.data?.detail || 'Errore', 'error'); }
    finally { setSaving(false); }
  };

  const handleDeleteListino = async (l) => {
    if (!window.confirm(`Disattivare il listino "${l.nome}"?`)) return;
    try {
      await deleteListino(l.id);
      toast('Listino disattivato');
      if (selected?.id === l.id) setSelected(null);
      loadListini();
    } catch { toast('Errore', 'error'); }
  };

  // ── Voce inline ───────────────────────────────────────────────────────────
  const openNewVoce = () => {
    setVoceEdit({ mode: 'create' });
    setVoceForm(EMPTY_VOCE);
  };

  const openEditVoce = (v) => {
    setVoceEdit({ mode: 'edit', id: v.id });
    setVoceForm({
      prodotto_id: v.prodotto_id,
      prezzo_override: v.prezzo_override ?? '',
      sconto_percentuale: v.sconto_percentuale ?? '0',
      note: v.note || '',
    });
  };

  const handleSaveVoce = async () => {
    if (!voceForm.prodotto_id) { toast('Seleziona un prodotto', 'error'); return; }
    setSavingVoce(true);
    try {
      const payload = {
        listino_id: selected.id,
        prodotto_id: Number(voceForm.prodotto_id),
        prezzo_override: voceForm.prezzo_override !== '' ? Number(voceForm.prezzo_override) : null,
        sconto_percentuale: Number(voceForm.sconto_percentuale) || 0,
        note: voceForm.note || null,
      };
      if (voceEdit.mode === 'create') {
        await addVoceListino(selected.id, payload);
        toast('Prodotto aggiunto al listino');
      } else {
        await updateVoceListino(selected.id, voceEdit.id, {
          prezzo_override: payload.prezzo_override,
          sconto_percentuale: payload.sconto_percentuale,
          note: payload.note,
        });
        toast('Voce aggiornata');
      }
      setVoceEdit(null);
      loadVoci(selected.id);
    } catch (e) { toast(e?.response?.data?.detail || 'Errore', 'error'); }
    finally { setSavingVoce(false); }
  };

  const handleDeleteVoce = async (voceId) => {
    if (!window.confirm('Rimuovere questo prodotto dal listino?')) return;
    try {
      await deleteVoceListino(selected.id, voceId);
      toast('Prodotto rimosso');
      loadVoci(selected.id);
    } catch { toast('Errore', 'error'); }
  };

  // ── Prezzo finale preview ────────────────────────────────────────────────
  const prezzoPreview = () => {
    const prodotto = prodotti.find(p => p.id === Number(voceForm.prodotto_id));
    if (!prodotto) return null;
    const override = voceForm.prezzo_override !== '' ? Number(voceForm.prezzo_override) : null;
    const sconto = Number(voceForm.sconto_percentuale) || 0;
    const finale = override != null ? override : prodotto.prezzo_base * (1 - sconto / 100);
    return { base: prodotto.prezzo_base, finale, unita: prodotto.unita_misura };
  };

  const preview = voceEdit ? prezzoPreview() : null;

  const prodottiDisponibili = prodotti.filter(p => !voci.some(v => v.prodotto_id === p.id && (!voceEdit || voceEdit.mode !== 'edit' || v.id !== voceEdit.id)));

  const fv = (key) => ({
    value: voceForm[key],
    onChange: (e) => setVoceForm(f => ({ ...f, [key]: e.target.value })),
  });

  return (
    <div className="listini-manager">
      {success && <div className="toast toast-success">{success}</div>}
      {error && <div className="toast toast-error">{error}</div>}

      <div className="listini-layout">

        {/* ── Pannello sinistro: lista listini ── */}
        <aside className="listini-sidebar">
          <div className="sidebar-header">
            <h2>Listini</h2>
            <button className="btn-primary btn-sm" onClick={openCreate}>+ Nuovo</button>
          </div>

          <div className="sidebar-filters">
            <input className="search-input" placeholder="Cerca listino…"
              value={filters.search} onChange={e => setFilters(f => ({ ...f, search: e.target.value }))} />
            <select className="filter-select-sm" value={filters.tipo_cliente}
              onChange={e => setFilters(f => ({ ...f, tipo_cliente: e.target.value }))}>
              <option value="">Tutti i tipi</option>
              {TIPI_CLIENTE.map(t => <option key={t} value={t}>{TIPO_LABELS[t]}</option>)}
            </select>
          </div>

          {loading ? <div className="loading-spinner">…</div> : (
            <ul className="listini-list">
              {listini.length === 0 && <li className="empty-item">Nessun listino.</li>}
              {listini.map(l => (
                <li key={l.id}
                  className={`listino-item ${selected?.id === l.id ? 'active' : ''} ${!l.attivo ? 'inactive' : ''}`}
                  onClick={() => setSelected(l)}>
                  <div className="listino-item-top">
                    <span className="listino-nome">{l.nome}</span>
                    <span className="tipo-chip" style={{ background: TIPO_COLORS[l.tipo_cliente] + '22', color: TIPO_COLORS[l.tipo_cliente] }}>
                      {TIPO_LABELS[l.tipo_cliente]}
                    </span>
                  </div>
                  {l.descrizione && <div className="listino-desc">{l.descrizione}</div>}
                  {!l.attivo && <span className="badge badge-inactive">Inattivo</span>}
                  <div className="listino-item-actions" onClick={e => e.stopPropagation()}>
                    <button className="btn-xs" onClick={() => openEdit(l)}>✏️</button>
                    {l.attivo && <button className="btn-xs btn-xs-danger" onClick={() => handleDeleteListino(l)}>🗑</button>}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </aside>

        {/* ── Pannello destro: voci del listino ── */}
        <main className="voci-panel">
          {!selected ? (
            <div className="voci-empty-state">
              <div>📋</div>
              <p>Seleziona un listino per gestire le voci</p>
            </div>
          ) : (
            <>
              <div className="voci-header">
                <div>
                  <h3>{selected.nome}</h3>
                  <span className="voci-subtitle">
                    {TIPO_LABELS[selected.tipo_cliente]} — {voci.length} prodott{voci.length === 1 ? 'o' : 'i'}
                  </span>
                </div>
                <button className="btn-primary" onClick={openNewVoce} disabled={prodottiDisponibili.length === 0}>
                  + Aggiungi prodotto
                </button>
              </div>

              {/* ── Form aggiunta/modifica voce ── */}
              {voceEdit && (
                <div className="voce-form-card">
                  <div className="voce-form-grid">
                    <div className="form-group">
                      <label>Prodotto *</label>
                      {voceEdit.mode === 'create' ? (
                        <select value={voceForm.prodotto_id} onChange={e => setVoceForm(f => ({ ...f, prodotto_id: e.target.value }))}>
                          <option value="">— Seleziona —</option>
                          {prodottiDisponibili.map(p => (
                            <option key={p.id} value={p.id}>{p.nome} ({fmt(p.prezzo_base)}/{p.unita_misura})</option>
                          ))}
                        </select>
                      ) : (
                        <input readOnly value={prodotti.find(p => p.id === voceForm.prodotto_id)?.nome || '—'} />
                      )}
                    </div>
                    <div className="form-group">
                      <label>Prezzo override (€)</label>
                      <input {...fv('prezzo_override')} type="number" min={0} step={0.01} placeholder="Lascia vuoto = usa prezzo base" />
                    </div>
                    <div className="form-group">
                      <label>Sconto %</label>
                      <input {...fv('sconto_percentuale')} type="number" min={0} max={100} step={0.5} placeholder="0" />
                    </div>
                    <div className="form-group">
                      <label>Note</label>
                      <input {...fv('note')} placeholder="Note sulla voce…" />
                    </div>
                  </div>

                  {preview && (
                    <div className="prezzo-preview">
                      Prezzo base: <strong>{fmt(preview.base)}</strong>
                      {' → '}Prezzo finale: <strong className="finale">{fmt(preview.finale)}</strong>
                      <span className="preview-unit">/{preview.unita}</span>
                    </div>
                  )}

                  <div className="voce-form-actions">
                    <button className="btn-secondary btn-sm" onClick={() => setVoceEdit(null)}>Annulla</button>
                    <button className="btn-primary btn-sm" onClick={handleSaveVoce} disabled={savingVoce}>
                      {savingVoce ? '…' : voceEdit.mode === 'create' ? 'Aggiungi' : 'Salva'}
                    </button>
                  </div>
                </div>
              )}

              {/* ── Tabella voci ── */}
              {vociLoading ? <div className="loading-spinner">Caricamento voci…</div> : (
                <div className="voci-table-wrap">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Prodotto</th>
                        <th>Tipo</th>
                        <th>Prezzo base</th>
                        <th>Override</th>
                        <th>Sconto</th>
                        <th>Prezzo finale</th>
                        <th>Note</th>
                        <th>Azioni</th>
                      </tr>
                    </thead>
                    <tbody>
                      {voci.length === 0 && (
                        <tr><td colSpan={8} className="empty-cell">Nessun prodotto in questo listino.</td></tr>
                      )}
                      {voci.map(v => (
                        <tr key={v.id}>
                          <td>
                            <strong>{v.prodotto?.nome || '—'}</strong>
                            {v.prodotto?.codice && <div className="sub-text mono">{v.prodotto.codice}</div>}
                          </td>
                          <td>
                            {v.prodotto?.tipo && (
                              <span className={`tipo-badge tipo-${v.prodotto.tipo}`}>{v.prodotto.tipo}</span>
                            )}
                          </td>
                          <td>{v.prodotto ? fmt(v.prodotto.prezzo_base) : '—'}</td>
                          <td>{v.prezzo_override != null ? fmt(v.prezzo_override) : <span className="text-muted">—</span>}</td>
                          <td>{v.sconto_percentuale > 0 ? `${v.sconto_percentuale}%` : <span className="text-muted">—</span>}</td>
                          <td><strong className="prezzo-finale-cell">{fmt(v.prezzo_finale)}</strong></td>
                          <td>{v.note || <span className="text-muted">—</span>}</td>
                          <td className="action-cell">
                            <button className="btn-sm btn-secondary" onClick={() => openEditVoce(v)}>Modifica</button>
                            <button className="btn-sm btn-danger" onClick={() => handleDeleteVoce(v.id)}>Rimuovi</button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </main>
      </div>

      {/* ── Modal listino ── */}
      {modal && (
        <div className="modal-overlay" onClick={() => setModal(null)}>
          <div className="modal-box" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{modal.mode === 'create' ? 'Nuovo Listino' : 'Modifica Listino'}</h3>
              <button className="modal-close" onClick={() => setModal(null)}>×</button>
            </div>
            <div className="modal-body">
              <div className={`form-group ${formErrors.nome ? 'has-error' : ''}`}>
                <label>Nome *</label>
                <input value={form.nome} onChange={e => setForm(f => ({ ...f, nome: e.target.value }))} placeholder="Nome listino" />
                {formErrors.nome && <span className="field-error">{formErrors.nome}</span>}
              </div>
              <div className="form-group">
                <label>Tipo cliente</label>
                <select value={form.tipo_cliente} onChange={e => setForm(f => ({ ...f, tipo_cliente: e.target.value }))}>
                  {TIPI_CLIENTE.map(t => <option key={t} value={t}>{TIPO_LABELS[t]}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>Descrizione</label>
                <textarea value={form.descrizione} onChange={e => setForm(f => ({ ...f, descrizione: e.target.value }))}
                  rows={2} placeholder="Descrizione del listino…" />
              </div>
              <div className="form-group form-check">
                <label>
                  <input type="checkbox" checked={form.attivo}
                    onChange={e => setForm(f => ({ ...f, attivo: e.target.checked }))} />
                  {' '}Attivo
                </label>
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn-secondary" onClick={() => setModal(null)}>Annulla</button>
              <button className="btn-primary" onClick={handleSaveListino} disabled={saving}>
                {saving ? 'Salvataggio…' : 'Salva'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
