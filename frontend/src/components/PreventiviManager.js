import React, { useState, useEffect, useCallback } from 'react';
import {
  getPreventivi, getPreventivo, createPreventivo, updatePreventivo, deletePreventivo,
  inviaPreventivo, accettaPreventivo, rifiutaPreventivo, convertiInOrdine,
  downloadPreventivoPDF, addRigaPreventivo, updateRigaPreventivo, deleteRigaPreventivo,
  getProdotti, getAziendeClienti, getListini, getConsulenti,
} from '../services/apiService';
import './PreventiviManager.css';

const fmt = (n) => new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR' }).format(n ?? 0);
const fmtDate = (d) => d ? new Date(d).toLocaleDateString('it-IT') : '—';

const STATO_CONFIG = {
  bozza:     { label: 'Bozza',     color: '#64748b', bg: '#f1f5f9' },
  inviato:   { label: 'Inviato',   color: '#2563eb', bg: '#dbeafe' },
  accettato: { label: 'Accettato', color: '#16a34a', bg: '#dcfce7' },
  rifiutato: { label: 'Rifiutato', color: '#dc2626', bg: '#fee2e2' },
};

const StatoBadge = ({ stato }) => {
  const cfg = STATO_CONFIG[stato] || { label: stato, color: '#666', bg: '#f1f5f9' };
  return (
    <span className="stato-badge" style={{ color: cfg.color, background: cfg.bg }}>
      {cfg.label}
    </span>
  );
};

const EMPTY_FORM = {
  azienda_cliente_id: '', listino_id: '', consulente_id: '',
  oggetto: '', data_scadenza: '', note: '',
};

const EMPTY_RIGA = {
  prodotto_id: '', descrizione_custom: '', quantita: 1,
  prezzo_unitario: 0, sconto_percentuale: 0, ordine: 0,
};

