/**
 * WIZARD CREAZIONE PIANO FINANZIARIO DA TEMPLATE (FASE E1 — Task E1.4/E1.5)
 *
 * Tre passi:
 *  1. SELEZIONE  — fondo (obbligatorio) + anno + avviso (opzionale, filtrato
 *                  per fondo) + scelta del template; il template collegato
 *                  all'avviso è evidenziato ("Consigliato dall'avviso") e
 *                  preselezionato. L'anno vive qui perché determina i
 *                  massimali mostrati in anteprima (I1).
 *  2. ANTEPRIMA  — voci del template + massimali per l'anno scelto, con fonte
 *                  esplicita: "Regola avviso (art. X)" vs "Massimale fondo generico".
 *  3. CONFERMA   — testata (progetto, nome, budget) →
 *                  POST /api/v1/piani-finanziari/from-template → piano creato
 *                  mostrato con le sue voci.
 *
 * Il percorso libero di creazione piano (upload/POST esistenti) resta invariato.
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  createPianoFinanziarioFromTemplate,
  getAvvisi,
  getPianoTemplateAnteprima,
  getPianoTemplates,
} from '../services/apiService';
import { canRequest } from '../auth/permissions';
import ErrorBanner from './ErrorBanner';
import './PianoTemplateWizard.css';

// Stessi valori ammessi dal validator backend PianoFinanziario.tipo_fondo.
const TIPI_FONDO = [
  { value: 'fapi', label: 'FAPI' },
  { value: 'fondimpresa', label: 'Fondimpresa' },
  { value: 'formazienda', label: 'Formazienda' },
  { value: 'fonamcom', label: 'Fon.Am.Com.' },
  { value: 'fse', label: 'FSE' },
  { value: 'regionale', label: 'Regionale' },
  { value: 'altro', label: 'Altro' },
];

const STEP_LABELS = {
  1: 'Selezione',
  2: 'Anteprima',
  3: 'Conferma',
};

const formatEuro = (value) => {
  if (value == null) return '—';
  return new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR' }).format(value);
};

const extractApiError = (err, fallback) => {
  const detail = err?.response?.data?.detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => `${item.loc?.join('.')}: ${item.msg}`).join(', ');
  }
  return detail || fallback;
};

const CLOSE_CONFIRM_MESSAGE = 'Chiudere il wizard? Le selezioni andranno perse.';

const PianoTemplateWizard = ({ project = null, availableProjects = [], onClose, onSuccess }) => {
  const [step, setStep] = useState(1);

  // Passo 1 — selezione
  const [fondo, setFondo] = useState('');
  const [avvisi, setAvvisi] = useState([]);
  const [avvisoId, setAvvisoId] = useState('');
  const [avvisiLoadFailed, setAvvisiLoadFailed] = useState(false);
  const [avvisiFetchTick, setAvvisiFetchTick] = useState(0);
  const [templates, setTemplates] = useState([]);
  const [templateId, setTemplateId] = useState('');
  const [loadingTemplates, setLoadingTemplates] = useState(false);
  const fondoSelectRef = useRef(null);

  // Passo 2 — anteprima
  const [anteprima, setAnteprima] = useState(null);
  const [anteprimaAnno, setAnteprimaAnno] = useState(null);
  const [loadingAnteprima, setLoadingAnteprima] = useState(false);

  // Passo 3 — conferma
  const [formData, setFormData] = useState({
    progetto_id: project?.id ? String(project.id) : '',
    nome: '',
    anno: String(new Date().getFullYear()),
    budget_totale: '',
  });
  const [saving, setSaving] = useState(false);
  const [pianoCreato, setPianoCreato] = useState(null);

  const [error, setError] = useState(null);

  // Avvisi caricati una volta e filtrati per fondo lato client
  // (GET /avvisi/ non espone un filtro fondo server-side).
  // avvisiFetchTick permette il retry esplicito in caso di errore (I3).
  useEffect(() => {
    let cancelled = false;
    setAvvisiLoadFailed(false);
    getAvvisi({ active_only: true, limit: 1000 })
      .then((data) => { if (!cancelled) setAvvisi(Array.isArray(data) ? data : []); })
      .catch(() => {
        if (!cancelled) {
          setAvvisi([]);
          setAvvisiLoadFailed(true);
        }
      });
    return () => { cancelled = true; };
  }, [avvisiFetchTick]);

  // A11y (I5): focus iniziale sulla select del fondo al mount.
  useEffect(() => {
    fondoSelectRef.current?.focus();
  }, []);

  // Chiusura protetta (I2/I5): libera al passo 1 o a piano creato,
  // conferma esplicita dai passi 2-3 (le selezioni andrebbero perse).
  const requestClose = useCallback(() => {
    if (pianoCreato || step === 1) {
      onClose();
      return;
    }
    if (window.confirm(CLOSE_CONFIRM_MESSAGE)) onClose();
  }, [pianoCreato, step, onClose]);

  // A11y (I5): Escape → stessa logica di chiusura del bottone ✕.
  useEffect(() => {
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') requestClose();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [requestClose]);

  const avvisiDelFondo = useMemo(
    () => avvisi.filter((avviso) => avviso.fondo === fondo),
    [avvisi, fondo],
  );

  // Template pertinenti al fondo (+ preselezione dal backend quando c'è avviso)
  useEffect(() => {
    if (!fondo) {
      setTemplates([]);
      setTemplateId('');
      return undefined;
    }

    let cancelled = false;
    const params = { tipo_fondo: fondo };
    if (avvisoId) params.avviso_id = Number(avvisoId);

    setLoadingTemplates(true);
    getPianoTemplates(params)
      .then((data) => {
        if (cancelled) return;
        const items = Array.isArray(data) ? data : [];
        setTemplates(items);
        const consigliato = items.find((item) => item.preselezionato);
        setTemplateId((prev) => {
          if (consigliato) return String(consigliato.id);
          return items.some((item) => String(item.id) === prev) ? prev : '';
        });
      })
      .catch((err) => {
        if (!cancelled) {
          setTemplates([]);
          setError(extractApiError(err, 'Errore nel caricamento dei template.'));
        }
      })
      .finally(() => { if (!cancelled) setLoadingTemplates(false); });

    return () => { cancelled = true; };
  }, [fondo, avvisoId]);

  const selectedTemplate = templates.find((item) => String(item.id) === String(templateId)) || null;

  const annoValido = useMemo(() => {
    const anno = Number(formData.anno);
    return Number.isFinite(anno) && anno >= 2000 && anno <= 2100;
  }, [formData.anno]);

  // I1: l'anno è scelto al passo 1 e ogni ingresso al passo 2 dal passo 1
  // ricalcola l'anteprima con l'anno corrente (anteprimaAnno traccia
  // l'anno effettivamente usato, mostrato nell'intestazione dei massimali).
  const loadAnteprima = async () => {
    try {
      setLoadingAnteprima(true);
      setError(null);
      const annoRichiesto = Number(formData.anno) || new Date().getFullYear();
      const params = { anno: annoRichiesto };
      if (avvisoId) params.avviso_id = Number(avvisoId);
      const data = await getPianoTemplateAnteprima(Number(templateId), params);
      setAnteprima(data);
      setAnteprimaAnno(annoRichiesto);
      setStep(2);
    } catch (err) {
      setError(extractApiError(err, 'Errore nel caricamento dell\'anteprima.'));
    } finally {
      setLoadingAnteprima(false);
    }
  };

  // M6: al passaggio 2→3, se il nome è vuoto lo precompiliamo
  // con "Piano {template} {anno}" (resta modificabile).
  const goToConferma = () => {
    setFormData((prev) => {
      if (prev.nome.trim()) return prev;
      const nomeTemplate = selectedTemplate?.nome || anteprima?.template?.nome || '';
      return { ...prev, nome: `Piano ${nomeTemplate} ${prev.anno}`.replace(/\s+/g, ' ').trim() };
    });
    setStep(3);
  };

  const handleFormChange = (event) => {
    const { name, value } = event.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    setError(null);
  };

  const handleSubmit = async (event) => {
    event.preventDefault();

    const errors = [];
    if (!formData.progetto_id) errors.push('Seleziona un progetto');
    if (!formData.nome.trim()) errors.push('Inserisci il nome del piano');
    const anno = Number(formData.anno);
    if (!anno || anno < 2000 || anno > 2100) errors.push('Inserisci un anno valido (2000-2100)');
    if (errors.length > 0) {
      setError(errors.join(', '));
      return;
    }

    const payload = {
      template_id: Number(templateId),
      progetto_id: Number(formData.progetto_id),
      anno,
      nome: formData.nome.trim(),
    };
    if (avvisoId) payload.avviso_id = Number(avvisoId);
    if (formData.budget_totale !== '') payload.budget_totale = Number(formData.budget_totale);

    try {
      setSaving(true);
      setError(null);
      const piano = await createPianoFinanziarioFromTemplate(payload);
      setPianoCreato(piano);
      if (onSuccess) onSuccess(piano);
    } catch (err) {
      setError(extractApiError(err, 'Errore nella creazione del piano. Riprova.'));
    } finally {
      setSaving(false);
    }
  };

  const renderStepIndicator = () => (
    <div className="ptw-steps">
      <span className="ptw-step-counter">Passo {step} di 3</span>
      <span className="ptw-step-label">{STEP_LABELS[step]}</span>
    </div>
  );

  const renderSelezione = () => (
    <div className="ptw-body">
      <div className="ptw-form-group">
        <label htmlFor="ptw-fondo">Fondo *</label>
        <select
          id="ptw-fondo"
          ref={fondoSelectRef}
          value={fondo}
          onChange={(event) => {
            setFondo(event.target.value);
            setAvvisoId('');
            setError(null);
          }}
          required
        >
          <option value="">Seleziona fondo...</option>
          {TIPI_FONDO.map((item) => (
            <option key={item.value} value={item.value}>{item.label}</option>
          ))}
        </select>
      </div>

      <div className="ptw-form-group">
        <label htmlFor="ptw-anno">Anno *</label>
        <input
          id="ptw-anno"
          name="anno"
          type="number"
          min="2000"
          max="2100"
          value={formData.anno}
          onChange={handleFormChange}
          required
        />
        <small>L'anno determina i massimali applicati nell'anteprima e nel piano.</small>
      </div>

      {fondo && (
        <div className="ptw-form-group">
          <label htmlFor="ptw-avviso">Avviso (opzionale)</label>
          <select
            id="ptw-avviso"
            value={avvisoId}
            onChange={(event) => { setAvvisoId(event.target.value); setError(null); }}
          >
            <option value="">Nessun avviso</option>
            {avvisiDelFondo.map((avviso) => (
              <option key={avviso.id} value={avviso.id}>
                {avviso.codice} — {avviso.titolo || avviso.descrizione || 'Senza titolo'}
              </option>
            ))}
          </select>
          {avvisiLoadFailed ? (
            <p className="ptw-avvisi-error" role="alert">
              Impossibile caricare gli avvisi. Riprova.
              <button
                type="button"
                className="ptw-btn-link"
                onClick={() => setAvvisiFetchTick((tick) => tick + 1)}
              >
                Riprova
              </button>
            </p>
          ) : (
            <small>Con un avviso selezionato i massimali usano le regole validate dell'avviso.</small>
          )}
        </div>
      )}

      {fondo && (
        <div className="ptw-template-list">
          <h4>Template disponibili</h4>
          {loadingTemplates ? (
            <p className="ptw-muted">Caricamento template...</p>
          ) : templates.length === 0 ? (
            <p className="ptw-muted">Nessun template attivo per questo fondo.</p>
          ) : (
            templates.map((template) => (
              <label
                key={template.id}
                className={`ptw-template-card ${String(template.id) === String(templateId) ? 'selected' : ''} ${template.preselezionato ? 'consigliato' : ''}`}
              >
                <input
                  type="radio"
                  name="ptw-template"
                  value={template.id}
                  checked={String(template.id) === String(templateId)}
                  onChange={() => { setTemplateId(String(template.id)); setError(null); }}
                  aria-label={template.nome}
                />
                <span className="ptw-template-info">
                  <strong>{template.nome}</strong>
                  <span className="ptw-muted">
                    v{template.versione}{template.descrizione ? ` · ${template.descrizione}` : ''}
                  </span>
                </span>
                {template.preselezionato && (
                  <span className="ptw-badge ptw-badge-consigliato">Consigliato dall'avviso</span>
                )}
              </label>
            ))
          )}
          {!loadingTemplates && templates.length > 0 && !templateId && (
            <p className="ptw-hint">Seleziona un template per proseguire</p>
          )}
        </div>
      )}
    </div>
  );

  const renderAnteprima = () => (
    <div className="ptw-body">
      <h4>{anteprima?.template?.nome}</h4>
      {(anteprima?.voci || []).length === 0 ? (
        <p className="ptw-muted">Il template non contiene voci.</p>
      ) : (
        <table className="ptw-table">
          <thead>
            <tr>
              <th>Voce</th>
              <th>Categoria</th>
              <th>Descrizione</th>
              <th>Macrovoce</th>
            </tr>
          </thead>
          <tbody>
            {(anteprima?.voci || []).map((voce) => (
              <tr key={voce.voce_codice}>
                <td>{voce.voce_codice}</td>
                <td>{voce.categoria || '—'}</td>
                <td>{voce.descrizione}</td>
                <td>{voce.macrovoce}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h4>Massimali applicati (anno {anteprimaAnno})</h4>
      {(anteprima?.massimali || []).length === 0 ? (
        <p className="ptw-muted">Nessun massimale configurato per fondo/avviso selezionati.</p>
      ) : (
        <ul className="ptw-massimali">
          {(anteprima?.massimali || []).map((massimale) => (
            <li key={massimale.categoria}>
              <strong>{massimale.categoria}</strong>: {formatEuro(massimale.limite)}/h
              <span
                data-testid="badge-fonte-massimale"
                className={`ptw-badge ${massimale.fonte === 'regola_avviso' ? 'ptw-badge-regola' : 'ptw-badge-fondo'}`}
              >
                {massimale.fonte === 'regola_avviso'
                  ? `Regola avviso${massimale.riferimento_articolo ? ` (${massimale.riferimento_articolo})` : ''}`
                  : 'Massimale fondo generico'}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );

  const renderConferma = () => (
    <form className="ptw-body" onSubmit={handleSubmit}>
      <div className="ptw-form-group">
        <label htmlFor="ptw-progetto">Progetto *</label>
        <select
          id="ptw-progetto"
          name="progetto_id"
          value={formData.progetto_id}
          onChange={handleFormChange}
          disabled={Boolean(project)}
          required
        >
          <option value="">Seleziona progetto...</option>
          {(project ? [project] : availableProjects).map((item) => (
            <option key={item.id} value={item.id}>{item.name}</option>
          ))}
        </select>
      </div>

      <div className="ptw-form-group">
        <label htmlFor="ptw-nome">Nome del piano *</label>
        <input
          id="ptw-nome"
          name="nome"
          type="text"
          maxLength={200}
          value={formData.nome}
          onChange={handleFormChange}
          placeholder={selectedTemplate ? `Piano ${selectedTemplate.nome}` : 'Nome del piano'}
          required
        />
      </div>

      <p className="ptw-muted">
        Anno del piano: <strong>{formData.anno}</strong> (impostato al passo 1).
      </p>

      <div className="ptw-form-group">
        <label htmlFor="ptw-budget">Budget totale (€)</label>
        <input
          id="ptw-budget"
          name="budget_totale"
          type="number"
          min="0"
          step="0.01"
          value={formData.budget_totale}
          onChange={handleFormChange}
          placeholder="Opzionale"
        />
      </div>

      <div className="ptw-footer">
        <button type="button" className="ptw-btn" onClick={() => setStep(2)} disabled={saving}>
          ← Indietro
        </button>
        <button type="submit" className="ptw-btn primary" disabled={saving}>
          {saving ? '⏳ Creazione...' : '✅ Crea piano'}
        </button>
      </div>
    </form>
  );

  const renderPianoCreato = () => {
    // I4: nome progetto risolto dalla lista disponibile (il backend
    // restituisce solo l'id); fallback sull'id se non risolvibile.
    const progettoId = pianoCreato.progetto_id ?? formData.progetto_id;
    const progettoDelPiano = (project ? [project] : availableProjects)
      .find((item) => String(item.id) === String(progettoId));
    const nomeProgetto = progettoDelPiano?.name || `#${progettoId}`;
    const annoPiano = pianoCreato.anno ?? formData.anno;

    return (
      <div className="ptw-body">
        <p className="ptw-success">
          ✅ Il piano «{pianoCreato.nome}» per l'anno {annoPiano} è stato creato
          nel progetto «{nomeProgetto}».
        </p>
        <p className="ptw-muted">
          Al momento non è consultabile da questa interfaccia: resta disponibile
          per la rendicontazione e l'export.
        </p>
        <p className="ptw-muted">Codice interno: {pianoCreato.id}</p>
        <h4>Voci del piano</h4>
      <table className="ptw-table">
        <thead>
          <tr>
            <th>Voce</th>
            <th>Categoria</th>
            <th>Descrizione</th>
            <th>Macrovoce</th>
          </tr>
        </thead>
        <tbody>
          {(pianoCreato.voci || []).map((voce) => (
            <tr key={voce.id || voce.voce_codice}>
              <td>{voce.voce_codice}</td>
              <td>{voce.categoria || '—'}</td>
              <td>{voce.descrizione}</td>
              <td>{voce.macrovoce}</td>
            </tr>
          ))}
        </tbody>
      </table>
        <div className="ptw-footer">
          <button type="button" className="ptw-btn primary" onClick={onClose}>Chiudi</button>
        </div>
      </div>
    );
  };

  return (
    <div
      className="modal-overlay"
      onClick={(event) => {
        // I2: click sull'overlay chiude solo quando non c'è nulla da perdere
        // (passo 1 o piano già creato); dai passi 2-3 restano ✕ e Annulla.
        if (event.target === event.currentTarget && (pianoCreato || step === 1)) onClose();
      }}
    >
      <div className="ptw-modal" role="dialog" aria-modal="true" aria-labelledby="ptw-title">
        <div className="ptw-header">
          <h2 id="ptw-title">🧩 Nuovo piano da template</h2>
          <button type="button" onClick={requestClose} className="ptw-close" aria-label="Chiudi wizard">✕</button>
        </div>

        {!pianoCreato && renderStepIndicator()}

        {error && (
          <div className="ptw-error" role="alert">⚠️ <ErrorBanner error={error} /></div>
        )}

        {pianoCreato
          ? renderPianoCreato()
          : step === 1
            ? renderSelezione()
            : step === 2
              ? renderAnteprima()
              : renderConferma()}

        {!pianoCreato && step !== 3 && (
          <div className="ptw-footer">
            {step === 2 ? (
              <button type="button" className="ptw-btn" onClick={() => setStep(1)}>← Indietro</button>
            ) : (
              <button type="button" className="ptw-btn" onClick={onClose}>Annulla</button>
            )}
            {step === 1 && (
              <button
                type="button"
                className="ptw-btn primary"
                onClick={loadAnteprima}
                disabled={!fondo || !templateId || !annoValido || loadingAnteprima}
              >
                {loadingAnteprima ? '⏳ Caricamento...' : 'Avanti →'}
              </button>
            )}
            {step === 2 && (
              <button type="button" className="ptw-btn primary" onClick={goToConferma}>
                Avanti →
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

/**
 * Bottone di aggancio UI: visibile solo ai ruoli che possono creare piani
 * da template (matrice RBAC reale: POST /api/v1/piani-finanziari/from-template
 * = admin + operatore; consultazione non lo vede).
 */
export const PianoTemplateWizardButton = ({
  currentUser,
  project = null,
  availableProjects = [],
  onCreated,
}) => {
  const [open, setOpen] = useState(false);

  if (!canRequest(currentUser, 'POST', '/api/v1/piani-finanziari/from-template')) {
    return null;
  }

  return (
    <>
      <button type="button" className="ptw-open-button" onClick={() => setOpen(true)}>
        🧩 Nuovo piano da template
      </button>
      {open && (
        <PianoTemplateWizard
          project={project}
          availableProjects={availableProjects}
          onClose={() => setOpen(false)}
          onSuccess={onCreated}
        />
      )}
    </>
  );
};

export default PianoTemplateWizard;
