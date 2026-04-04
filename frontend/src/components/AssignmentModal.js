/**
 * COMPONENTE MODAL PER GESTIRE LE ASSEGNAZIONI DETTAGLIATE
 *
 * Questo componente permette di:
 * - Creare nuove assegnazioni con dettagli completi
 * - Modificare assegnazioni esistenti
 * - Specificare mansione, ore, date, costo orario
 */

import React, { useState, useEffect } from 'react';
import {
  createAssignment,
  updateAssignment,
  deleteAssignment,
  getPianiFinanziari,
  getPianoFinanziario
} from '../services/apiService';
import ErrorBanner from './ErrorBanner';
import './AssignmentModal.css';

const PIANO_ROLE_TEMPLATES = [
  { voce_codice: 'A.1', descrizione: 'Progettazione esecutiva' },
  { voce_codice: 'A.2', descrizione: 'Rilevazione fabbisogni' },
  { voce_codice: 'A.3', descrizione: 'Promozione' },
  { voce_codice: 'A.4', descrizione: 'Monitoraggio e valutazione' },
  { voce_codice: 'A.5', descrizione: 'Diffusione' },
  { voce_codice: 'A.6', descrizione: 'Viaggi e trasferte' },
  { voce_codice: 'A.7', descrizione: 'Altro' },
  { voce_codice: 'B.1', descrizione: 'Coordinamento' },
  { voce_codice: 'B.2', descrizione: 'Docenza' },
  { voce_codice: 'B.3', descrizione: 'Tutor' },
  { voce_codice: 'B.4', descrizione: 'Materiali didattici' },
  { voce_codice: 'B.5', descrizione: 'Materiali di consumo' },
  { voce_codice: 'B.6', descrizione: 'Aule didattiche' },
  { voce_codice: 'B.7', descrizione: 'Attrezzature' },
  { voce_codice: 'B.8', descrizione: 'Certificazione delle competenze' },
  { voce_codice: 'B.9', descrizione: 'Viaggi e trasferte' },
  { voce_codice: 'B.10', descrizione: 'Altro' },
  { voce_codice: 'C.1', descrizione: 'Designer' },
  { voce_codice: 'C.2', descrizione: 'Personale amministrativo' },
  { voce_codice: 'C.3', descrizione: 'Rendicontazione' },
  { voce_codice: 'C.4', descrizione: 'Revisione dei conti' },
  { voce_codice: 'C.5', descrizione: 'Fidejussione' },
  { voce_codice: 'C.6', descrizione: 'Costi generali e amministrativi (forfait)' },
  { voce_codice: 'C.7', descrizione: 'Viaggi e trasferte' },
  { voce_codice: 'C.8', descrizione: 'Altro' },
  { voce_codice: 'D.1', descrizione: 'Retribuzione ed oneri del personale' },
  { voce_codice: 'D.2', descrizione: 'Assicurazioni' },
  { voce_codice: 'D.3', descrizione: 'Rimborsi viaggi e trasferte' },
  { voce_codice: 'D.4', descrizione: 'Altro' },
];

const buildPlanRoleOptions = (voci = []) => {
  const byCode = voci.reduce((accumulator, voce) => {
    const key = voce.voce_codice;
    accumulator[key] = accumulator[key] || [];
    accumulator[key].push(voce);
    return accumulator;
  }, {});

  const options = [];

  PIANO_ROLE_TEMPLATES.forEach((template) => {
    const rows = byCode[template.voce_codice] || [];

    if (rows.length === 0) {
      options.push({
        id: `template-${template.voce_codice}`,
        mansione: `${template.voce_codice} – ${template.descrizione}`,
        tariffa_oraria: null,
        tipo_contratto: null,
        data_inizio: null,
        data_fine: null,
      });
      return;
    }

    rows.forEach((voce, index) => {
      const suffix = [voce.progetto_label, voce.edizione_label].filter(Boolean).join(' · ');
      options.push({
        id: voce.id || `${template.voce_codice}-${index}`,
        mansione: suffix
          ? `${template.voce_codice} – ${voce.descrizione} · ${suffix}`
          : `${template.voce_codice} – ${voce.descrizione}`,
        tariffa_oraria: (Number(voce.ore) > 0 && Number(voce.importo_preventivo) > 0)
          ? Math.round((Number(voce.importo_preventivo) / Number(voce.ore)) * 100) / 100
          : null,
        tipo_contratto: null,
        data_inizio: null,
        data_fine: null,
      });
    });
  });

  return options;
};

