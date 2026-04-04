import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  createPianoFondimpresa,
  exportPianoFondimpresaExcel,
  getPianiFondimpresa,
  getPianoFondimpresa,
  getProjects,
  getRiepilogoPianoFondimpresa,
  updateDettaglioBudgetFondimpresa,
  updateDocumentiPianoFondimpresa,
  updateVociPianoFondimpresa,
} from '../services/apiService';
import './PianiFinanziariManager.css';

const SECTION_TITLES = {
  A: 'Sezione A - Erogazione della formazione',
  B: 'Sezione B - Cofinanziamento aziendale',
  C: 'Sezione C - Attività preparatorie e non formative',
  D: 'Sezione D - Gestione del Programma',
};

const VOICE_TEMPLATES = [
  ['A', 'A1', 'Docenza', true],
  ['A', 'A2', 'Tutoraggio', true],
  ['A', 'A3', 'Coordinamento didattico', true],
  ['A', 'A3b', 'Comitato scientifico', true],
  ['A', 'A4', 'Aule ed attrezzature didattiche', false],
  ['A', 'A5', 'Materiali didattici', false],
  ['A', 'A6', 'Materiali di consumo', false],
  ['A', 'A7', 'Università/Partenariato – certificazione competenze', false],
  ['A', 'A7b', 'Certificazione competenze', true],
  ['A', 'A8', 'Viaggi e trasferte', false],
  ['B', 'B1', 'Cofinanziamento aziendale', false],
  ['C', 'C.1.1', 'Analisi della domanda', false],
  ['C', 'C.1.2', 'Diagnosi e rilevazione dei fabbisogni formativi', false],
  ['C', 'C.1.5', 'Definizione di metodologie e modelli di formazione continua', false],
  ['C', 'C.1.6', 'Altre attività preparatorie e di accompagnamento', false],
  ['C', 'C.1.7', 'Viaggi e trasferte', false],
  ['C', 'C.2.1', 'Progettazione attività del piano', true],
  ['C', 'C.2.3', 'Individuazione e orientamento dei partecipanti', false],
  ['C', 'C.2.4', 'Sistema di monitoraggio e valutazione', true],
  ['C', 'C.2.7', 'Viaggi e trasferte', false],
  ['D', 'D1', 'Costi diretti di gestione', true],
  ['D', 'D2', 'Costi indiretti di gestione', false],
].map(([sezione, voce_codice, descrizione, supportsNominativi]) => ({ sezione, voce_codice, descrizione, supportsNominativi }));

