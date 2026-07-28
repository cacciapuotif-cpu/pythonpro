import React, { useEffect, useState, useRef } from 'react';
import {
  uploadConvenzione, confirmConvenzione,
  uploadConvenzioneProgetto, confirmConvenzioneProgetto,
  uploadFormulario, confirmFormulario,
  uploadPianoFinanziario, confirmPianoFinanziario,
  uploadAmmissioneFondimpresa, confirmAmmissioneFondimpresa,
  uploadAmmissioneFondimpresaProgetto, confirmAmmissioneFondimpresaProgetto,
  uploadRiepilogoFondimpresa, confirmRiepilogoFondimpresa,
  getDocumentiProgetto, downloadDocumentoProgetto,
} from '../services/apiService';
import { formatApiError } from '../lib/errors';
import './FapiUpload.css';

// ── helpers ──────────────────────────────────────────────────────────────────

function formatEuro(n) {
  if (n == null) return '—';
  return new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR' }).format(n);
}

// ── UX-6: allega a un progetto esistente ─────────────────────────────────────
// Convenzione FAPI e lettera Fondimpresa condividono la stessa regola: dentro
// un progetto il documento si allega, i campi vuoti si arricchiscono e quelli
// gia' valorizzati non si toccano senza una spunta esplicita.

function useDocumentoProgetto({ projectId, upload, uploadProgetto, conferma, confermaProgetto }) {
  const associa = Boolean(projectId);
  const [step, setStep] = useState('pick');  // pick | uploading | preview | confirming | done
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState('');
  const [campiScelti, setCampiScelti] = useState([]);

  async function handleFile(file) {
    setStep('uploading');
    setError('');
    try {
      const data = associa ? await uploadProgetto(projectId, file) : await upload(file);
      setPreview(data);
      setCampiScelti([]);
      setStep('preview');
    } catch (err) {
      setError(formatApiError(err));
      setStep('pick');
    }
  }

  async function handleConfirm(onSuccess, options = {}) {
    setStep('confirming');
    try {
      const targetProjectId = options.projectId || projectId;
      let result;
      if (targetProjectId) {
        result = options.modalita
          ? await confermaProgetto(
            targetProjectId,
            preview.preview_token,
            campiScelti,
            options.modalita,
            options.tipoDocumento,
          )
          : await confermaProgetto(
            targetProjectId,
            preview.preview_token,
            campiScelti,
          );
      } else {
        result = options.createPayload
          ? await conferma(preview.preview_token, options.createPayload)
          : await conferma(preview.preview_token);
      }
      setPreview(prev => ({
        ...prev,
        _result: result,
        _operation: targetProjectId ? (options.modalita || 'arricchisci') : 'crea',
      }));
      setStep('done');
      onSuccess && onSuccess(result);
    } catch (err) {
      setError(formatApiError(err));
      setStep('preview');
    }
  }

  function toggleCampo(campo) {
    setCampiScelti(prev =>
      prev.includes(campo) ? prev.filter(c => c !== campo) : [...prev, campo]
    );
  }

  return {
    associa,
    step,
    preview,
    error,
    setError,
    campiScelti,
    handleFile,
    handleConfirm,
    toggleCampo,
  };
}

