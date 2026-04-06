import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  addVocePianoFinanziario,
  createPianoFinanziario,
  deletePianoFinanziario,
  deleteVocePianoFinanziario,
  getPianiFinanziari,
  getPianoFinanziario,
  getProjects,
  getVociPianoFinanziario,
  updatePianoFinanziario,
  updateVocePianoFinanziario,
} from '../services/apiService';
import './PianiFinanziariManager.css';

const STATI_PIANO = [
  { value: '', label: 'Tutti gli stati' },
  { value: 'bozza', label: 'Bozza' },
  { value: 'approvato', label: 'Approvato' },
  { value: 'in_corso', label: 'In corso' },
  { value: 'rendicontato', label: 'Rendicontato' },
  { value: 'chiuso', label: 'Chiuso' },
];

const TIPI_FONDO = [
  { value: 'formazienda', label: 'Formazienda' },
  { value: 'fondimpresa', label: 'Fondimpresa' },
  { value: 'fse', label: 'FSE' },
  { value: 'altro', label: 'Altro' },
];

const CATEGORIE_VOCE = [
  { value: 'docenza', label: 'Docenza' },
  { value: 'tutoraggio', label: 'Tutoraggio' },
  { value: 'coordinamento', label: 'Coordinamento' },
  { value: 'materiali', label: 'Materiali' },
  { value: 'aula', label: 'Aula' },
  { value: 'altro', label: 'Altro' },
];

const modalOverlayStyle = {
  position: 'fixed',
  inset: 0,
  background: 'rgba(15, 23, 42, 0.45)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  padding: '1.5rem',
  zIndex: 1000,
};

const modalCardStyle = {
  width: 'min(760px, 100%)',
  maxHeight: '90vh',
  overflow: 'auto',
  background: '#fff',
  borderRadius: '20px',
  border: '1px solid #dbe4f0',
  boxShadow: '0 24px 60px rgba(15, 23, 42, 0.18)',
  padding: '1.5rem',
};

const progressTrackStyle = {
  width: '100%',
  height: '12px',
  borderRadius: '999px',
  background: '#e2e8f0',
  overflow: 'hidden',
};

const fmtCurrency = (value) => new Intl.NumberFormat('it-IT', {
  style: 'currency',
  currency: 'EUR',
  minimumFractionDigits: 2,
}).format(Number(value || 0));

const formatDateTimeLocal = (value) => {
  if (!value) {
    return '';
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return '';
  }
  const year = parsed.getFullYear();
  const month = String(parsed.getMonth() + 1).padStart(2, '0');
  const day = String(parsed.getDate()).padStart(2, '0');
  const hours = String(parsed.getHours()).padStart(2, '0');
  const minutes = String(parsed.getMinutes()).padStart(2, '0');
  return `${year}-${month}-${day}T${hours}:${minutes}`;
};

const toIsoString = (value) => {
  if (!value) {
    return null;
  }
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed.toISOString();
};

const parseNumber = (value) => {
  if (value === null || value === undefined || value === '') {
    return 0;
  }
  const normalized = String(value).replace(',', '.').replace(/[^\d.-]/g, '');
  const parsed = Number.parseFloat(normalized);
  return Number.isFinite(parsed) ? parsed : 0;
};

const createEmptyPianoForm = () => ({
  progetto_id: '',
  nome: '',
  tipo_fondo: 'formazienda',
  budget_totale: '',
  data_inizio: '',
  data_fine: '',
  stato: 'bozza',
  note: '',
});

const createEmptyVoceForm = (pianoId = '') => ({
  piano_id: pianoId,
  categoria: 'altro',
  descrizione: '',
  importo_preventivo: '',
  importo_consuntivo: '',
  collaborator_id: '',
});

function BudgetProgress({ totale, utilizzato }) {
  const total = Number(totale || 0);
  const used = Number(utilizzato || 0);
  const percentage = total > 0 ? (used / total) * 100 : 0;
  const isOverBudget = used > total && total > 0;
  const barColor = isOverBudget ? '#dc2626' : percentage >= 80 ? '#d97706' : '#16a34a';

  return (
    <div>
      <div style={progressTrackStyle}>
        <div
          style={{
            width: `${Math.max(0, Math.min(percentage, 100))}%`,
            height: '100%',
            background: barColor,
            transition: 'width 180ms ease',
          }}
        />
      </div>
      <div className="summary-meta" style={{ marginTop: '0.45rem' }}>
        <span>{fmtCurrency(used)} / {fmtCurrency(total)}</span>
        <span style={{ color: isOverBudget ? '#b91c1c' : '#475569', fontWeight: 700 }}>
          {percentage.toFixed(1)}%
        </span>
      </div>
    </div>
  );
}