const extractVoceCodice = (role = '') => {
  const normalizedRole = String(role || '').trim();
  const match = normalizedRole.match(/^([A-D]\.\d+)/i);
  return match ? match[1].toUpperCase() : '';
};

const inferVoceCodice = (role = '') => {
  const explicitCode = extractVoceCodice(role);
  if (explicitCode) {
    return explicitCode;
  }
  const normalized = String(role || '').toLowerCase();
  if (normalized.includes('docen')) {
    return 'B.2';
  }
  if (normalized.includes('tutor')) {
    return 'B.3';
  }
  return '';
};

const AssignmentModal = ({
  isOpen,
  onClose,
  onSuccess,
  collaborator,
  project,
  assignment = null, // Se presente, siamo in modalità modifica
  availableProjects = [],
  availableCollaborators = []
}) => {
  const [formData, setFormData] = useState({
    collaborator_id: '',
    project_id: '',
    role: '',
    edizione_label: '',
    assigned_hours: '',
    start_date: '',
    end_date: '',
    contract_signed_date: '',
    hourly_rate: '',
    contract_type: ''
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [planRoles, setPlanRoles] = useState([]);
  const [loadingPlanRoles, setLoadingPlanRoles] = useState(false);
  const selectablePlanRoles = formData.role && !planRoles.some((item) => item.mansione === formData.role)
    ? [{ id: `legacy-${formData.role}`, mansione: formData.role, tipo_contratto: formData.contract_type, tariffa_oraria: formData.hourly_rate }, ...planRoles]
    : planRoles;

  // Lista dei tipi di contratto
  const contractTypeOptions = [
    { value: 'professionale', label: '💼 Professionale' },
    { value: 'occasionale', label: '📝 Occasionale' },
    { value: 'ordine_servizio', label: '📋 Ordine di servizio' },
    { value: 'contratto_progetto', label: '📄 Contratto a progetto' }
  ];

  // Inizializza il form quando si apre il modal
  useEffect(() => {
    if (isOpen) {
      if (assignment) {
        // Modalità modifica - carica i dati esistenti
        setFormData({
          collaborator_id: assignment.collaborator_id,
          project_id: assignment.project_id,
          role: assignment.role,
          edizione_label: assignment.edizione_label || '',
          assigned_hours: assignment.assigned_hours,
          start_date: assignment.start_date ? assignment.start_date.split('T')[0] : '',
          end_date: assignment.end_date ? assignment.end_date.split('T')[0] : '',
          contract_signed_date: assignment.contract_signed_date ? assignment.contract_signed_date.split('T')[0] : '',
          hourly_rate: assignment.hourly_rate,
          contract_type: assignment.contract_type || ''
        });
      } else {
        // Modalità creazione - pre-compila i dati se disponibili
        setFormData({
          collaborator_id: collaborator?.id || '',
          project_id: project?.id || '',
          role: '',
          edizione_label: '',
          assigned_hours: '',
          start_date: '',
          end_date: '',
          contract_signed_date: '',
          hourly_rate: '',
          contract_type: ''
        });
      }
      setError(null);
    }
  }, [isOpen, assignment, collaborator, project]);

  useEffect(() => {
    const projectId = formData.project_id || project?.id;
    if (!isOpen || !projectId) {
      setPlanRoles([]);
      return;
    }

    let cancelled = false;

    const loadPlanRoles = async () => {
      try {
        setLoadingPlanRoles(true);

        // 1. Ottieni i piani finanziari del progetto
        const piani = await getPianiFinanziari({ progetto_id: projectId, limit: 20 });
        if (cancelled) return;

        if (!Array.isArray(piani) || piani.length === 0) {
          setPlanRoles([]);
          return;
        }

        // 2. Carica il primo piano con le sue voci
        const piano = await getPianoFinanziario(piani[0].id);
        if (cancelled) return;

        if (!piano || !Array.isArray(piano.voci)) {
          setPlanRoles([]);
          return;
        }

        setPlanRoles(buildPlanRoleOptions(piano.voci));
      } catch (err) {
        if (!cancelled) {
          setPlanRoles([]);
        }
      } finally {
        if (!cancelled) {
          setLoadingPlanRoles(false);
        }
      }
    };

    loadPlanRoles();

    return () => {
      cancelled = true;
    };
  }, [isOpen, formData.project_id, project]);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => {
      const next = {
        ...prev,
        [name]: value
      };

      if (name === 'project_id') {
        next.role = '';
        next.edizione_label = '';
        next.hourly_rate = '';
        next.contract_type = '';
        next.start_date = '';
        next.end_date = '';
      }

      if (name === 'role') {
        const selectedPlanRole = planRoles.find((item) => item.mansione === value);
        if (!['B.2', 'B.3'].includes(inferVoceCodice(value))) {
          next.edizione_label = '';
        }
        if (selectedPlanRole) {
          next.hourly_rate = selectedPlanRole.tariffa_oraria || next.hourly_rate;
          next.contract_type = selectedPlanRole.tipo_contratto || next.contract_type;
          next.start_date = selectedPlanRole.data_inizio ? selectedPlanRole.data_inizio.split('T')[0] : next.start_date;
          next.end_date = selectedPlanRole.data_fine ? selectedPlanRole.data_fine.split('T')[0] : next.end_date;
        }
      }

      return next;
    });
    setError(null);
  };

  const validateForm = () => {
    const errors = [];
    const selectedVoceCodice = inferVoceCodice(formData.role);

    if (!formData.collaborator_id) errors.push('Seleziona un collaboratore');
    if (!formData.project_id) errors.push('Seleziona un progetto');
    if (!formData.role) errors.push('Seleziona una mansione');
    if (!formData.assigned_hours || formData.assigned_hours <= 0) {
      errors.push('Inserisci un numero di ore valido');
    }
    if (!formData.start_date) errors.push('Inserisci la data di inizio');
    if (!formData.end_date) errors.push('Inserisci la data di fine');
    if (!formData.hourly_rate || formData.hourly_rate <= 0) {
      errors.push('Inserisci un costo orario valido');
    }
    if (['B.2', 'B.3'].includes(selectedVoceCodice) && !formData.edizione_label.trim()) {
      errors.push('Per Docenza e Tutor indica l\'edizione');
    }

    // Valida le date
    if (formData.start_date && formData.end_date) {
      const startDate = new Date(formData.start_date);
      const endDate = new Date(formData.end_date);
      if (endDate <= startDate) {
        errors.push('La data di fine deve essere successiva alla data di inizio');
      }
    }

    return errors;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    const errors = validateForm();
    if (errors.length > 0) {
      setError(errors.join(', '));
      return;
    }

    try {
      setLoading(true);
      setError(null);

      // Prepara i dati per l'invio
      const assignmentData = {
        collaborator_id: parseInt(formData.collaborator_id),
        project_id: parseInt(formData.project_id),
        role: formData.role,
        edizione_label: formData.edizione_label.trim() || null,
        assigned_hours: parseFloat(formData.assigned_hours),
        start_date: new Date(formData.start_date).toISOString(),  // Formato ISO datetime
        end_date: new Date(formData.end_date).toISOString(),      // Formato ISO datetime
        contract_signed_date: formData.contract_signed_date
          ? new Date(formData.contract_signed_date).toISOString()
          : null,
        hourly_rate: parseFloat(formData.hourly_rate),
        contract_type: formData.contract_type || null
      };

      console.log('Invio dati assegnazione:', assignmentData);

      if (assignment) {
        // Modalità modifica
        await updateAssignment(assignment.id, assignmentData);
        onSuccess('Assegnazione aggiornata con successo!');
      } else {
        // Modalità creazione
        await createAssignment(assignmentData);
        onSuccess('Assegnazione creata con successo!');
      }

      onClose();

    } catch (err) {
      console.error('Errore salvataggio assegnazione:', err);
      console.error('Response data:', err.response?.data);
      if (err.response?.status === 400 || err.response?.status === 422) {
        const detail = err.response.data?.detail;
        if (Array.isArray(detail)) {
          setError(detail.map(e => `${e.loc?.join('.')}: ${e.msg}`).join(', '));
        } else {
          setError(detail || 'Errore nei dati inseriti');
        }
      } else {
        setError('Errore nel salvataggio. Riprova.');
      }
    } finally {
      setLoading(false);
    }
  };

  const selectedVoceCodice = inferVoceCodice(formData.role);
  const requiresEdition = ['B.2', 'B.3'].includes(selectedVoceCodice);

  const handleDelete = async () => {
    if (!assignment || !window.confirm('Sei sicuro di voler eliminare questa assegnazione?')) {
      return;
    }

    try {
      setLoading(true);
      await deleteAssignment(assignment.id);
      onSuccess('Assegnazione eliminata con successo!');
      onClose();
    } catch (err) {
      console.error('Errore eliminazione:', err);
      setError('Errore nell\'eliminazione. Riprova.');
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="assignment-modal">
        <div className="modal-header">
          <h2>
            {assignment ? '✏️ Modifica Assegnazione' : '➕ Nuova Assegnazione'}
          </h2>
          <button onClick={onClose} className="close-button">✕</button>
        </div>

        <form onSubmit={handleSubmit} className="assignment-form">
          {/* Sezione Collaboratore e Progetto */}
          <div className="form-section">
            <h3>📋 Collaboratore e Progetto</h3>
            <div className="form-grid">
              <div className="form-group">
                <label htmlFor="collaborator_id">Collaboratore *</label>
                <select
                  id="collaborator_id"
                  name="collaborator_id"
                  value={formData.collaborator_id}
                  onChange={handleInputChange}
                  disabled={!!collaborator} // Disabilita se il collaboratore è pre-selezionato
                  required
                >
                  <option value="">Seleziona collaboratore...</option>
                  {availableCollaborators.map(collab => (
                    <option key={collab.id} value={collab.id}>
                      {collab.first_name} {collab.last_name} - {collab.email}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label htmlFor="project_id">Progetto *</label>
                <select
                  id="project_id"
                  name="project_id"
                  value={formData.project_id}
                  onChange={handleInputChange}
                  disabled={!!project} // Disabilita se il progetto è pre-selezionato
                  required
                >
                  <option value="">Seleziona progetto...</option>
                  {availableProjects.map(proj => (
                    <option key={proj.id} value={proj.id}>
                      {proj.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          {/* Sezione Mansione */}
          <div className="form-section">
            <h3>👔 Mansione</h3>
            <div className="form-grid">
              <div className="form-group">
                <label htmlFor="role">Voce Piano / Mansione *</label>
                <select
                  id="role"
                  name="role"
                  value={formData.role}
                  onChange={handleInputChange}
                  required
                >
                  <option value="">
                    {loadingPlanRoles ? 'Caricamento voci piano...' : 'Seleziona una voce del piano finanziario...'}
                  </option>
                  {selectablePlanRoles.map(option => (
                    <option key={option.id} value={option.mansione}>
                      {option.mansione}{option.tipo_contratto ? ` · ${option.tipo_contratto}` : ''}{option.tariffa_oraria ? ` · €${option.tariffa_oraria}/h` : ''}
                    </option>
                  ))}
                </select>
                {formData.project_id && !loadingPlanRoles && planRoles.length === 0 ? (
                  <small style={{color:'var(--color-warning)'}}>Nessun piano finanziario trovato per questo progetto. Crea prima il piano in "Piani Finanziari".</small>
                ) : (
                  <small>Le voci vengono dal piano finanziario del progetto.</small>
                )}
              </div>

              <div className="form-group">
                <label htmlFor="contract_type">Tipo di Contratto</label>
                <select
                  id="contract_type"
                  name="contract_type"
                  value={formData.contract_type}
                  onChange={handleInputChange}
                >
                  <option value="">Seleziona tipo contratto...</option>
                  {contractTypeOptions.map(option => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>

              {requiresEdition && (
                <div className="form-group">
                  <label htmlFor="edizione_label">Edizione *</label>
                  <input
                    type="text"
                    id="edizione_label"
                    name="edizione_label"
                    value={formData.edizione_label}
                    onChange={handleInputChange}
                    placeholder="Es. Edizione 1 / Aula Napoli / 2026-01"
                    required
                  />
                  <small>L'edizione viene riportata sul piano finanziario per Docenza e Tutor.</small>
                </div>
              )}
            </div>
          </div>

          {/* Sezione Ore e Costi */}
          <div className="form-section">
            <h3>💰 Ore e Costi</h3>
            <div className="form-grid">
              <div className="form-group">
                <label htmlFor="assigned_hours">Ore Assegnate *</label>
                <input
                  type="number"
                  id="assigned_hours"
                  name="assigned_hours"
                  value={formData.assigned_hours}
                  onChange={handleInputChange}
                  placeholder="Es: 40"
                  min="0"
                  step="0.5"
                  required
                />
                <small>Numero totale di ore per questa mansione</small>
              </div>

              <div className="form-group">
                <label htmlFor="hourly_rate">Costo Orario (€) *</label>
                <input
                  type="number"
                  id="hourly_rate"
                  name="hourly_rate"
                  value={formData.hourly_rate}
                  onChange={handleInputChange}
                  placeholder="Es: 25.50"
                  min="0"
                  step="0.01"
                  required
                />
                <small>Importo in euro per ogni ora di lavoro</small>
              </div>
            </div>

            {/* Calcolo totale */}
            {formData.assigned_hours && formData.hourly_rate && (
              <div className="cost-summary">
                <div className="total-cost">
                  <strong>
                    💶 Costo Totale: €{(parseFloat(formData.assigned_hours) * parseFloat(formData.hourly_rate)).toFixed(2)}
                  </strong>
                </div>
              </div>
            )}

            {/* Riepilogo Ore (solo in modalità modifica) */}
            {assignment && (
              <div className="hours-summary">
                <h4>📊 Riepilogo Ore</h4>
                <div className="hours-grid">
                  <div className="hours-item">
                    <span className="hours-label">Ore Assegnate:</span>
                    <span className="hours-value">{assignment.assigned_hours}h</span>
                  </div>
                  <div className="hours-item">
                    <span className="hours-label">Ore Completate:</span>
                    <span className="hours-value hours-completed">{assignment.completed_hours || 0}h</span>
                  </div>
                  <div className="hours-item">
                    <span className="hours-label">Ore Rimanenti:</span>
                    <span className="hours-value hours-remaining">
                      {Math.max(0, assignment.assigned_hours - (assignment.completed_hours || 0))}h
                    </span>
                  </div>
                  <div className="hours-item">
                    <span className="hours-label">Progresso:</span>
                    <span className="hours-value">
                      {assignment.progress_percentage ? assignment.progress_percentage.toFixed(1) : 0}%
                    </span>
                  </div>
                </div>
                <div className="progress-bar-container">
                  <div
                    className="progress-bar"
                    style={{width: `${Math.min(100, assignment.progress_percentage || 0)}%`}}
                  ></div>
                </div>
              </div>
            )}
          </div>

          {/* Sezione Date */}
          <div className="form-section">
            <h3>📅 Periodo di Attività</h3>
            <div className="form-grid">
              <div className="form-group">
                <label htmlFor="start_date">Data Inizio *</label>
                <input
                  type="date"
                  id="start_date"
                  name="start_date"
                  value={formData.start_date}
                  onChange={handleInputChange}
                  required
                />
              </div>

              <div className="form-group">
                <label htmlFor="end_date">Data Fine *</label>
                <input
                  type="date"
                  id="end_date"
                  name="end_date"
                  value={formData.end_date}
                  onChange={handleInputChange}
                  required
                />
              </div>

              <div className="form-group">
                <label htmlFor="contract_signed_date">Data Firma Contratto</label>
                <input
                  type="date"
                  id="contract_signed_date"
                  name="contract_signed_date"
                  value={formData.contract_signed_date}
                  onChange={handleInputChange}
                />
                <small>Campo opzionale. Lascialo vuoto se non disponibile.</small>
              </div>
            </div>

            {/* Calcolo durata */}
            {formData.start_date && formData.end_date && (
              <div className="duration-info">
                <small>
                  📊 Durata: {Math.ceil((new Date(formData.end_date) - new Date(formData.start_date)) / (1000 * 60 * 60 * 24))} giorni
                </small>
              </div>
            )}
          </div>

          {/* Messaggi di errore */}
          {error && (
            <div className="error-message">
              ⚠️ <ErrorBanner error={error} />
            </div>
          )}

          {/* Pulsanti */}
          <div className="modal-buttons">
            <button
              type="button"
              onClick={onClose}
              className="cancel-button"
              disabled={loading}
            >
              Annulla
            </button>

            {assignment && (
              <button
                type="button"
                onClick={handleDelete}
                className="delete-button"
                disabled={loading}
              >
                🗑️ Elimina
              </button>
            )}

            <button
              type="submit"
              className="submit-button"
              disabled={loading}
            >
              {loading ? '⏳ Salvando...' : (assignment ? '✏️ Aggiorna' : '➕ Crea')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default AssignmentModal;