const fmtCurrency = (value) => new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR' }).format(Number(value || 0));
const createKey = () => `tmp-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;

const buildVoiceRows = (piano) => {
  const byCode = Object.fromEntries((piano?.voci || []).map((voce) => [voce.voce_codice, voce]));
  return VOICE_TEMPLATES.map((template) => {
    const voce = byCode[template.voce_codice];
    return {
      id: voce?.id || null,
      sezione: template.sezione,
      voce_codice: template.voce_codice,
      descrizione: voce?.descrizione || template.descrizione,
      note_temporali: voce?.note_temporali || '',
      totale_voce: voce?.totale_voce || 0,
      righe_nominativo: (voce?.righe_nominativo || []).map((row) => ({ ...row, localKey: `nom-${row.id}` })),
      documenti: (voce?.documenti || []).map((row) => ({ ...row, localKey: `doc-${row.id}` })),
      supportsNominativi: template.supportsNominativi,
    };
  });
};

const buildBudgetState = (budget) => ({
  consulenti: (budget?.consulenti || []).map((row) => ({ ...row, localKey: `cons-${row.id}` })),
  costi_fissi: (budget?.costi_fissi || []).map((row) => ({ ...row, localKey: `fix-${row.id}` })),
  margini: (budget?.margini || []).map((row) => ({ ...row, localKey: `mar-${row.id}` })),
});

export default function PianiFondimpresaManager({ forcedProjectId = '', embedded = false }) {
  const query = new URLSearchParams(window.location.search);
  const pathMatch = window.location.pathname.match(/^\/piani-fondimpresa\/(\d+)/);

  const [projects, setProjects] = useState([]);
  const [plans, setPlans] = useState([]);
  const [selectedProjectId, setSelectedProjectId] = useState(query.get('projectId') || '');
  const [selectedPianoId, setSelectedPianoId] = useState(pathMatch?.[1] || '');
  const [anno, setAnno] = useState(new Date().getFullYear());
  const [tipoConto, setTipoConto] = useState('conto_formazione');
  const [totalePreventivo, setTotalePreventivo] = useState('0');
  const [activeTab, setActiveTab] = useState('piano');
  const [rows, setRows] = useState([]);
  const [budget, setBudget] = useState(buildBudgetState());
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const selectedProject = useMemo(
    () => projects.find((project) => String(project.id) === String(selectedProjectId)),
    [projects, selectedProjectId],
  );

  const loadProjects = useCallback(async () => {
    const data = await getProjects(0, 300);
    setProjects(Array.isArray(data) ? data : []);
  }, []);

  const loadPlans = useCallback(async (projectId) => {
    const data = await getPianiFondimpresa(projectId ? { progetto_id: projectId, limit: 50 } : { limit: 100 });
    setPlans(Array.isArray(data) ? data : []);
  }, []);

  const loadDetail = useCallback(async (pianoId) => {
    if (!pianoId) {
      setRows([]);
      setBudget(buildBudgetState());
      setSummary(null);
      return;
    }
    setLoading(true);
    setError('');
    try {
      const [detail, riepilogo] = await Promise.all([
        getPianoFondimpresa(pianoId),
        getRiepilogoPianoFondimpresa(pianoId),
      ]);
      setSelectedProjectId(String(detail.progetto_id));
      setAnno(detail.anno);
      setTipoConto(detail.tipo_conto);
      setTotalePreventivo(String(detail.totale_preventivo || 0));
      setRows(buildVoiceRows(detail));
      setBudget(buildBudgetState(detail.dettaglio_budget));
      setSummary(riepilogo);
    } catch (loadError) {
      setError(loadError?.response?.data?.detail || 'Errore nel caricamento del piano Fondimpresa.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!forcedProjectId) {
      return;
    }
    setSelectedProjectId(String(forcedProjectId));
  }, [forcedProjectId]);

  useEffect(() => {
    loadProjects();
    loadPlans(selectedProjectId);
  }, [loadProjects, loadPlans, selectedProjectId]);

  useEffect(() => {
    loadDetail(selectedPianoId);
  }, [loadDetail, selectedPianoId]);

  useEffect(() => {
    if (!forcedProjectId) {
      return;
    }

    if (!Array.isArray(plans) || plans.length === 0) {
      setSelectedPianoId('');
      return;
    }

    const nextPlanId = plans[0]?.id || '';
    if (String(selectedPianoId) !== String(nextPlanId)) {
      setSelectedPianoId(String(nextPlanId));
    }
  }, [forcedProjectId, plans, selectedPianoId]);

  const groupedRows = useMemo(() => (
    ['A', 'B', 'C', 'D'].map((section) => ({
      section,
      title: SECTION_TITLES[section],
      rows: rows.filter((row) => row.sezione === section),
      summary: summary?.sezioni?.find((item) => item.sezione === section),
    }))
  ), [rows, summary]);

  const budgetTotal = useMemo(() => {
    const consulenti = budget.consulenti.reduce((sum, item) => sum + (Number(item.ore || 0) * Number(item.costo_orario || 0)), 0);
    const costiFissi = budget.costi_fissi.reduce((sum, item) => sum + Number(item.totale || 0), 0);
    const margini = budget.margini.reduce((sum, item) => sum + ((summary?.totale_escluso_cofinanziamento || 0) * Number(item.percentuale || 0) / 100), 0);
    return consulenti + costiFissi + margini;
  }, [budget, summary]);

  const setVoiceField = (voceCodice, field, value) => {
    setRows((current) => current.map((row) => row.voce_codice === voceCodice ? { ...row, [field]: value } : row));
  };

  const addNominativo = (voceCodice) => {
    setRows((current) => current.map((row) => row.voce_codice === voceCodice ? {
      ...row,
      righe_nominativo: [...row.righe_nominativo, { id: null, localKey: createKey(), nominativo: '', ore: 0, costo_orario: 0 }],
    } : row));
  };

  const updateNominativo = (voceCodice, localKey, field, value) => {
    setRows((current) => current.map((row) => row.voce_codice === voceCodice ? {
      ...row,
      righe_nominativo: row.righe_nominativo.map((entry) => entry.localKey === localKey ? { ...entry, [field]: value } : entry),
    } : row));
  };

  const addDocumento = (voceCodice) => {
    setRows((current) => current.map((row) => row.voce_codice === voceCodice ? {
      ...row,
      documenti: [...row.documenti, { id: null, localKey: createKey(), tipo_documento: '', numero_documento: '', data_documento: '', importo_totale: 0, importo_imputato: 0, data_pagamento: '' }],
    } : row));
  };

  const updateDocumento = (voceCodice, localKey, field, value) => {
    setRows((current) => current.map((row) => row.voce_codice === voceCodice ? {
      ...row,
      documenti: row.documenti.map((entry) => entry.localKey === localKey ? { ...entry, [field]: value } : entry),
    } : row));
  };

  const addBudgetRow = (bucket) => {
    const defaults = {
      consulenti: { id: null, localKey: createKey(), nominativo: '', ore: 0, costo_orario: 0 },
      costi_fissi: { id: null, localKey: createKey(), tipologia: '', parametro: '', totale: 0 },
      margini: { id: null, localKey: createKey(), tipologia: '', percentuale: 0 },
    };
    setBudget((current) => ({ ...current, [bucket]: [...current[bucket], defaults[bucket]] }));
  };

  const updateBudgetRow = (bucket, localKey, field, value) => {
    setBudget((current) => ({
      ...current,
      [bucket]: current[bucket].map((entry) => entry.localKey === localKey ? { ...entry, [field]: value } : entry),
    }));
  };

  const handleCreate = async () => {
    if (!selectedProjectId) {
      setError('Seleziona prima un progetto.');
      return;
    }
    setSaving(true);
    setError('');
    try {
      const detail = await createPianoFondimpresa({
        progetto_id: Number(selectedProjectId),
        anno: Number(anno),
        tipo_conto: tipoConto,
        totale_preventivo: Number(totalePreventivo || 0),
      });
      window.history.pushState({}, '', `/piani-fondimpresa/${detail.id}`);
      setSelectedPianoId(String(detail.id));
      setMessage('Piano Fondimpresa creato.');
    } catch (createError) {
      setError(createError?.response?.data?.detail || 'Errore nella creazione del piano.');
    } finally {
      setSaving(false);
    }
  };

  const handleSave = async () => {
    if (!selectedPianoId) {
      setError('Crea prima il piano.');
      return;
    }
    setSaving(true);
    setError('');
    try {
      if (activeTab === 'piano') {
        await updateVociPianoFondimpresa(selectedPianoId, {
          voci: rows.map((row) => ({
            id: row.id,
            sezione: row.sezione,
            voce_codice: row.voce_codice,
            descrizione: row.descrizione,
            note_temporali: row.note_temporali,
            righe_nominativo: row.righe_nominativo.map((entry) => ({
              id: entry.id,
              nominativo: entry.nominativo,
              ore: Number(entry.ore || 0),
              costo_orario: Number(entry.costo_orario || 0),
            })),
            documenti: [],
          })),
        });
      } else if (activeTab === 'documenti') {
        await updateDocumentiPianoFondimpresa(selectedPianoId, {
          voci: rows.map((row) => ({
            id: row.id,
            sezione: row.sezione,
            voce_codice: row.voce_codice,
            descrizione: row.descrizione,
            note_temporali: row.note_temporali,
            righe_nominativo: [],
            documenti: row.documenti.map((entry) => ({
              id: entry.id,
              tipo_documento: entry.tipo_documento,
              numero_documento: entry.numero_documento,
              data_documento: entry.data_documento || null,
              importo_totale: Number(entry.importo_totale || 0),
              importo_imputato: Number(entry.importo_imputato || 0),
              data_pagamento: entry.data_pagamento || null,
            })),
          })),
        });
      } else {
        await updateDettaglioBudgetFondimpresa(selectedPianoId, {
          consulenti: budget.consulenti.map((entry) => ({ id: entry.id, nominativo: entry.nominativo, ore: Number(entry.ore || 0), costo_orario: Number(entry.costo_orario || 0) })),
          costi_fissi: budget.costi_fissi.map((entry) => ({ id: entry.id, tipologia: entry.tipologia, parametro: entry.parametro, totale: Number(entry.totale || 0) })),
          margini: budget.margini.map((entry) => ({ id: entry.id, tipologia: entry.tipologia, percentuale: Number(entry.percentuale || 0) })),
        });
      }
      await loadDetail(selectedPianoId);
      setMessage('Salvataggio completato.');
    } catch (saveError) {
      setError(saveError?.response?.data?.detail || 'Errore nel salvataggio.');
    } finally {
      setSaving(false);
    }
  };

  const handleExport = async () => {
    if (!selectedPianoId) return;
    const response = await exportPianoFondimpresaExcel(selectedPianoId);
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `piano_fondimpresa_${selectedPianoId}.xlsx`);
    document.body.appendChild(link);
    link.click();
    link.remove();
  };

  return (
    <div className={embedded ? 'piani-finanziari-embedded' : 'piani-finanziari-manager'}>
      <div className="manager-header">
        <div className="header-title">
          <h2>{embedded ? 'Piano Finanziario' : 'Piano Finanziario Fondimpresa'}</h2>
          <p>{embedded ? "Layout Fondimpresa attivato dall'ente erogatore del progetto selezionato." : 'Gestisci il piano ufficiale, la rendicontazione documentale e il dettaglio budget interno.'}</p>
        </div>
        <div className="manager-actions">
          <button className="btn-secondary" onClick={handleExport} disabled={!selectedPianoId}>Esporta Excel</button>
          <button className="btn-primary" onClick={handleSave} disabled={saving || !selectedPianoId}>{saving ? 'Salvataggio...' : 'Salva'}</button>
        </div>
      </div>

      {error ? <div className="alert-banner danger">{error}</div> : null}
      {message ? <div className="alert-banner success">{message}</div> : null}

      <div className="plans-toolbar">
        {!forcedProjectId && (
          <select value={selectedProjectId} onChange={(event) => setSelectedProjectId(event.target.value)}>
            <option value="">Seleziona progetto</option>
            {projects.map((project) => (
              <option key={project.id} value={project.id}>{project.name}</option>
            ))}
          </select>
        )}
        <select value={selectedPianoId} onChange={(event) => {
          const nextId = event.target.value;
          setSelectedPianoId(nextId);
          if (nextId) window.history.pushState({}, '', `/piani-fondimpresa/${nextId}`);
        }}>
          <option value="">Seleziona piano</option>
          {plans.map((plan) => (
            <option key={plan.id} value={plan.id}>{plan.anno} · {plan.tipo_conto}</option>
          ))}
        </select>
        <input type="number" value={anno} onChange={(event) => setAnno(event.target.value)} />
        <select value={tipoConto} onChange={(event) => setTipoConto(event.target.value)}>
          <option value="conto_formazione">Conto Formazione</option>
          <option value="conto_sistema">Conto Sistema</option>
        </select>
        <input type="number" step="0.01" value={totalePreventivo} onChange={(event) => setTotalePreventivo(event.target.value)} placeholder="Totale preventivo" />
        <button className="btn-secondary" onClick={handleCreate} disabled={saving}>Crea piano</button>
      </div>

      {selectedProject ? (
        <div className="financial-summary-grid">
          <div className="summary-card emphasis">
            <span>Progetto</span>
            <strong>{selectedProject.name}</strong>
            <small>{selectedProject.ente_erogatore || 'Ente erogatore non impostato'}</small>
          </div>
          <div className="summary-card">
            <span>Totale escluso cofinanziamento</span>
            <strong>{fmtCurrency(summary?.totale_escluso_cofinanziamento)}</strong>
            <small>Consuntivo ufficiale</small>
          </div>
          <div className="summary-card">
            <span>Differenza preventivo / consuntivo</span>
            <strong>{fmtCurrency(summary?.differenza_preventivo_consuntivo)}</strong>
            <small>{Number(summary?.differenza_preventivo_consuntivo || 0) < 0 ? 'Budget sforato' : 'Budget capiente'}</small>
          </div>
        </div>
      ) : null}

      <div className="manager-filters">
        {['piano', 'documenti', 'budget'].map((tab) => (
          <button key={tab} className={`filter-chip ${activeTab === tab ? 'active' : ''}`} onClick={() => setActiveTab(tab)}>
            {tab === 'piano' ? 'Piano Finanziario' : tab === 'documenti' ? 'Rendicontazione Documenti' : 'Dettaglio Budget'}
          </button>
        ))}
      </div>

      {loading ? <div className="empty-state">Caricamento piano...</div> : null}

      {!loading && activeTab === 'piano' ? (
        <div className="financial-table-shell">
          {groupedRows.map((group) => (
            <section key={group.section} className="macrovoce-block">
              <div className="macrovoce-header">
                <div>
                  <h3>{group.title}</h3>
                  <p>{group.summary ? `${fmtCurrency(group.summary.totale)} · ${Number(group.summary.percentuale || 0).toFixed(2)}%` : 'Nessun riepilogo disponibile'}</p>
                </div>
                {group.summary ? <span className={`alert-pill ${group.summary.alert_level}`}>{group.summary.alert_level}</span> : null}
              </div>

              {group.rows.map((row) => (
                <div key={row.voce_codice} className="financial-row-editor">
                  <div className="financial-row-head">
                    <div>
                      <strong>{row.voce_codice}</strong>
                      <span>{row.descrizione}</span>
                    </div>
                    <div>{fmtCurrency(row.totale_voce)}</div>
                  </div>
                  <input value={row.note_temporali} onChange={(event) => setVoiceField(row.voce_codice, 'note_temporali', event.target.value)} placeholder="Note temporali / ammissibilità" />
                  {row.supportsNominativi ? (
                    <div className="financial-inline-table">
                      <div className="table-toolbar">
                        <span>Righe nominativo</span>
                        <button className="btn-secondary" onClick={() => addNominativo(row.voce_codice)}>+ Aggiungi nominativo</button>
                      </div>
                      <table>
                        <thead>
                          <tr>
                            <th>Nominativo</th>
                            <th>Ore</th>
                            <th>Costo orario</th>
                            <th>Totale</th>
                          </tr>
                        </thead>
                        <tbody>
                          {row.righe_nominativo.map((entry) => (
                            <tr key={entry.localKey}>
                              <td><input value={entry.nominativo} onChange={(event) => updateNominativo(row.voce_codice, entry.localKey, 'nominativo', event.target.value)} /></td>
                              <td><input type="number" step="0.01" value={entry.ore} onChange={(event) => updateNominativo(row.voce_codice, entry.localKey, 'ore', event.target.value)} /></td>
                              <td><input type="number" step="0.01" value={entry.costo_orario} onChange={(event) => updateNominativo(row.voce_codice, entry.localKey, 'costo_orario', event.target.value)} /></td>
                              <td>{fmtCurrency(Number(entry.ore || 0) * Number(entry.costo_orario || 0))}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : null}
                </div>
              ))}
            </section>
          ))}
        </div>
      ) : null}

      {!loading && activeTab === 'documenti' ? (
        <div className="financial-table-shell">
          {rows.map((row) => (
            <section key={row.voce_codice} className="macrovoce-block">
              <div className="macrovoce-header">
                <div>
                  <h3>{row.voce_codice} · {row.descrizione}</h3>
                  <p>Totale imputato: {fmtCurrency(row.documenti.reduce((sum, item) => sum + Number(item.importo_imputato || 0), 0))}</p>
                </div>
                <button className="btn-secondary" onClick={() => addDocumento(row.voce_codice)}>+ Aggiungi documento</button>
              </div>
              <table>
                <thead>
                  <tr>
                    <th>Tipo Doc</th>
                    <th>Numero</th>
                    <th>Data</th>
                    <th>Importo Totale</th>
                    <th>Importo Imputato</th>
                    <th>Data Pagamento</th>
                  </tr>
                </thead>
                <tbody>
                  {row.documenti.map((entry) => (
                    <tr key={entry.localKey}>
                      <td><input value={entry.tipo_documento || ''} onChange={(event) => updateDocumento(row.voce_codice, entry.localKey, 'tipo_documento', event.target.value)} /></td>
                      <td><input value={entry.numero_documento || ''} onChange={(event) => updateDocumento(row.voce_codice, entry.localKey, 'numero_documento', event.target.value)} /></td>
                      <td><input type="date" value={String(entry.data_documento || '').slice(0, 10)} onChange={(event) => updateDocumento(row.voce_codice, entry.localKey, 'data_documento', event.target.value)} /></td>
                      <td><input type="number" step="0.01" value={entry.importo_totale} onChange={(event) => updateDocumento(row.voce_codice, entry.localKey, 'importo_totale', event.target.value)} /></td>
                      <td><input type="number" step="0.01" value={entry.importo_imputato} onChange={(event) => updateDocumento(row.voce_codice, entry.localKey, 'importo_imputato', event.target.value)} /></td>
                      <td><input type="date" value={String(entry.data_pagamento || '').slice(0, 10)} onChange={(event) => updateDocumento(row.voce_codice, entry.localKey, 'data_pagamento', event.target.value)} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          ))}
        </div>
      ) : null}

      {!loading && activeTab === 'budget' ? (
        <div className="financial-summary-grid">
          <div className="summary-card emphasis">
            <span>Uso interno</span>
            <strong>Dettaglio Budget</strong>
            <small>Consulenti, costi fissi e margine</small>
          </div>
          <div className="summary-card">
            <span>Totale Budget Interno</span>
            <strong>{fmtCurrency(budgetTotal)}</strong>
            <small>Analisi economica interna</small>
          </div>

          {[
            ['consulenti', 'Consulenti', ['nominativo', 'ore', 'costo_orario']],
            ['costi_fissi', 'Costi Fissi', ['tipologia', 'parametro', 'totale']],
            ['margini', 'Margine', ['tipologia', 'percentuale']],
          ].map(([bucket, title, columns]) => (
            <div key={bucket} className="summary-card">
              <div className="table-toolbar">
                <span>{title}</span>
                <button className="btn-secondary" onClick={() => addBudgetRow(bucket)}>+ Aggiungi</button>
              </div>
              {(budget[bucket] || []).map((entry) => (
                <div key={entry.localKey} className="budget-inline-row">
                  {columns.map((column) => (
                    <input
                      key={column}
                      type={column === 'ore' || column === 'costo_orario' || column === 'totale' || column === 'percentuale' ? 'number' : 'text'}
                      step="0.01"
                      placeholder={column}
                      value={entry[column] ?? ''}
                      onChange={(event) => updateBudgetRow(bucket, entry.localKey, column, event.target.value)}
                    />
                  ))}
                  {bucket === 'consulenti' ? <small>{fmtCurrency(Number(entry.ore || 0) * Number(entry.costo_orario || 0))}</small> : null}
                  {bucket === 'margini' ? <small>{fmtCurrency((summary?.totale_escluso_cofinanziamento || 0) * Number(entry.percentuale || 0) / 100)}</small> : null}
                </div>
              ))}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