export default function PianoFinanziarioManager() {
  const [projects, setProjects] = useState([]);
  const [piani, setPiani] = useState([]);
  const [selectedPianoId, setSelectedPianoId] = useState('');
  const [selectedPiano, setSelectedPiano] = useState(null);
  const [voci, setVoci] = useState([]);
  const [filters, setFilters] = useState({ progetto_id: '', stato: '' });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [showPianoModal, setShowPianoModal] = useState(false);
  const [showVoceModal, setShowVoceModal] = useState(false);
  const [editingPiano, setEditingPiano] = useState(null);
  const [editingVoce, setEditingVoce] = useState(null);
  const [pianoForm, setPianoForm] = useState(createEmptyPianoForm());
  const [voceForm, setVoceForm] = useState(createEmptyVoceForm());

  const projectMap = useMemo(
    () => Object.fromEntries((projects || []).map((project) => [String(project.id), project])),
    [projects],
  );

  const clearNotice = () => {
    setError('');
    setMessage('');
  };

  const loadProjects = useCallback(async () => {
    const data = await getProjects(0, 500);
    setProjects(Array.isArray(data) ? data : []);
  }, []);

  const loadPiani = useCallback(async (activeFilters = filters) => {
    const params = { limit: 200 };
    if (activeFilters.progetto_id) {
      params.progetto_id = activeFilters.progetto_id;
    }
    if (activeFilters.stato) {
      params.stato = activeFilters.stato;
    }
    const data = await getPianiFinanziari(params);
    setPiani(Array.isArray(data) ? data : []);
  }, [filters]);

  const loadPianoDetail = useCallback(async (pianoId) => {
    if (!pianoId) {
      setSelectedPiano(null);
      setVoci([]);
      return;
    }
    const [piano, pianoVoci] = await Promise.all([
      getPianoFinanziario(pianoId),
      getVociPianoFinanziario(pianoId),
    ]);
    setSelectedPiano(piano);
    setVoci(Array.isArray(pianoVoci) ? pianoVoci : []);
  }, []);

  useEffect(() => {
    let mounted = true;
    const bootstrap = async () => {
      setLoading(true);
      try {
        await loadProjects();
        await loadPiani();
      } catch (err) {
        if (mounted) {
          setError(err?.response?.data?.detail || 'Errore nel caricamento dei piani finanziari');
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    };
    bootstrap();
    return () => {
      mounted = false;
    };
  }, [loadPiani, loadProjects]);

  useEffect(() => {
    if (!selectedPianoId) {
      return;
    }
    loadPianoDetail(selectedPianoId).catch((err) => {
      setError(err?.response?.data?.detail || 'Errore nel caricamento del dettaglio piano');
    });
  }, [selectedPianoId, loadPianoDetail]);

  const refreshAll = useCallback(async (keepSelectedId = selectedPianoId) => {
    await loadPiani();
    if (keepSelectedId) {
      await loadPianoDetail(keepSelectedId);
    }
  }, [loadPiani, loadPianoDetail, selectedPianoId]);

  const handleFilterChange = async (key, value) => {
    clearNotice();
    const nextFilters = { ...filters, [key]: value };
    setFilters(nextFilters);
    setSelectedPianoId('');
    setSelectedPiano(null);
    setVoci([]);
    try {
      setLoading(true);
      await loadPiani(nextFilters);
    } catch (err) {
      setError(err?.response?.data?.detail || 'Errore nell\'applicazione dei filtri');
    } finally {
      setLoading(false);
    }
  };

  const openCreatePianoModal = () => {
    clearNotice();
    setEditingPiano(null);
    setPianoForm(createEmptyPianoForm());
    setShowPianoModal(true);
  };

  const openEditPianoModal = () => {
    if (!selectedPiano) {
      return;
    }
    clearNotice();
    setEditingPiano(selectedPiano);
    setPianoForm({
      progetto_id: String(selectedPiano.progetto_id || ''),
      nome: selectedPiano.nome || '',
      tipo_fondo: selectedPiano.tipo_fondo || 'formazienda',
      budget_totale: String(selectedPiano.budget_totale ?? ''),
      data_inizio: formatDateTimeLocal(selectedPiano.data_inizio),
      data_fine: formatDateTimeLocal(selectedPiano.data_fine),
      stato: selectedPiano.stato || 'bozza',
      note: selectedPiano.note || '',
    });
    setShowPianoModal(true);
  };

  const handleSavePiano = async (event) => {
    event.preventDefault();
    clearNotice();
    setSaving(true);
    try {
      const payload = {
        nome: pianoForm.nome.trim(),
        tipo_fondo: pianoForm.tipo_fondo,
        budget_totale: parseNumber(pianoForm.budget_totale),
        budget_utilizzato: selectedPiano?.budget_utilizzato || 0,
        data_inizio: toIsoString(pianoForm.data_inizio),
        data_fine: toIsoString(pianoForm.data_fine),
        stato: pianoForm.stato,
        note: pianoForm.note.trim() || null,
      };

      let saved;
      if (editingPiano) {
        saved = await updatePianoFinanziario(editingPiano.id, payload);
        setMessage('Piano finanziario aggiornato con successo');
      } else {
        saved = await createPianoFinanziario({
          ...payload,
          progetto_id: Number(pianoForm.progetto_id),
        });
        setMessage('Piano finanziario creato con successo');
      }

      setShowPianoModal(false);
      setSelectedPianoId(String(saved.id));
      await refreshAll(String(saved.id));
    } catch (err) {
      setError(err?.response?.data?.detail || 'Errore nel salvataggio del piano');
    } finally {
      setSaving(false);
    }
  };

  const handleDeletePiano = async () => {
    if (!selectedPiano || !window.confirm(`Eliminare il piano "${selectedPiano.nome}"?`)) {
      return;
    }
    clearNotice();
    setSaving(true);
    try {
      await deletePianoFinanziario(selectedPiano.id, true);
      setMessage('Piano finanziario chiuso con successo');
      setSelectedPianoId('');
      setSelectedPiano(null);
      setVoci([]);
      await loadPiani();
    } catch (err) {
      setError(err?.response?.data?.detail || 'Errore nell\'eliminazione del piano');
    } finally {
      setSaving(false);
    }
  };

  const openCreateVoceModal = () => {
    if (!selectedPiano) {
      return;
    }
    clearNotice();
    setEditingVoce(null);
    setVoceForm(createEmptyVoceForm(selectedPiano.id));
    setShowVoceModal(true);
  };

  const openEditVoceModal = (voce) => {
    clearNotice();
    setEditingVoce(voce);
    setVoceForm({
      piano_id: voce.piano_id,
      categoria: voce.categoria || 'altro',
      descrizione: voce.descrizione || '',
      importo_preventivo: String(voce.importo_preventivo ?? ''),
      importo_consuntivo: String(voce.importo_consuntivo ?? ''),
      collaborator_id: voce.collaborator_id ? String(voce.collaborator_id) : '',
    });
    setShowVoceModal(true);
  };

  const handleSaveVoce = async (event) => {
    event.preventDefault();
    if (!selectedPiano) {
      return;
    }
    clearNotice();
    setSaving(true);
    try {
      const payload = {
        piano_id: Number(selectedPiano.id),
        categoria: voceForm.categoria || null,
        descrizione: voceForm.descrizione.trim() || null,
        importo_preventivo: parseNumber(voceForm.importo_preventivo),
        importo_consuntivo: parseNumber(voceForm.importo_consuntivo),
        collaborator_id: voceForm.collaborator_id ? Number(voceForm.collaborator_id) : null,
      };

      if (editingVoce) {
        await updateVocePianoFinanziario(selectedPiano.id, editingVoce.id, payload);
        setMessage('Voce aggiornata con successo');
      } else {
        await addVocePianoFinanziario(selectedPiano.id, payload);
        setMessage('Voce aggiunta con successo');
      }

      setShowVoceModal(false);
      await refreshAll(String(selectedPiano.id));
    } catch (err) {
      setError(err?.response?.data?.detail || 'Errore nel salvataggio della voce');
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteVoce = async (voce) => {
    if (!selectedPiano || !window.confirm('Eliminare questa voce dal piano?')) {
      return;
    }
    clearNotice();
    setSaving(true);
    try {
      await deleteVocePianoFinanziario(selectedPiano.id, voce.id);
      setMessage('Voce eliminata con successo');
      await refreshAll(String(selectedPiano.id));
    } catch (err) {
      setError(err?.response?.data?.detail || 'Errore nell\'eliminazione della voce');
    } finally {
      setSaving(false);
    }
  };

  const budgetTotal = Number(selectedPiano?.budget_totale || 0);
  const budgetUsed = Number(selectedPiano?.budget_utilizzato || 0);
  const budgetOver = budgetTotal > 0 && budgetUsed > budgetTotal;

  return (
    <div className="piani-finanziari-page">
      <section className="page-header">
        <div>
          <span className="page-eyebrow">Gestione Budget</span>
          <h2>Piani Finanziari</h2>
          <p>Gestisci piani, budget e voci economiche da un’unica area operativa.</p>
        </div>
        <div className="header-actions">
          <button type="button" className="btn-secondary" onClick={() => refreshAll()}>
            Aggiorna
          </button>
          <button type="button" className="btn-primary" onClick={openCreatePianoModal}>
            Nuovo piano
          </button>
        </div>
      </section>

      {message ? <div className="banner success">{message}</div> : null}
      {error ? <div className="banner error">{error}</div> : null}

      <section className="toolbar-card">
        <div className="toolbar-grid">
          <label>
            <span>Progetto</span>
            <select value={filters.progetto_id} onChange={(e) => handleFilterChange('progetto_id', e.target.value)}>
              <option value="">Tutti i progetti</option>
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </select>
          </label>

          <label>
            <span>Stato</span>
            <select value={filters.stato} onChange={(e) => handleFilterChange('stato', e.target.value)}>
              {STATI_PIANO.map((item) => (
                <option key={item.value || 'all'} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
        </div>
      </section>

      <section className="table-shell">
        <table className="piano-table">
          <thead>
            <tr>
              <th>Piano</th>
              <th>Progetto</th>
              <th>Stato</th>
              <th>Fondo</th>
              <th>Budget</th>
              <th>Utilizzo</th>
              <th>Azioni</th>
            </tr>
          </thead>
          <tbody>
            {!loading && piani.length === 0 ? (
              <tr>
                <td colSpan="7">Nessun piano finanziario trovato.</td>
              </tr>
            ) : null}
            {piani.map((piano) => {
              const isSelected = String(selectedPianoId) === String(piano.id);
              const project = projectMap[String(piano.progetto_id)];
              return (
                <tr
                  key={piano.id}
                  onClick={() => setSelectedPianoId(String(piano.id))}
                  style={{ cursor: 'pointer', background: isSelected ? '#eff6ff' : undefined }}
                >
                  <td>
                    <strong>{piano.nome || `Piano #${piano.id}`}</strong>
                  </td>
                  <td>{project?.name || `Progetto #${piano.progetto_id}`}</td>
                  <td>{piano.stato}</td>
                  <td>{piano.tipo_fondo}</td>
                  <td>{fmtCurrency(piano.budget_totale)}</td>
                  <td style={{ minWidth: 220 }}>
                    <BudgetProgress totale={piano.budget_totale} utilizzato={piano.budget_utilizzato} />
                  </td>
                  <td>
                    <button
                      type="button"
                      className="btn-inline"
                      onClick={(event) => {
                        event.stopPropagation();
                        setSelectedPianoId(String(piano.id));
                      }}
                    >
                      Dettaglio
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>

      {selectedPiano ? (
        <>
          <section className={`summary-card ${budgetOver ? 'danger' : 'highlight'}`}>
            <div className="summary-card-top">
              <div>
                <span>{projectMap[String(selectedPiano.progetto_id)]?.name || `Progetto #${selectedPiano.progetto_id}`}</span>
                <strong>{selectedPiano.nome || `Piano #${selectedPiano.id}`}</strong>
              </div>
              <div className={`badge ${budgetOver ? 'danger' : selectedPiano.stato === 'chiuso' ? 'warning' : 'ok'}`}>
                {selectedPiano.stato}
              </div>
            </div>
            <div style={{ marginTop: '1rem' }}>
              <BudgetProgress totale={budgetTotal} utilizzato={budgetUsed} />
            </div>
            <div className="summary-meta">
              <span>Fondo: {selectedPiano.tipo_fondo}</span>
              <span style={{ color: budgetOver ? '#b91c1c' : '#475569', fontWeight: 700 }}>
                {budgetOver ? 'Budget sforato' : 'Budget sotto controllo'}
              </span>
            </div>
            <div className="header-actions" style={{ marginTop: '1rem' }}>
              <button type="button" className="btn-secondary" onClick={openEditPianoModal}>
                Modifica piano
              </button>
              <button type="button" className="btn-primary" onClick={openCreateVoceModal}>
                Nuova voce
              </button>
              <button type="button" className="btn-remove" onClick={handleDeletePiano} title="Chiudi piano">
                ×
              </button>
            </div>
          </section>

          <section className="table-shell">
            <table className="piano-table">
              <thead>
                <tr>
                  <th>Categoria</th>
                  <th>Descrizione</th>
                  <th>Preventivo</th>
                  <th>Consuntivo</th>
                  <th>Collaboratore</th>
                  <th>Azioni</th>
                </tr>
              </thead>
              <tbody>
                {voci.length === 0 ? (
                  <tr>
                    <td colSpan="6">Nessuna voce presente per questo piano.</td>
                  </tr>
                ) : null}
                {voci.map((voce) => (
                  <tr key={voce.id}>
                    <td>{voce.categoria || 'altro'}</td>
                    <td>{voce.descrizione || 'Voce senza descrizione'}</td>
                    <td>{fmtCurrency(voce.importo_preventivo)}</td>
                    <td style={{ color: Number(voce.importo_consuntivo || 0) > Number(voce.importo_preventivo || 0) ? '#b91c1c' : undefined }}>
                      {fmtCurrency(voce.importo_consuntivo)}
                    </td>
                    <td>{voce.collaborator_id || '—'}</td>
                    <td>
                      <div className="header-actions">
                        <button type="button" className="btn-inline" onClick={() => openEditVoceModal(voce)}>
                          Modifica
                        </button>
                        <button type="button" className="btn-remove" onClick={() => handleDeleteVoce(voce)}>
                          ×
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </>
      ) : null}

      {showPianoModal ? (
        <div style={modalOverlayStyle} onClick={() => setShowPianoModal(false)}>
          <div style={modalCardStyle} onClick={(event) => event.stopPropagation()}>
            <div className="page-header" style={{ padding: 0, boxShadow: 'none', border: 'none' }}>
              <div>
                <span className="page-eyebrow">Piano Finanziario</span>
                <h2 style={{ fontSize: '1.5rem' }}>{editingPiano ? 'Modifica Piano' : 'Nuovo Piano'}</h2>
              </div>
              <button type="button" className="btn-remove" onClick={() => setShowPianoModal(false)}>×</button>
            </div>
            <form onSubmit={handleSavePiano}>
              <div className="toolbar-grid" style={{ marginTop: '1rem' }}>
                <label>
                  <span>Progetto</span>
                  <select
                    value={pianoForm.progetto_id}
                    onChange={(e) => setPianoForm((prev) => ({ ...prev, progetto_id: e.target.value }))}
                    disabled={Boolean(editingPiano)}
                    required
                  >
                    <option value="">Seleziona progetto</option>
                    {projects.map((project) => (
                      <option key={project.id} value={project.id}>
                        {project.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>Nome</span>
                  <input
                    value={pianoForm.nome}
                    onChange={(e) => setPianoForm((prev) => ({ ...prev, nome: e.target.value }))}
                    required
                  />
                </label>
                <label>
                  <span>Tipo fondo</span>
                  <select
                    value={pianoForm.tipo_fondo}
                    onChange={(e) => setPianoForm((prev) => ({ ...prev, tipo_fondo: e.target.value }))}
                  >
                    {TIPI_FONDO.map((item) => (
                      <option key={item.value} value={item.value}>{item.label}</option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>Stato</span>
                  <select
                    value={pianoForm.stato}
                    onChange={(e) => setPianoForm((prev) => ({ ...prev, stato: e.target.value }))}
                  >
                    {STATI_PIANO.filter((item) => item.value).map((item) => (
                      <option key={item.value} value={item.value}>{item.label}</option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>Budget totale</span>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={pianoForm.budget_totale}
                    onChange={(e) => setPianoForm((prev) => ({ ...prev, budget_totale: e.target.value }))}
                    required
                  />
                </label>
                <label>
                  <span>Data inizio</span>
                  <input
                    type="datetime-local"
                    value={pianoForm.data_inizio}
                    onChange={(e) => setPianoForm((prev) => ({ ...prev, data_inizio: e.target.value }))}
                    required
                  />
                </label>
                <label>
                  <span>Data fine</span>
                  <input
                    type="datetime-local"
                    value={pianoForm.data_fine}
                    onChange={(e) => setPianoForm((prev) => ({ ...prev, data_fine: e.target.value }))}
                    required
                  />
                </label>
              </div>
              <label style={{ display: 'flex', flexDirection: 'column', gap: '0.45rem', marginTop: '1rem' }}>
                <span style={{ fontSize: '0.82rem', fontWeight: 700, color: '#334155', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Note
                </span>
                <textarea
                  value={pianoForm.note}
                  onChange={(e) => setPianoForm((prev) => ({ ...prev, note: e.target.value }))}
                  rows={4}
                  style={{ width: '100%', border: '1px solid #cbd5e1', borderRadius: '12px', padding: '0.82rem', font: 'inherit' }}
                />
              </label>
              <div className="header-actions" style={{ marginTop: '1.2rem', justifyContent: 'flex-end' }}>
                <button type="button" className="btn-secondary" onClick={() => setShowPianoModal(false)}>
                  Annulla
                </button>
                <button type="submit" className="btn-primary" disabled={saving}>
                  {saving ? 'Salvataggio...' : 'Salva piano'}
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}

      {showVoceModal ? (
        <div style={modalOverlayStyle} onClick={() => setShowVoceModal(false)}>
          <div style={{ ...modalCardStyle, width: 'min(620px, 100%)' }} onClick={(event) => event.stopPropagation()}>
            <div className="page-header" style={{ padding: 0, boxShadow: 'none', border: 'none' }}>
              <div>
                <span className="page-eyebrow">Voce Piano</span>
                <h2 style={{ fontSize: '1.5rem' }}>{editingVoce ? 'Modifica Voce' : 'Nuova Voce'}</h2>
              </div>
              <button type="button" className="btn-remove" onClick={() => setShowVoceModal(false)}>×</button>
            </div>
            <form onSubmit={handleSaveVoce}>
              <div className="toolbar-grid" style={{ marginTop: '1rem', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))' }}>
                <label>
                  <span>Categoria</span>
                  <select
                    value={voceForm.categoria}
                    onChange={(e) => setVoceForm((prev) => ({ ...prev, categoria: e.target.value }))}
                  >
                    {CATEGORIE_VOCE.map((item) => (
                      <option key={item.value} value={item.value}>{item.label}</option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>Collaboratore ID</span>
                  <input
                    type="number"
                    min="1"
                    value={voceForm.collaborator_id}
                    onChange={(e) => setVoceForm((prev) => ({ ...prev, collaborator_id: e.target.value }))}
                  />
                </label>
                <label>
                  <span>Importo preventivo</span>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={voceForm.importo_preventivo}
                    onChange={(e) => setVoceForm((prev) => ({ ...prev, importo_preventivo: e.target.value }))}
                  />
                </label>
                <label>
                  <span>Importo consuntivo</span>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={voceForm.importo_consuntivo}
                    onChange={(e) => setVoceForm((prev) => ({ ...prev, importo_consuntivo: e.target.value }))}
                  />
                </label>
              </div>
              <label style={{ display: 'flex', flexDirection: 'column', gap: '0.45rem', marginTop: '1rem' }}>
                <span style={{ fontSize: '0.82rem', fontWeight: 700, color: '#334155', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Descrizione
                </span>
                <textarea
                  rows={4}
                  value={voceForm.descrizione}
                  onChange={(e) => setVoceForm((prev) => ({ ...prev, descrizione: e.target.value }))}
                  style={{ width: '100%', border: '1px solid #cbd5e1', borderRadius: '12px', padding: '0.82rem', font: 'inherit' }}
                />
              </label>
              <div className="header-actions" style={{ marginTop: '1.2rem', justifyContent: 'flex-end' }}>
                <button type="button" className="btn-secondary" onClick={() => setShowVoceModal(false)}>
                  Annulla
                </button>
                <button type="submit" className="btn-primary" disabled={saving}>
                  {saving ? 'Salvataggio...' : 'Salva voce'}
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </div>
  );
}
