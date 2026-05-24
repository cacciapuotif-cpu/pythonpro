import React, { useState, useRef } from 'react';
import {
  uploadConvenzione, confirmConvenzione,
  uploadFormulario, confirmFormulario,
  uploadPianoFinanziario, confirmPianoFinanziario,
  uploadAmmissioneFondimpresa, confirmAmmissioneFondimpresa,
  uploadRiepilogoFondimpresa, confirmRiepilogoFondimpresa,
} from '../services/apiService';
import './FapiUpload.css';

// ── helpers ──────────────────────────────────────────────────────────────────

function formatEuro(n) {
  if (n == null) return '—';
  return new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR' }).format(n);
}

// ── DropZone ─────────────────────────────────────────────────────────────────

function DropZone({ accept, onFile, label }) {
  const inputRef = useRef();
  const [drag, setDrag] = useState(false);

  function handleDrop(e) {
    e.preventDefault();
    setDrag(false);
    const f = e.dataTransfer.files[0];
    if (f) onFile(f);
  }

  return (
    <div
      className={`fapi-drop-zone ${drag ? 'active' : ''}`}
      onDragOver={e => { e.preventDefault(); setDrag(true); }}
      onDragLeave={() => setDrag(false)}
      onDrop={handleDrop}
      onClick={() => inputRef.current.click()}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="fapi-file-input"
        onChange={e => { if (e.target.files[0]) onFile(e.target.files[0]); }}
      />
      📂 {label}
    </div>
  );
}

