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
  deleteAssignment
} from '../services/apiService';
import ErrorBanner from './ErrorBanner';
import './AssignmentModal.css';

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
    assigned_hours: '',
    start_date: '',
    end_date: '',
    hourly_rate: '',
    contract_type: ''
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Lista delle mansioni disponibili
  const roleOptions = [
    { value: 'docente', label: '👨‍🏫 Docente' },
    { value: 'tutor', label: '🤝 Tutor' },
    { value: 'progettista', label: '📐 Progettista' },
    { value: 'coordinatore', label: '🎯 Coordinatore' },
    { value: 'esperto', label: '🔬 Esperto' },
    { value: 'assistente', label: '🙋‍♂️ Assistente' }
  ];

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
          assigned_hours: assignment.assigned_hours,
          start_date: assignment.start_date ? assignment.start_date.split('T')[0] : '',
          end_date: assignment.end_date ? assignment.end_date.split('T')[0] : '',
          hourly_rate: assignment.hourly_rate,
          contract_type: assignment.contract_type || ''
        });
      } else {
        // Modalità creazione - pre-compila i dati se disponibili
        setFormData({
          collaborator_id: collaborator?.id || '',
          project_id: project?.id || '',
          role: '',
          assigned_hours: '',
          start_date: '',
          end_date: '',
          hourly_rate: '',
          contract_type: ''
        });
      }
      setError(null);
    }
  }, [isOpen, assignment, collaborator, project]);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
    setError(null);
  };

  const validateForm = () => {
    const errors = [];

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
        assigned_hours: parseFloat(formData.assigned_hours),
        start_date: new Date(formData.start_date).toISOString(),  // Formato ISO datetime
        end_date: new Date(formData.end_date).toISOString(),      // Formato ISO datetime
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
                <label htmlFor="role">Tipo di Mansione *</label>
                <select
                  id="role"
                  name="role"
                  value={formData.role}
                  onChange={handleInputChange}
                  required
                >
                  <option value="">Seleziona mansione...</option>
                  {roleOptions.map(option => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
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