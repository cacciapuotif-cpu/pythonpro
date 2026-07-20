/**
 * WIZARD CREAZIONE PIANO FINANZIARIO DA TEMPLATE (FASE E1 — Task E1.4/E1.5)
 *
 * Tre passi:
 *  1. SELEZIONE  — fondo (obbligatorio) + avviso (opzionale, filtrato per fondo)
 *                  + scelta del template; il template collegato all'avviso è
 *                  evidenziato ("Consigliato dall'avviso") e preselezionato.
 *  2. ANTEPRIMA  — voci del template + massimali con fonte esplicita:
 *                  "Regola avviso (art. X)" vs "Massimale fondo generico".
 *  3. CONFERMA   — testata (progetto, nome, anno, budget) →
 *                  POST /api/v1/piani-finanziari/from-template → piano creato
 *                  mostrato con le sue voci.
 *
 * Il percorso libero di creazione piano (upload/POST esistenti) resta invariato.
 */

import React, { useEffect, useMemo, useState } from 'react';
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

const PianoTemplateWizard = ({ project = null, availableProjects = [], onClose, onSuccess }) => {
  const [step, setStep] = useState(1);

  // Passo 1 — selezione
  const [fondo, setFondo] = useState('');
  const [avvisi, setAvvisi] = useState([]);
  const [avvisoId, setAvvisoId] = useState('');
  const [templates, setTemplates] = useState([]);
  const [templateId, setTemplateId] = useState('');
  const [loadingTemplates, setLoadingTemplates] = useState(false);

  // Passo 2 — anteprima
  const [anteprima, setAnteprima] = useState(null);
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
  useEffect(() => {
    let cancelled = false;
    getAvvisi({ active_only: true, limit: 1000 })
      .then((data) => { if (!cancelled) setAvvisi(Array.isArray(data) ? data : []); })
      .catch(() => { if (!cancelled) setAvvisi([]); });
    return () => { cancelled = true; };
  }, []);

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

  const loadAnteprima = async () => {
    try {
      setLoadingAnteprima(true);
      setError(null);
      const params = { anno: Number(formData.anno) || new Date().getFullYear() };
      if (avvisoId) params.avviso_id = Number(avvisoId);
      const data = await getPianoTemplateAnteprima(Number(templateId), params);
      setAnteprima(data);
      setStep(2);
    } catch (err) {
      setError(extractApiError(err, 'Errore nel caricamento dell\'anteprima.'));
    } finally {
      setLoadingAnteprima(false);
    }
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
          <small>Con un avviso selezionato i massimali usano le regole validate dell'avviso.</small>
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
        </div>
      )}
    </div>
  );

  const renderAnteprima = () => (
    <div className="ptw-body">
      <h4>{anteprima?.template?.nome}</h4>
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

      <h4>Massimali applicati</h4>
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
      </div>

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

  const renderPianoCreato = () => (
    <div className="ptw-body">
      <p className="ptw-success">
        ✅ Piano creato — ID: <strong>{pianoCreato.id}</strong> · {pianoCreato.nome}
      </p>
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

  return (
    <div className="modal-overlay" onClick={(event) => event.target === event.currentTarget && onClose()}>
      <div className="ptw-modal">
        <div className="ptw-header">
          <h2>🧩 Nuovo piano da template</h2>
          <button type="button" onClick={onClose} className="ptw-close" aria-label="Chiudi wizard">✕</button>
        </div>

        {!pianoCreato && renderStepIndicator()}

        {error && (
          <div className="ptw-error">⚠️ <ErrorBanner error={error} /></div>
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
                disabled={!fondo || !templateId || loadingAnteprima}
              >
                {loadingAnteprima ? '⏳ Caricamento...' : 'Avanti →'}
              </button>
            )}
            {step === 2 && (
              <button type="button" className="ptw-btn primary" onClick={() => setStep(3)}>
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