function DiffProgetto({ diff, campiScelti, onToggle }) {
  const conflitti = (diff || []).filter(d => d.conflitto);
  const arricchimenti = (diff || []).filter(d => !d.conflitto);

  return (
    <div className="fapi-preview-section">
      <strong>Cosa cambia sul progetto</strong>
      {(diff || []).length === 0 && (
        <div style={{ fontSize: 12, color: '#666' }}>
          Il documento non porta dati nuovi: verrà solo allegato.
        </div>
      )}
      {arricchimenti.length > 0 && (
        <table>
          <thead>
            <tr><th>Campo vuoto</th><th>Valore dal documento</th></tr>
          </thead>
          <tbody>
            {arricchimenti.map(d => (
              <tr key={d.campo}>
                <td>{d.etichetta}</td>
                <td>{String(d.valore_estratto)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {conflitti.length > 0 && (
        <>
          <div className="fapi-warning">
            ⚠️ {conflitti.length} campo/i hanno già un valore diverso.
            Restano invariati salvo tua spunta esplicita.
          </div>
          <table>
            <thead>
              <tr><th>Sovrascrivi</th><th>Campo</th><th>Valore attuale</th><th>Dal documento</th></tr>
            </thead>
            <tbody>
              {conflitti.map(d => (
                <tr key={d.campo}>
                  <td>
                    <input
                      type="checkbox"
                      aria-label={`Sovrascrivi ${d.etichetta}`}
                      checked={campiScelti.includes(d.campo)}
                      onChange={() => onToggle(d.campo)}
                    />
                  </td>
                  <td>{d.etichetta}</td>
                  <td>{String(d.valore_attuale)}</td>
                  <td>{String(d.valore_estratto)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}

function ConfrontoCompleto({ confronto, campiScelti, onToggle }) {
  return (
    <div className="fapi-preview-section">
      <strong>Confronto con il progetto esistente</strong>
      <table>
        <thead>
          <tr>
            <th>Aggiorna</th>
            <th>Campo</th>
            <th>Valore attuale</th>
            <th>Dal documento</th>
            <th>Stato</th>
          </tr>
        </thead>
        <tbody>
          {(confronto || []).map(riga => (
            <tr key={riga.campo}>
              <td>
                {riga.stato !== 'identico' && (
                  <input
                    type="checkbox"
                    aria-label={`Aggiorna ${riga.etichetta}`}
                    checked={campiScelti.includes(riga.campo)}
                    onChange={() => onToggle(riga.campo)}
                  />
                )}
              </td>
              <td>{riga.etichetta}</td>
              <td>{riga.valore_attuale == null ? '—' : String(riga.valore_attuale)}</td>
              <td>{riga.valore_estratto == null ? '—' : String(riga.valore_estratto)}</td>
              <td>
                <span className={`fapi-diff-status ${riga.stato}`}>
                  {riga.stato.replaceAll('_', ' ')}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ConfrontoAziende({ aziende }) {
  if (!aziende?.length) return null;
  return (
    <div className="fapi-preview-section">
      <strong>Confronto aziende beneficiarie</strong>
      <table>
        <thead>
          <tr>
            <th>Azienda</th>
            <th>Nel progetto</th>
            <th>Codice progetto</th>
            <th>Partecipanti</th>
            <th>Totale</th>
          </tr>
        </thead>
        <tbody>
          {aziende.map((azienda, index) => (
            <tr key={azienda.codice_progetto || azienda.azienda_id || index}>
              <td>{azienda.ragione_sociale}</td>
              <td>
                {azienda.gia_associata
                  ? <span className="badge-exists">Associata</span>
                  : <span className="badge-new">Da associare</span>}
              </td>
              <td>{azienda.codice_progetto || '—'}</td>
              <td>{azienda.num_partecipanti ?? '—'}</td>
              <td>{formatEuro(azienda.importo)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="fapi-domain-note">
        Codice, partecipanti e totale sono mostrati senza salvarli finché non
        viene confermato il modello degli interventi per azienda.
      </div>
    </div>
  );
}

function DocumentiProgetto({ projectId, refreshKey }) {
  const [documenti, setDocumenti] = useState([]);
  const [errore, setErrore] = useState('');

  useEffect(() => {
    let mounted = true;
    if (!projectId) return undefined;
    getDocumentiProgetto(projectId)
      .then(rows => {
        if (mounted) setDocumenti(rows || []);
      })
      .catch(err => {
        if (mounted) setErrore(formatApiError(err));
      });
    return () => { mounted = false; };
  }, [projectId, refreshKey]);

  async function scarica(documento) {
    try {
      const blob = await downloadDocumentoProgetto(projectId, documento.id);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = documento.file_name || `documento-${documento.id}`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setErrore(formatApiError(err));
    }
  }

  if (!documenti.length && !errore) return null;
  return (
    <div className="fapi-project-documents">
      <strong>Documenti archiviati</strong>
      {errore && <div className="fapi-error">⚠️ {errore}</div>}
      {documenti.map(documento => (
        <div className="fapi-project-document" key={documento.id}>
          <span>
            {documento.tipo_documento.replaceAll('_', ' ')} · v{documento.versione}
            {' · '}
            {documento.file_name}
            {documento.caricato_da_user_id
              ? ` · utente #${documento.caricato_da_user_id}`
              : ' · importato dallo storico'}
          </span>
          <button
            className="fapi-btn"
            type="button"
            onClick={() => scarica(documento)}
          >
            Scarica
          </button>
        </div>
      ))}
    </div>
  );
}

function EsitoAssociazione({ result }) {
  return (
    <>
      ✅ Documento allegato al progetto <strong>#{result.project_id}</strong><br />
      Campi aggiornati: {result.campi_applicati?.length || 0}
      {result.campi_in_conflitto_non_applicati?.length > 0 && (
        <> · lasciati invariati: {result.campi_in_conflitto_non_applicati.join(', ')}</>
      )}<br />
    </>
  );
}

function NotaAssociazione() {
  return (
    <p style={{ fontSize: 12, color: 'var(--color-text-secondary)', margin: '0 0 8px' }}>
      Il documento viene allegato a <strong>questo progetto</strong>. I dati
      estratti riempiono solo i campi ancora vuoti: quelli già valorizzati
      restano come sono, salvo tua scelta esplicita.
    </p>
  );
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

function ConvenzioneModal({ projectId, onClose, onSuccess }) {
  // UX-6: con projectId il documento si ALLEGA al progetto aperto; senza,
  // siamo nel flusso "nuovo piano" e il progetto viene creato.
  const {
    associa, step, preview, error, setError, campiScelti,
    handleFile, handleConfirm, toggleCampo,
  } = useDocumentoProgetto({
    projectId,
    upload: uploadConvenzione,
    uploadProgetto: uploadConvenzioneProgetto,
    conferma: confirmConvenzione,
    confermaProgetto: confirmConvenzioneProgetto,
  });
  const [selectedProjectId, setSelectedProjectId] = useState('');
  const [tipoDocumento, setTipoDocumento] = useState('convenzione');
  const [dataApprovazione, setDataApprovazione] = useState('');
  const [dataAvvioPiano, setDataAvvioPiano] = useState('');

  const candidati = preview?.match?.candidati || [];
  const hasGlobalMatch = !associa && candidati.length > 0;
  const targetProjectId = Number(selectedProjectId || preview?.existing_project_id || 0);
  const confrontoSelezionato = targetProjectId
    ? preview?.confronti_per_progetto?.[String(targetProjectId)] || preview?.confronto
    : [];
  const confrontoAziendeSelezionato = targetProjectId
    ? preview?.confronti_aziende_per_progetto?.[String(targetProjectId)]
      || preview?.confronto_aziende
    : [];

  useEffect(() => {
    if (preview?.existing_project_id) {
      setSelectedProjectId(String(preview.existing_project_id));
    }
    if (preview?.piano?.delibera_data) {
      setDataApprovazione(current => current || preview.piano.delibera_data);
    }
  }, [preview?.existing_project_id, preview?.piano?.delibera_data]);

  async function associaEsistente(modalita) {
    if (!targetProjectId) {
      setError('Scegli il progetto a cui associare il documento.');
      return;
    }
    await handleConfirm(onSuccess, {
      projectId: targetProjectId,
      modalita,
      tipoDocumento,
    });
  }

  async function creaProgetto({ duplicato = false } = {}) {
    if (!dataApprovazione || !dataAvvioPiano) {
      setError('Data approvazione e data avvio piano sono obbligatorie.');
      return;
    }
    if (duplicato && !window.confirm(
      'Confermi? Creerai un secondo progetto con lo stesso codice FAPI.',
    )) {
      return;
    }
    await handleConfirm(onSuccess, {
      createPayload: {
        data_approvazione: dataApprovazione,
        data_avvio_piano: dataAvvioPiano,
        tipo_documento: tipoDocumento,
        conferma_creazione_duplicato: duplicato,
      },
    });
  }

  return (
    <div className="fapi-modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="fapi-modal">
        <h3>
          {associa
            ? '📄 Allega atto / convenzione al progetto'
            : '📄 Carica Convenzione FAPI'}
        </h3>

        {associa && <NotaAssociazione />}

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

            {associa && (
              <DiffProgetto
                diff={preview.diff}
                campiScelti={campiScelti}
                onToggle={toggleCampo}
              />
            )}

            {hasGlobalMatch && (
              <>
                <div className="fapi-match-panel">
                  <strong>
                    {preview.match.stato === 'esatto'
                      ? 'Progetto esistente riconosciuto'
                      : 'Possibili progetti corrispondenti'}
                  </strong>
                  <label>
                    Progetto destinatario
                    <select
                      aria-label="Progetto destinatario"
                      value={selectedProjectId}
                      onChange={event => setSelectedProjectId(event.target.value)}
                    >
                      {preview.match.stato !== 'esatto' && (
                        <option value="">Scegli il progetto…</option>
                      )}
                      {candidati.map(candidate => (
                        <option key={candidate.project_id} value={candidate.project_id}>
                          #{candidate.project_id} · {candidate.nome}
                          {candidate.codice_fapi ? ` · ${candidate.codice_fapi}` : ''}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                {confrontoSelezionato?.length > 0 && (
                  <ConfrontoCompleto
                    confronto={confrontoSelezionato}
                    campiScelti={campiScelti}
                    onToggle={toggleCampo}
                  />
                )}
                <ConfrontoAziende aziende={confrontoAziendeSelezionato} />
              </>
            )}

            {!associa && (
              <div className="fapi-preview-section fapi-confirm-metadata">
                <strong>Classificazione e date amministrative</strong>
                <label>
                  Tipo documento
                  <select
                    aria-label="Tipo documento"
                    value={tipoDocumento}
                    onChange={event => setTipoDocumento(event.target.value)}
                  >
                    <option value="convenzione">Convenzione</option>
                    <option value="atto_concessione">Atto di concessione</option>
                    <option value="delibera">Delibera</option>
                  </select>
                </label>
                <label>
                  Data approvazione
                  <input
                    aria-label="Data approvazione"
                    type="date"
                    value={dataApprovazione}
                    onChange={event => setDataApprovazione(event.target.value)}
                  />
                </label>
                <label>
                  Data avvio piano
                  <input
                    aria-label="Data avvio piano"
                    type="date"
                    value={dataAvvioPiano}
                    onChange={event => setDataAvvioPiano(event.target.value)}
                  />
                </label>
              </div>
            )}

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
            {preview._operation !== 'crea' ? (
              <EsitoAssociazione result={preview._result} />
            ) : (
              <>
                ✅ Progetto creato — ID: <strong>{preview._result.project_id}</strong><br />
              </>
            )}
            Aziende create: {preview._result.aziende_create} · Associate: {preview._result.aziende_associate}<br />
            Suggestions create: {preview._result.suggestions_create}
          </div>
        )}

        <div className="fapi-modal-footer">
          <button className="fapi-btn" onClick={onClose}>
            {step === 'done' ? 'Chiudi' : 'Annulla'}
          </button>
          {step === 'preview' && (
            <>
              {associa && (
                <button className="fapi-btn primary" onClick={() => handleConfirm(onSuccess)}>
                  ✅ Allega al progetto
                </button>
              )}
              {!associa && !hasGlobalMatch && (
                <button className="fapi-btn primary" onClick={() => creaProgetto()}>
                  ✅ Conferma e Crea Progetto
                </button>
              )}
              {hasGlobalMatch && (
                <>
                  <button
                    className="fapi-btn primary"
                    disabled={!targetProjectId}
                    onClick={() => associaEsistente('associa')}
                  >
                    Associa al progetto esistente
                  </button>
                  <button
                    className="fapi-btn"
                    disabled={!targetProjectId}
                    onClick={() => associaEsistente('aggiorna')}
                  >
                    Aggiorna dati del progetto esistente
                  </button>
                  <button
                    className="fapi-btn subtle-danger"
                    onClick={() => creaProgetto({ duplicato: true })}
                  >
                    Crea comunque un nuovo progetto
                  </button>
                </>
              )}
            </>
          )}
          {step === 'confirming' && (
            <button className="fapi-btn primary" disabled>
              ⏳ Operazione in corso…
            </button>
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

function AmmissioneFondimpresaModal({ projectId, onClose, onSuccess }) {
  // UX-6: stessa regola della convenzione FAPI (vedi useDocumentoProgetto).
  const {
    associa, step, preview, error, campiScelti, handleFile, handleConfirm, toggleCampo,
  } = useDocumentoProgetto({
    projectId,
    upload: uploadAmmissioneFondimpresa,
    uploadProgetto: uploadAmmissioneFondimpresaProgetto,
    conferma: confirmAmmissioneFondimpresa,
    confermaProgetto: confirmAmmissioneFondimpresaProgetto,
  });

  return (
    <div className="fapi-modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="fapi-modal">
        <h3>
          {associa
            ? '📄 Allega lettera di ammissione al progetto'
            : '📄 Carica Lettera Ammissione Fondimpresa'}
        </h3>
        {associa && <NotaAssociazione />}
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
            {associa && (
              <DiffProgetto
                diff={preview.diff}
                campiScelti={campiScelti}
                onToggle={toggleCampo}
              />
            )}
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
            {associa ? (
              <EsitoAssociazione result={preview._result} />
            ) : (
              <>✅ Progetto Fondimpresa creato — ID: <strong>{preview._result.project_id}</strong></>
            )}
          </div>
        )}
        <div className="fapi-modal-footer">
          <button className="fapi-btn" onClick={onClose}>{step === 'done' ? 'Chiudi' : 'Annulla'}</button>
          {step === 'preview' && (
            <button className="fapi-btn primary" onClick={() => handleConfirm(onSuccess)}>
              {associa ? '✅ Allega al progetto' : '✅ Conferma e Crea Progetto'}
            </button>
          )}
          {step === 'confirming' && (
            <button className="fapi-btn primary" disabled>
              {associa ? '⏳ Associazione…' : '⏳ Creazione…'}
            </button>
          )}
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
  const [documentRefreshKey, setDocumentRefreshKey] = useState(0);

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
      {project && (
        <DocumentiProgetto
          projectId={project.id}
          refreshKey={documentRefreshKey}
        />
      )}

      {modal === 'new-piano' && (
        <NuovoPianoModal
          onChoose={(value) => setModal(value)}
          onClose={() => { setModal(null); onAutoClose && onAutoClose(); }}
        />
      )}
      {modal === 'convenzione' && (
        <ConvenzioneModal
          projectId={project?.id}
          onClose={() => { setModal(null); onAutoClose && onAutoClose(); }}
          // Il modale ha una schermata di esito che dichiara i campi applicati e
          // quelli lasciati invariati: chiuderlo qui la rendeva irraggiungibile.
          // La chiusura resta un gesto dell'operatore, dopo aver letto l'esito.
          onSuccess={() => {
            setDocumentRefreshKey(value => value + 1);
            onRefresh && onRefresh();
          }}
        />
      )}
      {modal === 'ammissione-fondimpresa' && (
        <AmmissioneFondimpresaModal
          projectId={project?.id}
          onClose={() => { setModal(null); onAutoClose && onAutoClose(); }}
          onSuccess={() => { onRefresh && onRefresh(); }}
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