function PlaceholderDocumentModal({ title, label, confirmLabel, doneMessage, onClose, onSuccess }) {
  const [step, setStep] = useState('pick');
  const [file, setFile] = useState(null);

  function handleFile(selectedFile) {
    setFile(selectedFile);
    setStep('preview');
  }

  function handleConfirm() {
    setStep('done');
    onSuccess && onSuccess({ placeholder: true, file_name: file?.name });
  }

  return (
    <div className="fapi-modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="fapi-modal">
        <h3>{title}</h3>
        {step === 'pick' && (
          <DropZone accept=".pdf" onFile={handleFile} label={label} />
        )}
        {step === 'preview' && file && (
          <div className="fapi-preview">
            <div className="fapi-preview-section">
              <strong>Anteprima documento</strong>
              <table>
                <tbody>
                  <tr><td>Nome file</td><td>{file.name}</td></tr>
                  <tr><td>Dimensione</td><td>{Math.round(file.size / 1024)} KB</td></tr>
                  <tr><td>Tipo</td><td>{file.type || 'application/pdf'}</td></tr>
                </tbody>
              </table>
            </div>
            <div className="fapi-warning">
              ⚠️ Flusso backend specifico non ancora disponibile: procedi con wizard/manuale operativo.
            </div>
          </div>
        )}
        {step === 'done' && (
          <div className="fapi-success">{doneMessage}</div>
        )}
        <div className="fapi-modal-footer">
          <button className="fapi-btn" onClick={onClose}>{step === 'done' ? 'Chiudi' : 'Annulla'}</button>
          {step === 'preview' && (
            <button className="fapi-btn primary" onClick={handleConfirm}>{confirmLabel}</button>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Modal Convenzione ─────────────────────────────────────────────────────────

function ConvenzioneModal({ onClose, onSuccess }) {
  const [step, setStep] = useState('pick');    // pick | uploading | preview | confirming | done
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState('');

  async function handleFile(file) {
    setStep('uploading');
    setError('');
    try {
      const data = await uploadConvenzione(file);
      setPreview(data);
      setStep('preview');
    } catch (err) {
      setError(err?.response?.data?.detail || 'Errore durante upload');
      setStep('pick');
    }
  }

  async function handleConfirm() {
    setStep('confirming');
    try {
      const result = await confirmConvenzione(preview.preview_token);
      setPreview(prev => ({ ...prev, _result: result }));
      setStep('done');
      onSuccess && onSuccess(result);
    } catch (err) {
      setError(err?.response?.data?.detail || 'Errore durante conferma');
      setStep('preview');
    }
  }

  return (
    <div className="fapi-modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="fapi-modal">
        <h3>📄 Carica Convenzione FAPI</h3>

        {error && <div className="fapi-error">⚠️ {error}</div>}

        {step === 'pick' && (
          <DropZone accept=".pdf" onFile={handleFile} label="Trascina o clicca per selezionare la convenzione PDF" />
        )}

        {step === 'uploading' && (
          <div style={{ textAlign: 'center', padding: '2rem', fontSize: 13 }}>
            ⏳ Parsing del PDF in corso…
          </div>
        )}

        {(step === 'preview' || step === 'confirming') && preview && (
          <div className="fapi-preview">
            {preview.warnings?.map((w, i) => (
              <div key={i} className="fapi-warning">⚠️ {w}</div>
            ))}

            <div className="fapi-preview-section">
              <strong>Piano FAPI</strong>
              <table>
                <tbody>
                  <tr><td>Codice</td><td>{preview.piano?.codice_fapi || '—'}</td></tr>
                  <tr><td>Titolo</td><td>{preview.piano?.titolo || '—'}</td></tr>
                  <tr><td>Delibera</td><td>n. {preview.piano?.delibera_numero || '—'} del {preview.piano?.delibera_data || '—'}</td></tr>
                  <tr><td>Costo totale</td><td>{formatEuro(preview.piano?.costo_totale)}</td></tr>
                  <tr><td>Contributo FAPI</td><td>{formatEuro(preview.piano?.contributo_ente)}</td></tr>
                  <tr><td>Cofinanziamento</td><td>{formatEuro(preview.piano?.cofinanziamento)}</td></tr>
                </tbody>
              </table>
            </div>

            <div className="fapi-preview-section">
              <strong>Ente Attuatore</strong>
              <table>
                <tbody>
                  <tr>
                    <td>{preview.ente_attuatore?.ragione_sociale || '—'}</td>
                    <td>P.IVA {preview.ente_attuatore?.partita_iva || '—'}</td>
                    <td>
                      {preview.ente_attuatore?.exists_in_db
                        ? <span className="badge-exists">Nel sistema</span>
                        : <span className="badge-new">Nuovo</span>}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div className="fapi-preview-section">
              <strong>Aziende beneficiarie ({preview.aziende_beneficiarie?.length || 0})</strong>
              <table>
                <thead>
                  <tr><th>Ragione Sociale</th><th>P.IVA</th><th>Part.</th><th>Importo</th><th></th></tr>
                </thead>
                <tbody>
                  {(preview.aziende_beneficiarie || []).map((az, i) => (
                    <tr key={i}>
                      <td>{az.ragione_sociale}</td>
                      <td>{az.partita_iva || '—'}</td>
                      <td>{az.num_partecipanti || '—'}</td>
                      <td>{formatEuro(az.importo)}</td>
                      <td>
                        {az.exists_in_db
                          ? <span className="badge-exists">Esiste</span>
                          : <span className="badge-new">Nuova</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {preview.codici_progetto?.length > 0 && (
              <div className="fapi-preview-section">
                <strong>Codici progetto trovati</strong>
                <div style={{ fontSize: 11, color: '#666' }}>
                  {preview.codici_progetto.join(' · ')}
                </div>
              </div>
            )}
          </div>
        )}

        {step === 'done' && preview?._result && (
          <div className="fapi-success">
            ✅ Progetto creato — ID: <strong>{preview._result.project_id}</strong><br />
            Aziende create: {preview._result.aziende_create} · Associate: {preview._result.aziende_associate}<br />
            Suggestions create: {preview._result.suggestions_create}
          </div>
        )}

        <div className="fapi-modal-footer">
          <button className="fapi-btn" onClick={onClose}>
            {step === 'done' ? 'Chiudi' : 'Annulla'}
          </button>
          {step === 'preview' && (
            <button className="fapi-btn primary" onClick={handleConfirm}>
              ✅ Conferma e Crea Progetto
            </button>
          )}
          {step === 'confirming' && (
            <button className="fapi-btn primary" disabled>⏳ Creazione…</button>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Modal Formulario ──────────────────────────────────────────────────────────

function FormularioModal({ projectId, onClose, onSuccess }) {
  const [step, setStep] = useState('pick');
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState('');

  async function handleFile(file) {
    setStep('uploading');
    setError('');
    try {
      const data = await uploadFormulario(projectId, file);
      setPreview(data);
      setStep('preview');
    } catch (err) {
      setError(err?.response?.data?.detail || 'Errore durante upload');
      setStep('pick');
    }
  }

  async function handleConfirm() {
    setStep('confirming');
    try {
      const result = await confirmFormulario(projectId, preview.preview_token);
      setPreview(prev => ({ ...prev, _result: result }));
      setStep('done');
      onSuccess && onSuccess(result);
    } catch (err) {
      setError(err?.response?.data?.detail || 'Errore durante conferma');
      setStep('preview');
    }
  }

  const totalModuli = preview?.tutti_moduli?.length || 0;
  const formativi = preview?.tutti_moduli?.filter(m => m.tipo_attivita === 'formativa').length || 0;
  const propedeutici = preview?.tutti_moduli?.filter(m => m.tipo_attivita === 'propedeutica').length || 0;

  return (
    <div className="fapi-modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="fapi-modal">
        <h3>📋 Carica Formulario FAPI — Progetto #{projectId}</h3>

        {error && <div className="fapi-error">⚠️ {error}</div>}

        {step === 'pick' && (
          <DropZone accept=".pdf" onFile={handleFile} label="Trascina o clicca per selezionare il formulario PDF" />
        )}

        {step === 'uploading' && (
          <div style={{ textAlign: 'center', padding: '2rem', fontSize: 13 }}>⏳ Parsing del PDF…</div>
        )}

        {(step === 'preview' || step === 'confirming') && preview && (
          <div className="fapi-preview">
            {preview.warnings?.map((w, i) => (
              <div key={i} className="fapi-warning">⚠️ {w}</div>
            ))}
            <div className="fapi-preview-section">
              <strong>Moduli trovati: {totalModuli} ({formativi} formativi · {propedeutici} propedeutici)</strong>
              <table>
                <thead>
                  <tr><th>Cod. PG</th><th>Titolo</th><th>Modalità</th><th>Tipo</th><th>Ore</th></tr>
                </thead>
                <tbody>
                  {(preview.tutti_moduli || []).map((m, i) => (
                    <tr key={i}>
                      <td>{m.codice_progetto_fapi || '—'}</td>
                      <td style={{ maxWidth: 200, wordBreak: 'break-word' }}>{m.titolo_modulo}</td>
                      <td>{m.modalita_erogazione}</td>
                      <td>
                        {m.tipo_attivita === 'propedeutica'
                          ? <span className="badge-new">propedeutica</span>
                          : <span className="badge-exists">formativa</span>}
                      </td>
                      <td>{m.ore_previste ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {step === 'done' && preview?._result && (
          <div className="fapi-success">
            ✅ Moduli creati: <strong>{preview._result.moduli_creati}</strong>
          </div>
        )}

        <div className="fapi-modal-footer">
          <button className="fapi-btn" onClick={onClose}>
            {step === 'done' ? 'Chiudi' : 'Annulla'}
          </button>
          {step === 'preview' && totalModuli > 0 && (
            <button className="fapi-btn primary" onClick={handleConfirm}>
              ✅ Conferma e Salva Moduli
            </button>
          )}
          {step === 'confirming' && (
            <button className="fapi-btn primary" disabled>⏳ Salvataggio…</button>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Modal Piano Finanziario ────────────────────────────────────────────────────

function PianoFinanziarioModal({ projectId, onClose, onSuccess }) {
  const [step, setStep] = useState('pick');
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState('');

  async function handleFile(file) {
    setStep('uploading');
    setError('');
    try {
      const data = await uploadPianoFinanziario(projectId, file);
      setPreview(data);
      setStep('preview');
    } catch (err) {
      setError(err?.response?.data?.detail || 'Errore durante upload');
      setStep('pick');
    }
  }

  async function handleConfirm() {
    setStep('confirming');
    try {
      const result = await confirmPianoFinanziario(projectId, preview.preview_token);
      setPreview(prev => ({ ...prev, _result: result }));
      setStep('done');
      onSuccess && onSuccess(result);
    } catch (err) {
      setError(err?.response?.data?.detail || 'Errore durante conferma');
      setStep('preview');
    }
  }

  return (
    <div className="fapi-modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="fapi-modal">
        <h3>💰 Carica Piano Finanziario FAPI — Progetto #{projectId}</h3>

        {error && <div className="fapi-error">⚠️ {error}</div>}

        {step === 'pick' && (
          <DropZone accept=".xlsx,.xls" onFile={handleFile} label="Trascina o clicca per selezionare il piano finanziario XLSX" />
        )}

        {step === 'uploading' && (
          <div style={{ textAlign: 'center', padding: '2rem', fontSize: 13 }}>⏳ Parsing XLSX…</div>
        )}

        {(step === 'preview' || step === 'confirming') && preview && (
          <div className="fapi-preview">
            {preview.warnings?.map((w, i) => (
              <div key={i} className="fapi-warning">⚠️ {w}</div>
            ))}
            <div className="fapi-preview-section">
              <strong>
                {preview.voci?.length || 0} voci trovate — Totale: {formatEuro(preview.totale_preventivo)}
              </strong>
              <table>
                <thead>
                  <tr><th>Voce</th><th>Categoria</th><th>Descrizione</th><th>Ore</th><th>Importo</th></tr>
                </thead>
                <tbody>
                  {(preview.voci || []).slice(0, 30).map((v, i) => (
                    <tr key={i}>
                      <td>{v.voce_codice}</td>
                      <td>{v.categoria}</td>
                      <td style={{ maxWidth: 180, wordBreak: 'break-word' }}>{v.descrizione || '—'}</td>
                      <td>{v.ore_previste || '—'}</td>
                      <td>{formatEuro(v.importo_preventivo)}</td>
                    </tr>
                  ))}
                  {(preview.voci?.length || 0) > 30 && (
                    <tr><td colSpan="5" style={{ textAlign: 'center', color: '#999' }}>
                      … e altre {preview.voci.length - 30} voci
                    </td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {step === 'done' && preview?._result && (
          <div className="fapi-success">
            ✅ Piano finanziario creato — ID: <strong>{preview._result.piano_id}</strong><br />
            Voci create: <strong>{preview._result.voci_create}</strong>
          </div>
        )}

        <div className="fapi-modal-footer">
          <button className="fapi-btn" onClick={onClose}>
            {step === 'done' ? 'Chiudi' : 'Annulla'}
          </button>
          {step === 'preview' && (preview.voci?.length || 0) > 0 && (
            <button className="fapi-btn primary" onClick={handleConfirm}>
              ✅ Conferma e Salva Voci
            </button>
          )}
          {step === 'confirming' && (
            <button className="fapi-btn primary" disabled>⏳ Salvataggio…</button>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Modal Ammissione Fondimpresa ──────────────────────────────────────────────

function AmmissioneFondimpresaModal({ onClose, onSuccess }) {
  const [step, setStep] = useState('pick');
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState('');

  async function handleFile(file) {
    setStep('uploading');
    setError('');
    try {
      const data = await uploadAmmissioneFondimpresa(file);
      setPreview(data);
      setStep('preview');
    } catch (err) {
      setError(err?.response?.data?.detail || 'Errore durante upload');
      setStep('pick');
    }
  }

  async function handleConfirm() {
    setStep('confirming');
    try {
      const result = await confirmAmmissioneFondimpresa(preview.preview_token);
      setPreview(prev => ({ ...prev, _result: result }));
      setStep('done');
      onSuccess && onSuccess(result);
    } catch (err) {
      setError(err?.response?.data?.detail || 'Errore durante conferma');
      setStep('preview');
    }
  }

  return (
    <div className="fapi-modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="fapi-modal">
        <h3>📄 Carica Lettera Ammissione Fondimpresa</h3>
        {error && <div className="fapi-error">⚠️ {error}</div>}
        {step === 'pick' && (
          <DropZone accept=".pdf" onFile={handleFile} label="Trascina o clicca per selezionare la lettera PDF" />
        )}
        {step === 'uploading' && (
          <div style={{ textAlign: 'center', padding: '2rem', fontSize: 13 }}>⏳ Parsing del PDF…</div>
        )}
        {(step === 'preview' || step === 'confirming') && preview && (
          <div className="fapi-preview">
            {preview.warnings?.map((w, i) => <div key={i} className="fapi-warning">⚠️ {w}</div>)}
            <div className="fapi-preview-section">
              <strong>Piano Fondimpresa</strong>
              <table>
                <tbody>
                  <tr><td>Codice</td><td>{preview.codice_piano || '—'}</td></tr>
                  <tr><td>Titolo</td><td>{preview.titolo_piano || '—'}</td></tr>
                  <tr><td>CUP</td><td>{preview.cup || '—'}</td></tr>
                  <tr><td>Avviso</td><td>{preview.avviso_numero || '—'}</td></tr>
                  <tr><td>Soggetto attuatore</td><td>{preview.soggetto_attuatore || '—'}</td></tr>
                  <tr><td>Importo massimo</td><td>{formatEuro(preview.contributo_ente)}</td></tr>
                  <tr><td>Determina</td><td>{preview.determina_data || '—'}</td></tr>
                </tbody>
              </table>
            </div>
          </div>
        )}
        {step === 'done' && preview?._result && (
          <div className="fapi-success">
            ✅ Progetto Fondimpresa creato — ID: <strong>{preview._result.project_id}</strong>
          </div>
        )}
        <div className="fapi-modal-footer">
          <button className="fapi-btn" onClick={onClose}>{step === 'done' ? 'Chiudi' : 'Annulla'}</button>
          {step === 'preview' && (
            <button className="fapi-btn primary" onClick={handleConfirm}>✅ Conferma e Crea Progetto</button>
          )}
          {step === 'confirming' && <button className="fapi-btn primary" disabled>⏳ Creazione…</button>}
        </div>
      </div>
    </div>
  );
}

// ── Modal Riepilogo Fondimpresa ───────────────────────────────────────────────

function RiepilogoFondimpresaModal({ projectId, onClose, onSuccess }) {
  const [step, setStep] = useState('pick');
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState('');

  async function handleFile(file) {
    setStep('uploading');
    setError('');
    try {
      const data = await uploadRiepilogoFondimpresa(projectId, file);
      setPreview(data);
      setStep('preview');
    } catch (err) {
      setError(err?.response?.data?.detail || 'Errore durante upload');
      setStep('pick');
    }
  }

  async function handleConfirm() {
    setStep('confirming');
    try {
      const result = await confirmRiepilogoFondimpresa(projectId, preview.preview_token);
      setPreview(prev => ({ ...prev, _result: result }));
      setStep('done');
      onSuccess && onSuccess(result);
    } catch (err) {
      setError(err?.response?.data?.detail || 'Errore durante conferma');
      setStep('preview');
    }
  }

  const aziende = preview?.aziende_beneficiarie?.length || 0;
  const azioni = preview?.azioni_formative?.length || 0;
  const voci = preview?.piano_finanziario?.length || 0;

  return (
    <div className="fapi-modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="fapi-modal">
        <h3>📊 Carica Excel Riepilogo Fondimpresa — Progetto #{projectId}</h3>
        {error && <div className="fapi-error">⚠️ {error}</div>}
        {step === 'pick' && (
          <DropZone accept=".xlsx,.xls" onFile={handleFile} label="Trascina o clicca per selezionare il riepilogo Excel" />
        )}
        {step === 'uploading' && (
          <div style={{ textAlign: 'center', padding: '2rem', fontSize: 13 }}>⏳ Parsing Excel…</div>
        )}
        {(step === 'preview' || step === 'confirming') && preview && (
          <div className="fapi-preview">
            {preview.warnings?.map((w, i) => <div key={i} className="fapi-warning">⚠️ {w}</div>)}
            <div className="fapi-preview-section">
              <strong>{aziende} aziende · {azioni} azioni · {voci} voci piano</strong>
              <table>
                <thead>
                  <tr><th>Azienda</th><th>CF</th><th>Regime</th><th>Finanziamento</th></tr>
                </thead>
                <tbody>
                  {(preview.aziende_beneficiarie || []).map((az, i) => (
                    <tr key={i}>
                      <td>{az.ragione_sociale}</td>
                      <td>{az.codice_fiscale || '—'}</td>
                      <td>{az.regime_aiuto || '—'}</td>
                      <td>{formatEuro(az.finanziamento)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
        {step === 'done' && preview?._result && (
          <div className="fapi-success">
            ✅ Riepilogo salvato — aziende create: <strong>{preview._result.aziende_create}</strong>,
            moduli: <strong>{preview._result.moduli_creati}</strong>,
            voci piano: <strong>{preview._result.voci_piano}</strong>
          </div>
        )}
        <div className="fapi-modal-footer">
          <button className="fapi-btn" onClick={onClose}>{step === 'done' ? 'Chiudi' : 'Annulla'}</button>
          {step === 'preview' && (
            <button className="fapi-btn primary" onClick={handleConfirm}>✅ Conferma e Salva</button>
          )}
          {step === 'confirming' && <button className="fapi-btn primary" disabled>⏳ Salvataggio…</button>}
        </div>
      </div>
    </div>
  );
}

function NuovoPianoModal({ onChoose, onClose }) {
  const cards = [
    {
      key: 'convenzione',
      icon: '🏦',
      title: 'FAPI',
      description: 'Upload convenzione PDF con parsing e conferma progetto.',
    },
    {
      key: 'ammissione-fondimpresa',
      icon: '🏗️',
      title: 'Fondimpresa',
      description: 'Upload lettera ammissione PDF con anteprima dei dati estratti.',
    },
    {
      key: 'atto-formazienda',
      icon: '🏢',
      title: 'Formazienda',
      description: 'Upload atto adesione PDF e avvio del flusso documentale.',
    },
    {
      key: 'altro-ente',
      icon: '🏛️',
      title: 'Altro ente',
      description: 'Usa wizard manuale per configurazione progetto e documenti.',
    },
  ];

  return (
    <div className="fapi-modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="fapi-modal">
        <h3>📄 Carica Atto / Convenzione</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12 }}>
          {cards.map((card) => (
            <button
              key={card.key}
              className="fapi-btn"
              style={{ height: 132, textAlign: 'left', alignItems: 'flex-start', justifyContent: 'flex-start', display: 'flex', flexDirection: 'column', gap: 8, whiteSpace: 'normal' }}
              onClick={() => onChoose(card.key)}
            >
              <span style={{ fontSize: 20 }}>{card.icon}</span>
              <strong>{card.title}</strong>
              <span style={{ fontSize: 12, color: 'var(--color-text-secondary)' }}>{card.description}</span>
            </button>
          ))}
        </div>
        <div className="fapi-modal-footer">
          <button className="fapi-btn" onClick={onClose}>Chiudi</button>
        </div>
      </div>
    </div>
  );
}

// ── FapiUploadSection (componente principale) ────────────────────────────────

export function FapiUploadSection({ project, onRefresh, autoOpenConvenzione, autoOpenMode, onAutoClose }) {
  const [modal, setModal] = useState(autoOpenConvenzione ? (autoOpenMode || 'new-piano') : null);

  const isFapi = project?.ente_erogatore === 'FAPI' || project?.codice_fapi;
  const isFondimpresa = project?.ente_erogatore === 'Fondimpresa';
  const isFormazienda = project?.ente_erogatore === 'Formazienda';
  const unsupportedEnte = project && !isFapi && !isFondimpresa && !isFormazienda;
  const hasPrimaryDocument = Boolean(project?.convenzione_file_path);

  const primaryLabel = isFapi
    ? (hasPrimaryDocument ? '✅ Convenzione' : '📄 Carica Convenzione')
    : isFondimpresa
      ? (hasPrimaryDocument ? '✅ Lettera ammissione' : '📄 Carica Lettera Ammissione')
      : isFormazienda
        ? (hasPrimaryDocument ? '✅ Atto adesione' : '📄 Carica Atto adesione')
        : '📄 Documento';

  return (
    <div className="fapi-upload-section">
      <h4>📁 Documenti {isFondimpresa ? 'Fondimpresa' : isFormazienda ? 'Formazienda' : 'FAPI'}</h4>
      <div className="fapi-buttons">
        {!project && (
          <button className="fapi-btn primary" onClick={() => setModal('new-piano')}>
            📄 Carica Atto / Convenzione
          </button>
        )}
        {project && isFapi && (
          <>
            <button className="fapi-btn primary" onClick={() => setModal('convenzione')}>
              {primaryLabel}
            </button>
            <button className="fapi-btn" onClick={() => setModal('formulario')}>
              📋 Carica Formulario
            </button>
            <button className="fapi-btn" onClick={() => setModal('piano')}>
              💰 Carica Piano Finanziario
            </button>
          </>
        )}
        {project && isFondimpresa && (
          <>
            <button className="fapi-btn primary" onClick={() => setModal('ammissione-fondimpresa')}>
              {primaryLabel}
            </button>
            <button className="fapi-btn" onClick={() => setModal('riepilogo-fondimpresa')}>
              📊 Carica Excel Riepilogo
            </button>
          </>
        )}
        {project && isFormazienda && (
          <>
            <button className="fapi-btn primary" onClick={() => setModal('atto-formazienda')}>
              {primaryLabel}
            </button>
            <button className="fapi-btn" onClick={() => setModal('piano-formazienda')}>
              💰 Carica Piano Fin.
            </button>
          </>
        )}
        {unsupportedEnte && (
          null
        )}
      </div>

      {project?.codice_fapi && (
        <div style={{ marginTop: '0.5rem', fontSize: 11, color: 'var(--color-text-secondary)' }}>
          Codice FAPI: <strong>{project.codice_fapi}</strong>
          {project.delibera_numero && ` · Delibera n. ${project.delibera_numero} del ${project.delibera_data || '—'}`}
        </div>
      )}

      {modal === 'new-piano' && (
        <NuovoPianoModal
          onChoose={(value) => setModal(value)}
          onClose={() => { setModal(null); onAutoClose && onAutoClose(); }}
        />
      )}
      {modal === 'convenzione' && (
        <ConvenzioneModal
          onClose={() => { setModal(null); onAutoClose && onAutoClose(); }}
          onSuccess={() => { setModal(null); onRefresh && onRefresh(); onAutoClose && onAutoClose(); }}
        />
      )}
      {modal === 'ammissione-fondimpresa' && (
        <AmmissioneFondimpresaModal
          onClose={() => { setModal(null); onAutoClose && onAutoClose(); }}
          onSuccess={() => { setModal(null); onRefresh && onRefresh(); onAutoClose && onAutoClose(); }}
        />
      )}
      {modal === 'riepilogo-fondimpresa' && project && (
        <RiepilogoFondimpresaModal
          projectId={project.id}
          onClose={() => setModal(null)}
          onSuccess={() => { setModal(null); onRefresh && onRefresh(); }}
        />
      )}
      {modal === 'atto-formazienda' && (
        <PlaceholderDocumentModal
          title="🏢 Carica Atto adesione Formazienda"
          label="Trascina o clicca per selezionare l'atto adesione PDF"
          confirmLabel="✅ Conferma documento"
          doneMessage="✅ Documento acquisito in anteprima. Prosegui con il wizard/manuale operativo."
          onClose={() => { setModal(null); onAutoClose && onAutoClose(); }}
          onSuccess={() => { setModal(null); onAutoClose && onAutoClose(); onRefresh && onRefresh(); }}
        />
      )}
      {modal === 'altro-ente' && (
        <PlaceholderDocumentModal
          title="🏛️ Altro ente"
          label="Seleziona l'atto ufficiale del fondo/ente"
          confirmLabel="Apri wizard manuale"
          doneMessage="✅ Usa wizard manuale per completare configurazione e documenti."
          onClose={() => { setModal(null); onAutoClose && onAutoClose(); }}
          onSuccess={() => { setModal(null); onAutoClose && onAutoClose(); }}
        />
      )}
      {modal === 'formulario' && project && (
        <FormularioModal
          projectId={project.id}
          onClose={() => setModal(null)}
          onSuccess={() => setModal(null)}
        />
      )}
      {(modal === 'piano' || modal === 'piano-formazienda') && project && (
        <PianoFinanziarioModal
          projectId={project.id}
          onClose={() => setModal(null)}
          onSuccess={() => setModal(null)}
        />
      )}
    </div>
  );
}

export default FapiUploadSection;
