import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  createAvviso,
  getAvvisi,
  getAvvisoRevisioni,
  ingestAvvisoRevision,
} from '../services/apiService';
import './ResourceArchive.css';

const FONDI = [
  { value: 'fondimpresa', label: 'Fondimpresa' },
  { value: 'formazienda', label: 'Formazienda' },
  { value: 'fapi', label: 'FAPI' },
  { value: 'regionale', label: 'Regionale' },
  { value: 'altro', label: 'Altro' },
];

const EXTRACTION_STATUS = {
  caricato: { label: 'Caricato', tone: 'neutral' },
  pulito: { label: 'Pulito', tone: 'info' },
  segmentato: { label: 'Pronto', tone: 'info' },
  in_estrazione: { label: 'In analisi', tone: 'warning' },
  estratto: { label: 'Estratto', tone: 'success' },
  errore: { label: 'Errore', tone: 'danger' },
};

const emptyAvvisoForm = {
  codice: '',
  ente_erogatore: '',
  fondo: 'altro',
  titolo: '',
};

const formatDateTime = (value) => {
  if (!value) return '—';
  try {
    return new Intl.DateTimeFormat('it-IT', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(value));
  } catch {
    return value;
  }
};

const errorDetail = (error, fallback) => {
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map((item) => item.msg).filter(Boolean).join(' · ') || fallback;
  return error?.message || fallback;
};

function StatusBadge({ value }) {
  const meta = EXTRACTION_STATUS[value] || { label: value || 'N/D', tone: 'neutral' };
  return <span className={`resources-status ${meta.tone}`}>{meta.label}</span>;
}