export default function PreventiviManager() {
  const [preventivi, setPreventivi] = useState([]);
  const [total, setTotal] = useState(0);
  const [filters, setFilters] = useState({ search: '', stato: '', page: 1, limit: 20 });
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(null);
  const [error, setError] = useState(null);

  // Modal create/edit
  const [modal, setModal] = useState(null); // null | { mode: 'create'|'edit', data?: obj }
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

  // Modal dettaglio (righe)
  const [dettaglio, setDettaglio] = useState(null); // preventivo completo con righe
  const [rigaForm, setRigaForm] = useState(EMPTY_RIGA);
  const [editingRiga, setEditingRiga] = useState(null); // riga id in edit
  const [savingRiga, setSavingRiga] = useState(false);

  // Lookup data
  const [aziende, setAziende] = useState([]);
  const [listini, setListini] = useState([]);
  const [consulenti, setConsulenti] = useState([]);
  const [prodotti, setProdotti] = useState([]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = { limit: filters.limit, skip: (filters.page - 1) * filters.limit };
      if (filters.search) params.search = filters.search;
      if (filters.stato) params.stato = filters.stato;
      const data = await getPreventivi(params);
      setPreventivi(data.items || []);
      setTotal(data.total || 0);
    } catch { setError('Errore caricamento preventivi'); }
    finally { setLoading(false); }
  }, [filters]);

  useEffect(() => { load(); }, [load]);

  // Load lookup data once
  useEffect(() => {
    getAziendeClienti({ limit: 300 }).then(d => setAziende(Array.isArray(d) ? d : (d.items || []))).catch(() => {});
    getListini({ limit: 100 }).then(d => setListini(Array.isArray(d) ? d : (d.items || []))).catch(() => {});
    getConsulenti({ limit: 300 }).then(d => setConsulenti(Array.isArray(d) ? d : (d.items || []))).catch(() => {});
    getProdotti({ limit: 500, attivo: true }).then(d => setProdotti(Array.isArray(d) ? d : [])).catch(() => {});
  }, []);

  const toast = (msg, type = 'success') => {
    type === 'success' ? setSuccess(msg) : setError(msg);
    setTimeout(() => { setSuccess(null); setError(null); }, 3500);
  };

  // ── Modal create/edit ────────────────────

  const openCreate = () => { setForm(EMPTY_FORM); setModal({ mode: 'create' }); };
  const openEdit = (p) => {
    setForm({
      azienda_cliente_id: p.azienda_cliente_id || '',
      listino_id: p.listino_id || '',
      consulente_id: p.consulente_id || '',
      oggetto: p.oggetto || '',
      data_scadenza: p.data_scadenza ? p.data_scadenza.slice(0, 10) : '',
      note: p.note || '',
    });
    setModal({ mode: 'edit', data: p });
  };

  const handleSave = async () => {
    setSaving(true);
    const payload = {
      ...form,
      azienda_cliente_id: form.azienda_cliente_id ? Number(form.azienda_cliente_id) : null,
      listino_id: form.listino_id ? Number(form.listino_id) : null,
      consulente_id: form.consulente_id ? Number(form.consulente_id) : null,
      data_scadenza: form.data_scadenza || null,
      righe: [],
    };
    try {
      if (modal.mode === 'create') {
        await createPreventivo(payload);
        toast('Preventivo creato');
      } else {
        await updatePreventivo(modal.data.id, payload);
        toast('Preventivo aggiornato');
      }
      setModal(null);
      load();
    } catch (e) {
      toast(e?.response?.data?.detail || 'Errore nel salvataggio', 'error');
    } finally { setSaving(false); }
  };

  // ── Stato machine ────────────────────────

  const handleStato = async (p, action) => {
    const map = { invia: inviaPreventivo, accetta: accettaPreventivo, rifiuta: rifiutaPreventivo };
    try {
      await map[action](p.id);
      toast(`Preventivo ${action === 'invia' ? 'inviato' : action === 'accetta' ? 'accettato' : 'rifiutato'}`);
      load();
      if (dettaglio?.id === p.id) openDettaglio(p.id);
    } catch (e) { toast(e?.response?.data?.detail || 'Errore', 'error'); }
  };

  const handleConverti = async (p) => {
    if (!window.confirm(`Convertire "${p.numero}" in ordine?`)) return;
    try {
      await convertiInOrdine(p.id);
      toast('Ordine creato');
      load();
    } catch (e) { toast(e?.response?.data?.detail || 'Errore', 'error'); }
  };

  const handleDelete = async (p) => {
    if (!window.confirm(`Eliminare il preventivo "${p.numero}"?`)) return;
    try { await deletePreventivo(p.id); toast('Preventivo eliminato'); load(); }
    catch { toast('Errore', 'error'); }
  };

  // ── PDF ──────────────────────────────────

  const handlePDF = async (p) => {
    try {
      const blob = await downloadPreventivoPDF(p.id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `preventivo_${p.numero}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch { toast('Errore generazione PDF', 'error'); }
  };

  // ── Dettaglio con righe ──────────────────

  const openDettaglio = async (id) => {
    try {
      const data = await getPreventivo(id);
      setDettaglio(data);
      setRigaForm(EMPTY_RIGA);
      setEditingRiga(null);
    } catch { toast('Errore caricamento dettaglio', 'error'); }
  };

  const refreshDettaglio = async () => {
    if (!dettaglio) return;
    const data = await getPreventivo(dettaglio.id);
    setDettaglio(data);
    load(); // aggiorna totale nella lista
  };

  const handleAddRiga = async () => {
    if (!dettaglio) return;
    setSavingRiga(true);
    const payload = {
      prodotto_id: rigaForm.prodotto_id ? Number(rigaForm.prodotto_id) : null,
      descrizione_custom: rigaForm.descrizione_custom || null,
      quantita: Number(rigaForm.quantita) || 1,
      prezzo_unitario: Number(rigaForm.prezzo_unitario) || 0,
      sconto_percentuale: Number(rigaForm.sconto_percentuale) || 0,
      ordine: Number(rigaForm.ordine) || 0,
    };
    try {
      if (editingRiga) {
        await updateRigaPreventivo(dettaglio.id, editingRiga, payload);
        toast('Riga aggiornata');
      } else {
        await addRigaPreventivo(dettaglio.id, payload);
        toast('Riga aggiunta');
      }
      setRigaForm(EMPTY_RIGA);
      setEditingRiga(null);
      await refreshDettaglio();
    } catch (e) { toast(e?.response?.data?.detail || 'Errore', 'error'); }
    finally { setSavingRiga(false); }
  };

  const handleEditRiga = (riga) => {
    setEditingRiga(riga.id);
    setRigaForm({
      prodotto_id: riga.prodotto_id || '',
      descrizione_custom: riga.descrizione_custom || '',
      quantita: riga.quantita,
      prezzo_unitario: riga.prezzo_unitario,
      sconto_percentuale: riga.sconto_percentuale,
      ordine: riga.ordine,
    });
  };

  const handleDeleteRiga = async (rigaId) => {
    try {
      await deleteRigaPreventivo(dettaglio.id, rigaId);
      await refreshDettaglio();
    } catch { toast('Errore', 'error'); }
  };

  // Calcola importo preview riga
  const importoPreview = () => {
    const q = Number(rigaForm.quantita) || 0;
    const p = Number(rigaForm.prezzo_unitario) || 0;
    const s = Number(rigaForm.sconto_percentuale) || 0;
    return q * p * (1 - s / 100);
  };

  // Auto-fill prezzo da prodotto selezionato
  const handleProdottoChange = (prodottoId) => {
    const prod = prodotti.find(p => p.id === Number(prodottoId));
    setRigaForm(f => ({
      ...f,
      prodotto_id: prodottoId,
      prezzo_unitario: prod ? prod.prezzo_base : f.prezzo_unitario,
      descrizione_custom: f.descrizione_custom || '',
    }));
  };

  const pages = Math.ceil(total / filters.limit) || 1;
  const f = (key) => ({ value: form[key], onChange: (e) => setForm(ff => ({ ...ff, [key]: e.target.value })) });
  const rf = (key) => ({ value: rigaForm[key], onChange: (e) => setRigaForm(ff => ({ ...ff, [key]: e.target.value })) });

  return (
    <div className="preventivi-manager">
      <div className="preventivi-header">
        <div>
          <h2>Preventivi</h2>
          <span className="count-badge">{total} preventivi</span>
        </div>
        <button className="btn-primary" onClick={openCreate}>+ Nuovo Preventivo</button>
      </div>

      {success && <div className="toast toast-success">{success}</div>}
      {error && <div className="toast toast-error">{error}</div>}

      {/* Filtri */}
      <div className="preventivi-filters">
        <input className="search-input" placeholder="Cerca numero, oggetto…"
          value={filters.search}
          onChange={e => setFilters(f => ({ ...f, search: e.target.value, page: 1 }))} />
        <select className="filter-select-sm" value={filters.stato}
          onChange={e => setFilters(f => ({ ...f, stato: e.target.value, page: 1 }))}>
          <option value="">Tutti gli stati</option>
          <option value="bozza">Bozza</option>
          <option value="inviato">Inviato</option>
          <option value="accettato">Accettato</option>
          <option value="rifiutato">Rifiutato</option>
        </select>
      </div>

      {/* Tabella */}
      {loading ? <div className="loading-spinner">Caricamento…</div> : (
        <div className="preventivi-table-wrap">
          <table className="preventivi-table">
            <thead>
              <tr>
                <th>Numero</th>
                <th>Cliente</th>
                <th>Oggetto</th>
                <th>Scadenza</th>
                <th>Stato</th>
                <th className="right">Totale</th>
                <th>Azioni</th>
              </tr>
            </thead>
            <tbody>
              {preventivi.length === 0 && (
                <tr><td colSpan={7} className="empty-state">Nessun preventivo trovato.</td></tr>
              )}
              {preventivi.map(p => (
                <tr key={p.id}>
                  <td>
                    <button className="link-btn" onClick={() => openDettaglio(p.id)}>{p.numero}</button>
                  </td>
                  <td>{p.azienda_cliente?.ragione_sociale || <span className="muted">—</span>}</td>
                  <td className="muted">{p.oggetto || '—'}</td>
                  <td className="muted">{fmtDate(p.data_scadenza)}</td>
                  <td><StatoBadge stato={p.stato} /></td>
                  <td className="right bold">{fmt(p.totale)}</td>
                  <td>
                    <div className="row-actions">
                      <button className="btn-sm btn-secondary" onClick={() => openEdit(p)}>Modifica</button>
                      {p.stato === 'bozza' && (
                        <button className="btn-sm btn-info" onClick={() => handleStato(p, 'invia')}>Invia</button>
                      )}
                      {p.stato === 'inviato' && (
                        <>
                          <button className="btn-sm btn-success" onClick={() => handleStato(p, 'accetta')}>Accetta</button>
                          <button className="btn-sm btn-danger" onClick={() => handleStato(p, 'rifiuta')}>Rifiuta</button>
                        </>
                      )}
                      {p.stato === 'accettato' && !p.ordine_id && (
                        <button className="btn-sm btn-primary" onClick={() => handleConverti(p)}>→ Ordine</button>
                      )}
                      <button className="btn-sm btn-secondary" onClick={() => handlePDF(p)}>PDF</button>
                      <button className="btn-sm btn-danger" onClick={() => handleDelete(p)}>Elimina</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Paginazione */}
      {pages > 1 && (
        <div className="pagination">
          <button disabled={filters.page === 1} onClick={() => setFilters(f => ({ ...f, page: f.page - 1 }))}>‹</button>
          <span>{filters.page} / {pages}</span>
          <button disabled={filters.page >= pages} onClick={() => setFilters(f => ({ ...f, page: f.page + 1 }))}>›</button>
        </div>
      )}

      {/* Modal create/edit */}
      {modal && (
        <div className="modal-overlay" onClick={() => setModal(null)}>
          <div className="modal-box modal-lg" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{modal.mode === 'create' ? 'Nuovo Preventivo' : 'Modifica Preventivo'}</h3>
              <button className="modal-close" onClick={() => setModal(null)}>×</button>
            </div>
            <div className="modal-body modal-grid-2">
              <div className="form-group">
                <label>Cliente</label>
                <select {...f('azienda_cliente_id')}>
                  <option value="">— Seleziona azienda —</option>
                  {aziende.map(a => <option key={a.id} value={a.id}>{a.ragione_sociale}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>Listino (opzionale)</label>
                <select {...f('listino_id')}>
                  <option value="">— Nessun listino —</option>
                  {listini.map(l => <option key={l.id} value={l.id}>{l.nome}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>Consulente (opzionale)</label>
                <select {...f('consulente_id')}>
                  <option value="">— Nessun consulente —</option>
                  {consulenti.map(c => <option key={c.id} value={c.id}>{c.nome} {c.cognome}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>Data scadenza</label>
                <input type="date" {...f('data_scadenza')} />
              </div>
              <div className="form-group form-group-full">
                <label>Oggetto</label>
                <input {...f('oggetto')} placeholder="Oggetto del preventivo" />
              </div>
              <div className="form-group form-group-full">
                <label>Note</label>
                <textarea {...f('note')} rows={3} placeholder="Note aggiuntive…" />
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

      {/* Modal dettaglio / righe */}
      {dettaglio && (
        <div className="modal-overlay" onClick={() => setDettaglio(null)}>
          <div className="modal-box modal-xl" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h3>{dettaglio.numero}</h3>
                <div className="dettaglio-meta">
                  <StatoBadge stato={dettaglio.stato} />
                  {dettaglio.oggetto && <span className="muted">{dettaglio.oggetto}</span>}
                </div>
              </div>
              <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                {dettaglio.stato === 'bozza' && (
                  <button className="btn-sm btn-info" onClick={() => handleStato(dettaglio, 'invia')}>Invia</button>
                )}
                {dettaglio.stato === 'inviato' && (
                  <>
                    <button className="btn-sm btn-success" onClick={() => handleStato(dettaglio, 'accetta')}>Accetta</button>
                    <button className="btn-sm btn-danger" onClick={() => handleStato(dettaglio, 'rifiuta')}>Rifiuta</button>
                  </>
                )}
                {dettaglio.stato === 'accettato' && (
                  <button className="btn-sm btn-primary" onClick={() => handleConverti(dettaglio)}>→ Ordine</button>
                )}
                <button className="btn-sm btn-secondary" onClick={() => handlePDF(dettaglio)}>PDF</button>
                <button className="modal-close" onClick={() => setDettaglio(null)}>×</button>
              </div>
            </div>

            <div className="modal-body">
              {/* Riga form */}
              <div className="riga-form-section">
                <h4>{editingRiga ? 'Modifica riga' : '+ Aggiungi riga'}</h4>
                <div className="riga-form-grid">
                  <div className="form-group">
                    <label>Prodotto</label>
                    <select value={rigaForm.prodotto_id}
                      onChange={e => handleProdottoChange(e.target.value)}>
                      <option value="">— Riga libera —</option>
                      {prodotti.map(p => <option key={p.id} value={p.id}>{p.nome}</option>)}
                    </select>
                  </div>
                  <div className="form-group">
                    <label>Descrizione</label>
                    <input {...rf('descrizione_custom')} placeholder="Descrizione personalizzata" />
                  </div>
                  <div className="form-group">
                    <label>Qtà</label>
                    <input type="number" min={0.01} step={0.01} {...rf('quantita')} />
                  </div>
                  <div className="form-group">
                    <label>Prezzo unit. (€)</label>
                    <input type="number" min={0} step={0.01} {...rf('prezzo_unitario')} />
                  </div>
                  <div className="form-group">
                    <label>Sconto %</label>
                    <input type="number" min={0} max={100} step={0.1} {...rf('sconto_percentuale')} />
                  </div>
                  <div className="form-group" style={{ alignSelf: 'end' }}>
                    <label>Importo</label>
                    <div className="importo-preview">{fmt(importoPreview())}</div>
                  </div>
                </div>
                <div className="riga-form-actions">
                  <button className="btn-primary btn-sm" onClick={handleAddRiga} disabled={savingRiga}>
                    {savingRiga ? '…' : editingRiga ? 'Aggiorna riga' : 'Aggiungi riga'}
                  </button>
                  {editingRiga && (
                    <button className="btn-secondary btn-sm" onClick={() => { setEditingRiga(null); setRigaForm(EMPTY_RIGA); }}>
                      Annulla
                    </button>
                  )}
                </div>
              </div>

              {/* Tabella righe */}
              {dettaglio.righe?.length > 0 && (
                <table className="righe-table">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Descrizione</th>
                      <th className="right">Qtà</th>
                      <th className="right">Prezzo unit.</th>
                      <th className="right">Sconto</th>
                      <th className="right">Importo</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {dettaglio.righe.map((r, i) => (
                      <tr key={r.id}>
                        <td className="muted">{i + 1}</td>
                        <td>{r.descrizione_custom || r.prodotto?.nome || <span className="muted">—</span>}</td>
                        <td className="right">{r.quantita}</td>
                        <td className="right">{fmt(r.prezzo_unitario)}</td>
                        <td className="right">{r.sconto_percentuale > 0 ? `${r.sconto_percentuale}%` : '—'}</td>
                        <td className="right bold">{fmt(r.importo)}</td>
                        <td>
                          <div className="row-actions">
                            <button className="btn-sm btn-secondary" onClick={() => handleEditRiga(r)}>Mod</button>
                            <button className="btn-sm btn-danger" onClick={() => handleDeleteRiga(r.id)}>✕</button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr>
                      <td colSpan={5} className="right bold" style={{ paddingRight: '0.75rem' }}>TOTALE</td>
                      <td className="right bold totale-cell">{fmt(dettaglio.totale)}</td>
                      <td></td>
                    </tr>
                  </tfoot>
                </table>
              )}

              {dettaglio.righe?.length === 0 && (
                <div className="empty-state">Nessuna riga. Usa il form sopra per aggiungerne.</div>
              )}
            </div>

            <div className="modal-footer">
              <button className="btn-secondary" onClick={() => setDettaglio(null)}>Chiudi</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
