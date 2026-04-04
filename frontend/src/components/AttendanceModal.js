/**
 * COMPONENTE MODAL PER GESTIRE LE PRESENZE
 *
 * Questo modal si apre quando:
 * 1. L'utente clicca su uno slot vuoto del calendario (nuova presenza)
 * 2. L'utente clicca su una presenza esistente (modifica presenza)
 *
 * Permette di:
 * - Selezionare collaboratore e progetto
 * - Impostare data, ora inizio e ora fine
 * - Calcolare automaticamente le ore totali
 * - Aggiungere note opzionali
 * - Salvare o eliminare la presenza
 */

import React, { useState, useEffect } from 'react';
import Modal from 'react-modal';
import moment from 'moment';
import { createAttendance, updateAttendance, getAssignments } from '../services/apiService';
import './AttendanceModal.css';

// CONFIGURAZIONE DEL MODAL
// Impostiamo l'elemento root per l'accessibilità
Modal.setAppElement('#root');

/**
 * COMPONENTE PRINCIPALE DEL MODAL
 */
const AttendanceModal = ({
  isOpen,           // Se il modal è aperto o chiuso
  onClose,          // Funzione per chiudere il modal
  onSave,           // Funzione chiamata dopo aver salvato
  onDelete,         // Funzione chiamata dopo aver eliminato
  attendance,       // Presenza esistente (null per nuova presenza)
  selectedSlot,     // Slot selezionato per nuova presenza
  collaborators,    // Lista di tutti i collaboratori
  projects         // Lista di tutti i progetti
}) => {
  // ==========================================
  // STATE MANAGEMENT - Dati del form
  // ==========================================

  const [formData, setFormData] = useState({
    collaborator_id: '',
    project_id: '',
    assignment_id: '',
    date: '',
    start_time: '',
    end_time: '',
    hours: 0,
    notes: ''
  });

  // Stati per la gestione dell'interfaccia
  const [loading, setLoading] = useState(false);   // Mostra spinner durante salvataggio
  const [errors, setErrors] = useState({});        // Errori di validazione
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);  // Conferma eliminazione
  const [assignments, setAssignments] = useState([]);  // Lista mansioni disponibili
  const [filteredAssignments, setFilteredAssignments] = useState([]);  // Mansioni filtrate

  // ==========================================
  // INIZIALIZZAZIONE DEI DATI
  // ==========================================

  /**
   * EFFETTO CHE SI ESEGUE QUANDO SI APRE IL MODAL
   * Inizializza il form con i dati esistenti o con quelli dello slot selezionato
   */
  useEffect(() => {
    if (isOpen) {
      // Carica le assignments
      loadAssignments();

      if (attendance) {
        // MODALITÀ MODIFICA - Popoliamo il form con i dati esistenti
        setFormData({
          collaborator_id: attendance.collaborator_id,
          project_id: attendance.project_id,
          assignment_id: attendance.assignment_id || '',
          date: moment(attendance.date).format('YYYY-MM-DD'),
          start_time: moment(attendance.start_time).format('HH:mm'),
          end_time: moment(attendance.end_time).format('HH:mm'),
          hours: attendance.hours,
          notes: attendance.notes || ''
        });
      } else if (selectedSlot) {
        // MODALITÀ CREAZIONE - Popoliamo con i dati dello slot selezionato
        const startTime = moment(selectedSlot.start);
        const endTime = moment(selectedSlot.end);

        // Calcola le ore dalla differenza tra start e end
        let startTimeFormatted = startTime.format('HH:mm');
        let endTimeFormatted = endTime.format('HH:mm');
        let calculatedHours = calculateHours(startTimeFormatted, endTimeFormatted);

        // Se le ore sono 0 (click su giorno intero nella vista settimana/mese),
        // impostiamo orari di default (9:00-17:00)
        if (calculatedHours === 0 || startTimeFormatted === '00:00') {
          startTimeFormatted = '09:00';
          endTimeFormatted = '17:00';
          calculatedHours = 8;
        }

        setFormData({
          collaborator_id: '',
          project_id: '',
          assignment_id: '',
          date: startTime.format('YYYY-MM-DD'),
          start_time: startTimeFormatted,
          end_time: endTimeFormatted,
          hours: calculatedHours,
          notes: ''
        });
      } else {
        // MODALITÀ CREAZIONE SENZA SLOT - Impostiamo valori di default
        const now = moment();
        setFormData({
          collaborator_id: '',
          project_id: '',
          assignment_id: '',
          date: now.format('YYYY-MM-DD'),
          start_time: '09:00',  // Default 9:00
          end_time: '17:00',    // Default 17:00
          hours: 8,
          notes: ''
        });
      }

      // Resettiamo gli errori
      setErrors({});
      setShowDeleteConfirm(false);
    }
  }, [isOpen, attendance, selectedSlot]);

  // ==========================================
  // CARICAMENTO DATI
  // ==========================================

  /**
   * CARICA TUTTE LE ASSIGNMENTS DAL SERVER
   */
  const loadAssignments = async () => {
    try {
      const data = await getAssignments();
      setAssignments(data);
    } catch (error) {
      console.error('Errore nel caricamento delle assignments:', error);
    }
  };

  /**
   * FILTRA LE ASSIGNMENTS IN BASE AL COLLABORATORE E PROGETTO SELEZIONATI
   */
  useEffect(() => {
    if (formData.collaborator_id && formData.project_id) {
      const filtered = assignments.filter(
        (assignment) =>
          assignment.collaborator_id === parseInt(formData.collaborator_id) &&
          assignment.project_id === parseInt(formData.project_id) &&
          assignment.is_active
      );
      setFilteredAssignments(filtered);
    } else {
      setFilteredAssignments([]);
    }
  }, [formData.collaborator_id, formData.project_id, assignments]);

  // ==========================================
  // FUNZIONI DI UTILITÀ
  // ==========================================

  /**
   * CALCOLA LE ORE TOTALI TRA DUE ORARI
   * @param {string} startTime - Orario inizio (formato HH:mm)
   * @param {string} endTime - Orario fine (formato HH:mm)
   * @returns {number} Ore totali (con decimali)
   */
  const calculateHours = (startTime, endTime) => {
    if (!startTime || !endTime) return 0;

    const start = moment(startTime, 'HH:mm');
    const end = moment(endTime, 'HH:mm');

    // Se l'ora di fine è prima dell'inizio, assumiamo sia il giorno dopo
    if (end.isBefore(start)) {
      end.add(1, 'day');
    }

    const duration = moment.duration(end.diff(start));
    return Math.round(duration.asHours() * 100) / 100;  // Arrotonda a 2 decimali
  };

  // ==========================================
  // GESTORI EVENTI DEL FORM
  // ==========================================

  /**
   * GESTISCE I CAMBIAMENTI NEGLI INPUT DEL FORM
   */
  const handleInputChange = (e) => {
    const { name, value } = e.target;

    setFormData(prev => ({
      ...prev,
      [name]: value
    }));

    // Se cambiano gli orari, ricalcola automaticamente le ore
    if (name === 'start_time' || name === 'end_time') {
      const newFormData = { ...formData, [name]: value };
      const calculatedHours = calculateHours(newFormData.start_time, newFormData.end_time);

      setFormData(prev => ({
        ...prev,
        [name]: value,
        hours: calculatedHours
      }));
    }

    // Rimuovi l'errore per questo campo se era presente
    if (errors[name]) {
      setErrors(prev => ({
        ...prev,
        [name]: null
      }));
    }
  };

  // ==========================================
  // VALIDAZIONE DEL FORM
  // ==========================================

  /**
   * VALIDA I DATI DEL FORM PRIMA DEL SALVATAGGIO
   * @returns {boolean} true se tutto è valido, false altrimenti
   */
  const validateForm = () => {
    const newErrors = {};

    // Validazione campi obbligatori
    if (!formData.collaborator_id) {
      newErrors.collaborator_id = 'Seleziona un collaboratore';
    }

    if (!formData.project_id) {
      newErrors.project_id = 'Seleziona un progetto';
    }

    // assignment_id è opzionale - la presenza può essere registrata anche senza mansione specifica
    // if (!formData.assignment_id) {
    //   newErrors.assignment_id = 'Seleziona una mansione';
    // }

    if (!formData.date) {
      newErrors.date = 'Inserisci la data';
    }

    if (!formData.start_time) {
      newErrors.start_time = 'Inserisci l\'ora di inizio';
    }

    if (!formData.end_time) {
      newErrors.end_time = 'Inserisci l\'ora di fine';
    }

    // Validazione logica degli orari
    if (formData.start_time && formData.end_time) {
      const start = moment(formData.start_time, 'HH:mm');
      const end = moment(formData.end_time, 'HH:mm');

      if (start.isAfter(end)) {
        newErrors.end_time = 'L\'ora di fine deve essere dopo l\'ora di inizio';
      }

      if (formData.hours <= 0) {
        newErrors.hours = 'Le ore devono essere maggiori di zero';
      }

      if (formData.hours > 24) {
        newErrors.hours = 'Le ore non possono superare le 24 in un giorno';
      }
    }

    // Validazione ore rimanenti dell'assegnazione
    if (formData.assignment_id && formData.hours) {
      const selectedAssignment = filteredAssignments.find(
        a => a.id === parseInt(formData.assignment_id)
      );

      if (selectedAssignment) {
        const oreCompletate = selectedAssignment.completed_hours || 0;
        const oreAssegnate = selectedAssignment.assigned_hours;

        // Se stiamo modificando, sottrai le ore già registrate
        const oreGiaRegistrate = attendance ? attendance.hours : 0;
        const oreRimanenti = oreAssegnate - oreCompletate + oreGiaRegistrate;

        if (formData.hours > oreRimanenti) {
          newErrors.hours = `Le ore inserite (${formData.hours}h) superano le ore rimanenti (${oreRimanenti}h) per questa mansione`;
        }
      }
    }

    // Validazione periodo di attività dell'assegnazione
    if (formData.date) {
      // Usa timestamp numerici per confronto sicuro (no dipendenze da metodi moment avanzati)
      const presenzaTs = new Date(formData.date + 'T00:00:00').getTime();

      const assignmentDaControllare = formData.assignment_id
        ? filteredAssignments.filter(a => a.id === parseInt(formData.assignment_id))
        : filteredAssignments;

      if (assignmentDaControllare.length > 0) {
        const dentroAlmenoUna = assignmentDaControllare.some(a => {
          if (!a.start_date || !a.end_date) return true;
          const s = new Date(a.start_date.split('T')[0] + 'T00:00:00').getTime();
          const e = new Date(a.end_date.split('T')[0] + 'T23:59:59').getTime();
          return presenzaTs >= s && presenzaTs <= e;
        });

        if (!dentroAlmenoUna) {
          const periodi = assignmentDaControllare
            .filter(a => a.start_date && a.end_date)
            .map(a => {
              const s = moment(a.start_date).format('DD/MM/YYYY');
              const e = moment(a.end_date).format('DD/MM/YYYY');
              return `${s} - ${e}`;
            })
            .join(', ');
          newErrors.date = `Data fuori dal periodo di attività${periodi ? ` (${periodi})` : ''}`;
        }
      }
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;  // true se non ci sono errori
  };

  // ==========================================
  // AZIONI DEL MODAL
  // ==========================================

  /**
   * GESTISCE IL SALVATAGGIO DELLA PRESENZA
   */
  const handleSave = async () => {
    // Valida il form
    if (!validateForm()) {
      return;  // Se ci sono errori, non salvare
    }

    setLoading(true);

    try {
      // Prepara i dati per l'API
      const attendanceData = {
        collaborator_id: parseInt(formData.collaborator_id),
        project_id: parseInt(formData.project_id),
        assignment_id: formData.assignment_id ? parseInt(formData.assignment_id) : null,
        date: `${formData.date}T00:00:00`,  // Formato datetime completo
        start_time: `${formData.date}T${formData.start_time}:00`,  // Combina data e ora in formato ISO
        end_time: `${formData.date}T${formData.end_time}:00`,
        hours: formData.hours,
        notes: formData.notes
      };

      if (attendance) {
        // MODALITÀ MODIFICA - Aggiorna presenza esistente
        await updateAttendance(attendance.id, attendanceData);
      } else {
        // MODALITÀ CREAZIONE - Crea nuova presenza
        await createAttendance(attendanceData);
      }

      // Chiama la funzione di callback per ricaricare i dati
      onSave(attendanceData);

    } catch (error) {
      console.error('Errore nel salvataggio:', error);
      console.error('Risposta completa errore:', error.response?.data);

      // Mostra errori specifici dall'API se disponibili
      if (error.response?.data?.details) {
        // Gestisci errori di validazione multipli
        const validationErrors = {};
        error.response.data.details.forEach(err => {
          // Estrai il nome del campo dall'errore (es. "body.date" -> "date")
          const fieldName = err.field.split('.').pop();
          validationErrors[fieldName] = err.message;
        });
        setErrors(validationErrors);
      } else if (error.response?.data?.error) {
        // Errore generale dal backend
        setErrors({ general: error.response.data.error });
      } else if (error.response?.data?.detail) {
        // Formato alternativo per dettagli errore
        setErrors({ general: error.response.data.detail });
      } else {
        setErrors({ general: 'Errore nel salvataggio. Riprova.' });
      }
    } finally {
      setLoading(false);
    }
  };

  /**
   * GESTISCE L'ELIMINAZIONE DELLA PRESENZA
   * Chiama il callback del parent che gestirà l'eliminazione e la chiusura del modal
   */
  const handleDelete = () => {
    if (!attendance) return;  // Non si può eliminare una presenza che non esiste

    // Chiama il callback del parent component che gestirà:
    // 1. L'eliminazione via API
    // 2. L'aggiornamento dei dati
    // 3. La chiusura del modal
    onDelete();
  };

  /**
   * CHIUDE IL MODAL E RESETTA TUTTO
   */
  const handleClose = () => {
    setFormData({
      collaborator_id: '',
      project_id: '',
      assignment_id: '',
      date: '',
      start_time: '',
      end_time: '',
      hours: 0,
      notes: ''
    });
    setErrors({});
    setShowDeleteConfirm(false);
    onClose();
  };

  // ==========================================
  // RENDER DEL COMPONENTE
  // ==========================================

  return (
    <Modal
      isOpen={isOpen}
      onRequestClose={handleClose}
      className="attendance-modal"
      overlayClassName="attendance-modal-overlay"
      shouldCloseOnOverlayClick={!loading}  // Non chiudere durante il caricamento
    >
      <div className="modal-content">
        {/* INTESTAZIONE DEL MODAL */}
        <div className="modal-header">
          <h2>
            {attendance ? 'Modifica Presenza' : 'Nuova Presenza'}
          </h2>
          <button
            className="close-button"
            onClick={handleClose}
            disabled={loading}
          >
            ✕
          </button>
        </div>

        {/* CORPO DEL MODAL CON IL FORM */}
        <div className="modal-body">
          {/* ERRORE GENERALE */}
          {errors.general && (
            <div className="error-message">
              {errors.general}
            </div>
          )}

          {/* FORM PRINCIPALE */}
          <div className="form-grid">
            {/* SELEZIONE COLLABORATORE */}
            <div className="form-group">
              <label htmlFor="collaborator_id">
                Collaboratore <span className="required">*</span>
              </label>
              <select
                id="collaborator_id"
                name="collaborator_id"
                value={formData.collaborator_id}
                onChange={handleInputChange}
                className={errors.collaborator_id ? 'error' : ''}
                disabled={loading}
              >
                <option value="">Seleziona collaboratore...</option>
                {[...collaborators].sort((a, b) => (a.last_name || '').localeCompare(b.last_name || '', 'it')).map(collaborator => (
                  <option key={collaborator.id} value={collaborator.id}>
                    {collaborator.last_name} {collaborator.first_name}
                  </option>
                ))}
              </select>
              {errors.collaborator_id && (
                <span className="field-error">{errors.collaborator_id}</span>
              )}
            </div>

            {/* SELEZIONE PROGETTO */}
            <div className="form-group">
              <label htmlFor="project_id">
                Progetto <span className="required">*</span>
              </label>
              <select
                id="project_id"
                name="project_id"
                value={formData.project_id}
                onChange={handleInputChange}
                className={errors.project_id ? 'error' : ''}
                disabled={loading}
              >
                <option value="">Seleziona progetto...</option>
                {projects.map(project => (
                  <option key={project.id} value={project.id}>
                    {project.name}
                  </option>
                ))}
              </select>
              {errors.project_id && (
                <span className="field-error">{errors.project_id}</span>
              )}
            </div>

            {/* SELEZIONE MANSIONE */}
            <div className="form-group">
              <label htmlFor="assignment_id">
                Mansione <span className="required">*</span>
              </label>
              <select
                id="assignment_id"
                name="assignment_id"
                value={formData.assignment_id}
                onChange={handleInputChange}
                className={errors.assignment_id ? 'error' : ''}
                disabled={loading || !formData.collaborator_id || !formData.project_id}
              >
                <option value="">Seleziona mansione...</option>
                {filteredAssignments.map(assignment => {
                  const oreAssegnate = assignment.assigned_hours;
                  const oreCompletate = assignment.completed_hours || 0;
                  const oreRimanenti = Math.max(0, oreAssegnate - oreCompletate);

                  return (
                    <option key={assignment.id} value={assignment.id}>
                      {assignment.role} - Assegnate: {oreAssegnate}h | Rimanenti: {oreRimanenti}h
                    </option>
                  );
                })}
              </select>
              {errors.assignment_id && (
                <span className="field-error">{errors.assignment_id}</span>
              )}
              <small className="field-help">
                {!formData.collaborator_id || !formData.project_id
                  ? 'Seleziona prima collaboratore e progetto per vedere le mansioni disponibili'
                  : filteredAssignments.length === 0
                  ? '⚠️ Nessuna mansione assegnata per questo collaboratore e progetto'
                  : 'Seleziona la mansione a cui associare queste ore'}
              </small>
            </div>

            {/* DATA */}
            <div className="form-group">
              <label htmlFor="date">
                Data <span className="required">*</span>
              </label>
              <input
                type="date"
                id="date"
                name="date"
                value={formData.date}
                onChange={handleInputChange}
                className={errors.date ? 'error' : ''}
                disabled={loading}
              />
              {errors.date && (
                <span className="field-error">{errors.date}</span>
              )}
            </div>

            {/* ORA INIZIO */}
            <div className="form-group">
              <label htmlFor="start_time">
                Ora Inizio <span className="required">*</span>
              </label>
              <input
                type="time"
                id="start_time"
                name="start_time"
                value={formData.start_time}
                onChange={handleInputChange}
                className={errors.start_time ? 'error' : ''}
                disabled={loading}
              />
              {errors.start_time && (
                <span className="field-error">{errors.start_time}</span>
              )}
            </div>

            {/* ORA FINE */}
            <div className="form-group">
              <label htmlFor="end_time">
                Ora Fine <span className="required">*</span>
              </label>
              <input
                type="time"
                id="end_time"
                name="end_time"
                value={formData.end_time}
                onChange={handleInputChange}
                className={errors.end_time ? 'error' : ''}
                disabled={loading}
              />
              {errors.end_time && (
                <span className="field-error">{errors.end_time}</span>
              )}
            </div>

            {/* ORE TOTALI (CALCOLATE AUTOMATICAMENTE) */}
            <div className="form-group">
              <label htmlFor="hours">Ore Totali</label>
              <input
                type="number"
                id="hours"
                name="hours"
                value={formData.hours}
                step="0.25"
                min="0"
                max="24"
                onChange={handleInputChange}
                className={errors.hours ? 'error' : ''}
                disabled={loading}
              />
              {errors.hours && (
                <span className="field-error">{errors.hours}</span>
              )}
              <small className="field-help">
                Le ore vengono calcolate automaticamente dagli orari
              </small>
            </div>
          </div>

          {/* NOTE (CAMPO PIÙ LARGO) */}
          <div className="form-group full-width">
            <label htmlFor="notes">Note</label>
            <textarea
              id="notes"
              name="notes"
              value={formData.notes}
              onChange={handleInputChange}
              placeholder="Note opzionali (cosa è stato fatto, problemi riscontrati, etc...)"
              rows="3"
              disabled={loading}
            />
          </div>
        </div>

        {/* FOOTER DEL MODAL CON I PULSANTI */}
        <div className="modal-footer">
          {/* PULSANTE ELIMINA (solo se stiamo modificando) */}
          {attendance && !showDeleteConfirm && (
            <button
              className="delete-button"
              onClick={() => setShowDeleteConfirm(true)}
              disabled={loading}
            >
              🗑️ Elimina
            </button>
          )}

          {/* CONFERMA ELIMINAZIONE */}
          {showDeleteConfirm && (
            <div className="delete-confirm">
              <span>Sei sicuro di voler eliminare questa presenza?</span>
              <button
                className="confirm-delete-button"
                onClick={handleDelete}
                disabled={loading}
              >
                Sì, Elimina
              </button>
              <button
                className="cancel-delete-button"
                onClick={() => setShowDeleteConfirm(false)}
                disabled={loading}
              >
                Annulla
              </button>
            </div>
          )}

          {/* PULSANTI PRINCIPALI */}
          {!showDeleteConfirm && (
            <div className="main-buttons">
              <button
                className="cancel-button"
                onClick={handleClose}
                disabled={loading}
              >
                Annulla
              </button>
              <button
                className="save-button"
                onClick={handleSave}
                disabled={loading}
              >
                {loading ? (
                  <>
                    <span className="spinner-small"></span>
                    {attendance ? 'Aggiornamento...' : 'Salvataggio...'}
                  </>
                ) : (
                  attendance ? 'Aggiorna' : 'Salva'
                )}
              </button>
            </div>
          )}
        </div>
      </div>
    </Modal>
  );
};

export default AttendanceModal;