export default function ResourceArchive({ currentUser = null, onReviewSuggestions = null }) {
  const [avvisi, setAvvisi] = useState([]);
  const [selectedId, setSelectedId] = useState('');
  const [revisions, setRevisions] = useState([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [revisionsLoading, setRevisionsLoading] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [createForm, setCreateForm] = useState(emptyAvvisoForm);
  const [creating, setCreating] = useState(false);
  const [uploadFile, setUploadFile] = useState(null);
  const [uploadTitle, setUploadTitle] = useState('');
  const [revisionLabel, setRevisionLabel] = useState('');
  const [runExtraction, setRunExtraction] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [ingestResult, setIngestResult] = useState(null);
  const fileInputRef = useRef(null);

  const canWrite = ['admin', 'manager'].includes(currentUser?.role);

  const selectedAvviso = useMemo(
    () => avvisi.find((item) => String(item.id) === String(selectedId)) || null,
    [avvisi, selectedId],
  );

  const filteredAvvisi = useMemo(() => {
    const needle = search.trim().toLowerCase();
    if (!needle) return avvisi;
    return avvisi.filter((item) => (
      [item.codice, item.titolo, item.ente_erogatore, item.fondo]
        .some((value) => String(value || '').toLowerCase().includes(needle))
    ));
  }, [avvisi, search]);

  const loadRevisions = useCallback(async (avvisoId) => {
    if (!avvisoId) {
      setRevisions([]);
      return;
    }
    setRevisionsLoading(true);
    try {
      const data = await getAvvisoRevisioni(avvisoId);
      setRevisions(Array.isArray(data) ? data : []);
    } catch (loadError) {
      setError(errorDetail(loadError, 'Impossibile caricare lo storico revisioni.'));
      setRevisions([]);
    } finally {
      setRevisionsLoading(false);
    }
  }, []);

  const loadAvvisi = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await getAvvisi({ active_only: false, limit: 1000 });
      const items = Array.isArray(data) ? data : [];
      setAvvisi(items);
      setSelectedId((current) => current || (items[0]?.id ? String(items[0].id) : ''));
    } catch (loadError) {
      setError(errorDetail(loadError, 'Impossibile caricare l’archivio avvisi.'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadAvvisi(); }, [loadAvvisi]);

  useEffect(() => {
    if (!selectedId) return;
    loadRevisions(Number(selectedId));
    setIngestResult(null);
  }, [loadRevisions, selectedId]);

  useEffect(() => {
    if (selectedAvviso) setUploadTitle(selectedAvviso.titolo || `Avviso ${selectedAvviso.codice}`);
  }, [selectedAvviso]);

  const selectAvviso = (id) => {
    setSelectedId(String(id));
    setError('');
    setMessage('');
  };

  const handleCreate = async (event) => {
    event.preventDefault();
    if (!canWrite) return;
    setCreating(true);
    setError('');
    try {
      const created = await createAvviso({
        ...createForm,
        descrizione: createForm.titolo,
        stato: 'bozza',
        is_active: true,
      });
      setAvvisi((current) => [...current, created].sort((a, b) => String(a.codice).localeCompare(String(b.codice))));
      setSelectedId(String(created.id));
      setCreateForm(emptyAvvisoForm);
      setShowCreate(false);
      setMessage('Avviso creato. Ora puoi caricare la prima revisione markdown.');
    } catch (createError) {
      setError(errorDetail(createError, 'Creazione avviso non riuscita.'));
    } finally {
      setCreating(false);
    }
  };

  const handleIngest = async (event) => {
    event.preventDefault();
    if (!selectedAvviso || !uploadFile || !uploadTitle.trim() || !canWrite) return;
    if (!uploadFile.name.toLowerCase().endsWith('.md')) {
      setError('Seleziona un file markdown con estensione .md.');
      return;
    }
    setUploading(true);
    setError('');
    setMessage('');
    setIngestResult(null);
    try {
      const result = await ingestAvvisoRevision(selectedAvviso.id, {
        file: uploadFile,
        titolo: uploadTitle.trim(),
        etichettaRevisione: revisionLabel.trim(),
        eseguiEstrazione: runExtraction,
      });
      setIngestResult(result);
      setMessage('Revisione acquisita correttamente.');
      setUploadFile(null);
      setRevisionLabel('');
      if (fileInputRef.current) fileInputRef.current.value = '';
      await loadRevisions(selectedAvviso.id);
      await loadAvvisi();
    } catch (uploadError) {
      setError(errorDetail(uploadError, 'Ingestione del markdown non riuscita.'));
    } finally {
      setUploading(false);
    }
  };

  const openReview = () => {
    if (onReviewSuggestions) {
      onReviewSuggestions();
      return;
    }
    window.location.href = '/agents/review?agent_type=avviso_extractor&entity_type=avviso_revisione';
  };

  const suggestionsCount = ingestResult?.estrazione?.suggestions_count;

  return (
    <div className="resources-page">
      <section className="resources-hero">
        <div>
          <span className="resources-eyebrow">Base di conoscenza controllata</span>
          <h2>Archivio Risorse</h2>
          <p>
            Conserva le fonti che guidano la piattaforma. Gli avvisi sono versionati, analizzati
            dall’agente e trasformati in proposte verificabili.
          </p>
        </div>
        <div className="resources-hero-rule">
          <strong>Controllo umano obbligatorio</strong>
          <span>Le regole e scadenze diventano operative solo dopo validazione umana.</span>
        </div>
      </section>

      <section className="resources-types" aria-label="Tipi di risorsa">
        <article className="resources-type active">
          <span className="resources-type-icon">📜</span>
          <div><strong>Avvisi normativi</strong><span>Upload `.md`, versioni, regole e scadenze.</span></div>
          <span className="resources-type-state">Operativo</span>
        </article>
        <article className="resources-type planned">
          <span className="resources-type-icon">📎</span>
          <div><strong>Allegati e manuali</strong><span>Vademecum, circolari e documenti collegati.</span></div>
          <span className="resources-type-state">Prossima estensione</span>
        </article>
        <article className="resources-type planned">
          <span className="resources-type-icon">🧠</span>
          <div><strong>Conoscenza operativa</strong><span>Decisioni, buone prassi ed errori da evitare.</span></div>
          <span className="resources-type-state">Prossima estensione</span>
        </article>
      </section>

      {error ? <div className="resources-alert error" role="alert">{error}</div> : null}
      {message ? <div className="resources-alert success">{message}</div> : null}
      {!canWrite ? (
        <div className="resources-alert warning">L’upload è riservato ai ruoli amministratore e manager.</div>
      ) : null}

      <section className="resources-workflow">
        <div><span>1</span><strong>Seleziona l’avviso</strong><small>Oppure crea una nuova identità.</small></div>
        <div><span>2</span><strong>Carica il markdown</strong><small>Una nuova revisione immutabile.</small></div>
        <div><span>3</span><strong>Analisi AI</strong><small>Produce proposte, non dati validati.</small></div>
        <div><span>4</span><strong>Revisione umana</strong><small>Conferma regole e scadenze.</small></div>
      </section>

      <div className="resources-layout">
        <aside className="resources-sidebar">
          <div className="resources-panel-heading">
            <div><span>Archivio</span><strong>{avvisi.length} avvisi</strong></div>
            <button type="button" className="resources-button secondary" onClick={() => setShowCreate((value) => !value)} disabled={!canWrite}>
              {showCreate ? 'Annulla' : '+ Nuovo avviso'}
            </button>
          </div>

          {showCreate ? (
            <form className="resources-create-form" onSubmit={handleCreate}>
              <label>Codice avviso<input aria-label="Codice avviso" required pattern="[^/]+/20[0-9]{2}" title="Usa il formato numero/anno, per esempio 1/2026" placeholder="es. 1/2026" value={createForm.codice} onChange={(event) => setCreateForm((form) => ({ ...form, codice: event.target.value }))} /></label>
              <label>Ente erogatore<input aria-label="Ente erogatore" required placeholder="es. FAPI" value={createForm.ente_erogatore} onChange={(event) => setCreateForm((form) => ({ ...form, ente_erogatore: event.target.value }))} /></label>
              <label>Fondo<select value={createForm.fondo} onChange={(event) => setCreateForm((form) => ({ ...form, fondo: event.target.value }))}>{FONDI.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
              <label>Titolo avviso<input aria-label="Titolo avviso" required value={createForm.titolo} onChange={(event) => setCreateForm((form) => ({ ...form, titolo: event.target.value }))} /></label>
              <button type="submit" className="resources-button primary" disabled={creating}>{creating ? 'Creazione...' : 'Crea avviso'}</button>
            </form>
          ) : null}

          <label className="resources-search">
            <span>Cerca</span>
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Codice, ente o titolo" />
          </label>

          <div className="resources-list">
            {loading ? <div className="resources-empty">Caricamento archivio...</div> : null}
            {!loading && filteredAvvisi.map((item) => (
              <button key={item.id} type="button" className={`resources-list-item ${String(item.id) === String(selectedId) ? 'active' : ''}`} onClick={() => selectAvviso(item.id)}>
                <div><strong>{item.titolo || `Avviso ${item.codice}`}</strong><span>{item.ente_erogatore} · {item.codice}</span></div>
                <small>{item.fondo}</small>
              </button>
            ))}
            {!loading && filteredAvvisi.length === 0 ? <div className="resources-empty">Nessun avviso trovato.</div> : null}
          </div>
        </aside>

        <main className="resources-detail">
          {!selectedAvviso ? (
            <div className="resources-empty-detail"><span>📚</span><h3>Seleziona o crea un avviso</h3><p>Da qui potrai caricare la prima revisione markdown.</p></div>
          ) : (
            <>
              <header className="resources-detail-header">
                <div>
                  <span className="resources-eyebrow">{selectedAvviso.ente_erogatore} · {selectedAvviso.fondo}</span>
                  <h3>{selectedAvviso.titolo || `Avviso ${selectedAvviso.codice}`}</h3>
                  <p>Codice {selectedAvviso.codice} · stato {selectedAvviso.stato}</p>
                </div>
                <button type="button" className="resources-button review" onClick={openReview}>Vai alla revisione umana</button>
              </header>

              <section className="resources-upload-card">
                <div className="resources-section-title">
                  <div><span>Nuova fonte</span><h4>Carica una revisione `.md`</h4></div>
                  <small>UTF-8 · deduplica SHA-256 · massimo configurato dal server</small>
                </div>
                <form className="resources-upload-form" onSubmit={handleIngest}>
                  <label className="resources-file-field">
                    <span>File markdown</span>
                    <input ref={fileInputRef} aria-label="File markdown" type="file" accept=".md,text/markdown,text/plain" required onChange={(event) => setUploadFile(event.target.files?.[0] || null)} />
                    <small>{uploadFile ? uploadFile.name : 'Seleziona il documento principale dell’avviso'}</small>
                  </label>
                  <div className="resources-form-grid">
                    <label>Titolo revisione<input aria-label="Titolo revisione" required value={uploadTitle} onChange={(event) => setUploadTitle(event.target.value)} /></label>
                    <label>Etichetta facoltativa<input value={revisionLabel} onChange={(event) => setRevisionLabel(event.target.value)} placeholder="es. rettifica luglio 2026" /></label>
                  </div>
                  <label className="resources-checkbox"><input type="checkbox" checked={runExtraction} onChange={(event) => setRunExtraction(event.target.checked)} /><span>Analizza subito con l’agente avviso_extractor</span></label>
                  <button type="submit" className="resources-button primary wide" disabled={!canWrite || uploading || !uploadFile || !uploadTitle.trim()}>
                    {uploading ? 'Analisi in corso…' : 'Analizza e crea proposte'}
                  </button>
                </form>

                {ingestResult ? (
                  <div className="resources-result">
                    <div><strong>Revisione #{ingestResult.revisione?.numero_revisione}</strong><StatusBadge value={ingestResult.revisione?.stato_estrazione} /></div>
                    {Number.isFinite(suggestionsCount) ? <p><strong>{suggestionsCount} proposte create.</strong> Controllale prima di materializzare regole e scadenze.</p> : null}
                    {ingestResult.estrazione?.skipped ? <p>Analisi non eseguita: {ingestResult.estrazione.skipped}</p> : null}
                    <button type="button" className="resources-button review" onClick={openReview}>Vai alla revisione umana</button>
                  </div>
                ) : null}
              </section>

              <section className="resources-history">
                <div className="resources-section-title">
                  <div><span>Provenienza</span><h4>Storico revisioni</h4></div>
                  <small>{revisions.length} versioni</small>
                </div>
                {revisionsLoading ? <div className="resources-empty">Caricamento revisioni...</div> : null}
                {!revisionsLoading && revisions.length === 0 ? <div className="resources-empty">Nessuna revisione caricata.</div> : null}
                {!revisionsLoading && revisions.map((revision) => (
                  <article key={revision.id} className="resources-revision">
                    <div className="resources-revision-number">v{revision.numero_revisione}</div>
                    <div className="resources-revision-main">
                      <strong>{revision.titolo || revision.original_filename}</strong>
                      <span>{revision.original_filename || 'markdown'} · {formatDateTime(revision.created_at)}</span>
                      {revision.etichetta_revisione ? <small>{revision.etichetta_revisione}</small> : null}
                    </div>
                    <div className="resources-revision-meta">
                      <StatusBadge value={revision.stato_estrazione} />
                      {revision.extraction_run_id ? <small>Run #{revision.extraction_run_id}</small> : null}
                    </div>
                  </article>
                ))}
              </section>
            </>
          )}
        </main>
      </div>
    </div>
  );
}
