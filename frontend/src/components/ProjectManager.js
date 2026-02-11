/**
 * COMPONENTE GESTIONE PROGETTI COMPLETO
 *
 * Questa interfaccia permette di:
 * - Aggiungere nuovi progetti formativi tramite form
 * - Visualizzare lista completa progetti
 * - Modificare progetti esistenti
 * - Eliminare progetti
 * - Gestire stati e date dei progetti
 */

import React, { useState, useMemo } from 'react';
import { useProjects, useImplementingEntities, useNotifications } from '../hooks/useEntity';
import './ProjectManager.css';

const ProjectManager = () => {
  // ==========================================
  // CONTEXT E HOOKS
  // ==========================================

  // Carica dati dal Context
  const { data: projects, loading: loadingProjects, error: contextError, refresh, create, update, remove } = useProjects();
  const { data: allEntities, loading: loadingEntities } = useImplementingEntities();
  const { showSuccess, showError } = useNotifications();

  // Filtra solo enti attivi per il dropdown
  const implementingEntities = useMemo(() =>
    allEntities.filter(e => e.is_active),
    [allEntities]
  );

  // Dati del form per nuovo/modifica progetto
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    start_date: '',
    end_date: '',
    status: 'active',
    cup: '',
    ente_erogatore: '', // DEPRECATO: mantenuto per retrocompatibilità
    ente_attuatore_id: null // NUOVO: FK verso ente attuatore
  });

  // Stati locali dell'interfaccia
  const [editingId, setEditingId] = useState(null); // ID del progetto in modifica
  const [showForm, setShowForm] = useState(false);  // Mostra/nascondi form
  const [deleteConfirm, setDeleteConfirm] = useState(null); // Stato per conferma eliminazione
  const [statusFilter, setStatusFilter] = useState('all'); // Filtri per la visualizzazione

  // Combina stati di loading
  const loading = loadingProjects || loadingEntities;

  // ==========================================
  // GESTIONE FORM
  // ==========================================

  /**
   * GESTISCE I CAMBIAMENTI NEI CAMPI DEL FORM
   */
  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  /**
   * VALIDA I DATI DEL FORM
   */
  const validateForm = () => {
    const errors = [];

    if (!formData.name.trim()) {
      errors.push('Il nome del progetto è obbligatorio');
    }

    if (!formData.description.trim()) {
      errors.push('La descrizione è obbligatoria');
    }

    // Validazione date
    if (formData.start_date && formData.end_date) {
      const startDate = new Date(formData.start_date);
      const endDate = new Date(formData.end_date);

      if (endDate <= startDate) {
        errors.push('La data di fine deve essere successiva alla data di inizio');
      }
    }

    return errors;
  };

  /**
   * GESTISCE L'INVIO DEL FORM
   */
  const handleSubmit = async (e) => {
    e.preventDefault();

    // Validazione
    const errors = validateForm();
    if (errors.length > 0) {
      showError(errors.join(', '));
      return;
    }

    try {
      // Prepara i dati (converte date vuote in null e formatta quelle presenti)
      const projectData = {
        ...formData,
        start_date: formData.start_date ? `${formData.start_date}T00:00:00Z` : null,
        end_date: formData.end_date ? `${formData.end_date}T23:59:59Z` : null
      };

      if (editingId) {
        // MODALITÀ MODIFICA
        await update(editingId, projectData);
        showSuccess('Progetto aggiornato con successo!');
      } else {
        // MODALITÀ CREAZIONE
        await create(projectData);
        showSuccess('Progetto aggiunto con successo!');
      }

      // Ricarica i dati e reimposta il form
      await refresh();
      resetForm();

    } catch (err) {
      console.error('Errore salvataggio:', err);
      showError('Errore nel salvataggio. Riprova.');
    }
  };

  /**
   * REIMPOSTA IL FORM
   */
  const resetForm = () => {
    setFormData({
      name: '',
      description: '',
      start_date: '',
      end_date: '',
      status: 'active',
      cup: '',
      ente_erogatore: '',
      ente_attuatore_id: null
    });
    setEditingId(null);
    setShowForm(false);
  };

  // ==========================================
  // AZIONI SUI PROGETTI
  // ==========================================

  /**
   * AVVIA MODIFICA PROGETTO
   */
  const startEdit = (project) => {
    setFormData({
      name: project.name,
      description: project.description || '',
      start_date: project.start_date ? project.start_date.split('T')[0] : '',
      end_date: project.end_date ? project.end_date.split('T')[0] : '',
      status: project.status,
      cup: project.cup || '',
      ente_erogatore: project.ente_erogatore || '',
      ente_attuatore_id: project.ente_attuatore_id || null
    });
    setEditingId(project.id);
    setShowForm(true);
  };

  /**
   * ELIMINA PROGETTO
   */
  const handleDelete = async (projectId) => {
    try {
      await remove(projectId);
      showSuccess('Progetto eliminato con successo!');
      await refresh();
      setDeleteConfirm(null);
    } catch (err) {
      console.error('Errore eliminazione:', err);
      showError('Errore nell\'eliminazione. Riprova.');
    }
  };

  // ==========================================
  // FUNZIONI DI UTILITÀ
  // ==========================================

  /**
   * OTTIENI COLORE PER STATO PROGETTO
   */
  const getStatusColor = (status) => {
    switch (status) {
      case 'active': return '#28a745';
      case 'completed': return '#17a2b8';
      case 'paused': return '#ffc107';
      case 'cancelled': return '#dc3545';
      default: return '#6c757d';
    }
  };

  /**
   * OTTIENI ETICHETTA PER STATO
   */
  const getStatusLabel = (status) => {
    switch (status) {
      case 'active': return '🟢 Attivo';
      case 'completed': return '✅ Completato';
      case 'paused': return '⏸️ In Pausa';
      case 'cancelled': return '❌ Annullato';
      default: return '❓ Sconosciuto';
    }
  };

  /**
   * FILTRA PROGETTI PER STATO
   */
  const filteredProjects = projects.filter(project => {
    if (statusFilter === 'all') return true;
    return project.status === statusFilter;
  });

  // ==========================================
  // RENDER DEL COMPONENTE
  // ==========================================

  if (loading && projects.length === 0) {
    return (
      <div className="project-manager">
        <div className="loading">
          <div className="spinner"></div>
          <p>Caricamento progetti...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="project-manager">
      {/* INTESTAZIONE */}
      <div className="manager-header">
        <h1>📁 Gestione Progetti</h1>
        <p>Crea e gestisci i progetti formativi della tua organizzazione</p>

        <button
          className={`add-button ${showForm ? 'active' : ''}`}
          onClick={() => {
            setShowForm(!showForm);
            if (showForm) resetForm();
          }}
        >
          {showForm ? '❌ Chiudi Form' : '➕ Nuovo Progetto'}
        </button>
      </div>

      {/* MESSAGGI DI STATO */}
      {contextError && (
        <div className="message error-message">
          ⚠️ {contextError.message || 'Errore nel caricamento dei progetti'}
        </div>
      )}

      {/* FORM AGGIUNTA/MODIFICA */}
      {showForm && (
        <div className="form-section">
          <h2>{editingId ? '✏️ Modifica Progetto' : '➕ Nuovo Progetto'}</h2>

          <form onSubmit={handleSubmit} className="project-form">
            <div className="form-grid">
              {/* Nome Progetto */}
              <div className="form-group">
                <label htmlFor="name">Nome Progetto *</label>
                <input
                  type="text"
                  id="name"
                  name="name"
                  value={formData.name}
                  onChange={handleInputChange}
                  placeholder="Es: Corso React Avanzato"
                  required
                />
              </div>

              {/* Stato */}
              <div className="form-group">
                <label htmlFor="status">Stato Progetto</label>
                <select
                  id="status"
                  name="status"
                  value={formData.status}
                  onChange={handleInputChange}
                >
                  <option value="active">🟢 Attivo</option>
                  <option value="paused">⏸️ In Pausa</option>
                  <option value="completed">✅ Completato</option>
                  <option value="cancelled">❌ Annullato</option>
                </select>
              </div>

              {/* Data Inizio */}
              <div className="form-group">
                <label htmlFor="start_date">Data Inizio</label>
                <input
                  type="date"
                  id="start_date"
                  name="start_date"
                  value={formData.start_date}
                  onChange={handleInputChange}
                />
              </div>

              {/* Data Fine */}
              <div className="form-group">
                <label htmlFor="end_date">Data Fine</label>
                <input
                  type="date"
                  id="end_date"
                  name="end_date"
                  value={formData.end_date}
                  onChange={handleInputChange}
                />
              </div>

              {/* CUP */}
              <div className="form-group">
                <label htmlFor="cup">Codice CUP</label>
                <input
                  type="text"
                  id="cup"
                  name="cup"
                  value={formData.cup}
                  onChange={handleInputChange}
                  placeholder="Es: C12D20001234567"
                  maxLength="15"
                />
              </div>

              {/* Ente Attuatore */}
              <div className="form-group">
                <label htmlFor="ente_attuatore_id">Ente Attuatore</label>
                <select
                  id="ente_attuatore_id"
                  name="ente_attuatore_id"
                  value={formData.ente_attuatore_id || ''}
                  onChange={handleInputChange}
                >
                  <option value="">Seleziona Ente Attuatore</option>
                  {implementingEntities.map(entity => (
                    <option key={entity.id} value={entity.id}>
                      {entity.ragione_sociale} - {entity.citta}
                    </option>
                  ))}
                </select>
                <small className="field-hint">
                  Seleziona l'ente che attua il progetto (es: piemmei, Next Group, Wonder)
                </small>
              </div>

              {/* Ente Erogatore (deprecato ma mantenuto) */}
              <div className="form-group">
                <label htmlFor="ente_erogatore">Ente Erogatore (opzionale)</label>
                <select
                  id="ente_erogatore"
                  name="ente_erogatore"
                  value={formData.ente_erogatore}
                  onChange={handleInputChange}
                >
                  <option value="">Seleziona Ente Erogatore</option>
                  <option value="FAPI">FAPI</option>
                  <option value="FONDIMPRESA">FONDIMPRESA</option>
                  <option value="FORMAZIENDA">FORMAZIENDA</option>
                  <option value="REGIONE CAMPANIA">REGIONE CAMPANIA</option>
                  <option value="REGIONE LOMBARDIA">REGIONE LOMBARDIA</option>
                  <option value="MIMIT">MIMIT</option>
                </select>
                <small className="field-hint">
                  Ente che finanzia il progetto (campo legacy)
                </small>
              </div>

              {/* Descrizione */}
              <div className="form-group full-width">
                <label htmlFor="description">Descrizione *</label>
                <textarea
                  id="description"
                  name="description"
                  value={formData.description}
                  onChange={handleInputChange}
                  placeholder="Descrivi gli obiettivi e i contenuti del progetto formativo..."
                  rows="4"
                  required
                />
              </div>
            </div>

            {/* Pulsanti Form */}
            <div className="form-buttons">
              <button
                type="button"
                onClick={resetForm}
                className="cancel-button"
              >
                Annulla
              </button>
              <button
                type="submit"
                className="submit-button"
                disabled={loading}
              >
                {loading ? '⏳ Salvando...' : (editingId ? '✏️ Aggiorna' : '➕ Crea Progetto')}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* FILTRI */}
      <div className="filters-section">
        <h2>🔍 Filtra per Stato</h2>
        <div className="filter-buttons">
          <button
            className={`filter-button ${statusFilter === 'all' ? 'active' : ''}`}
            onClick={() => setStatusFilter('all')}
          >
            📋 Tutti ({projects.length})
          </button>
          <button
            className={`filter-button ${statusFilter === 'active' ? 'active' : ''}`}
            onClick={() => setStatusFilter('active')}
          >
            🟢 Attivi ({projects.filter(p => p.status === 'active').length})
          </button>
          <button
            className={`filter-button ${statusFilter === 'completed' ? 'active' : ''}`}
            onClick={() => setStatusFilter('completed')}
          >
            ✅ Completati ({projects.filter(p => p.status === 'completed').length})
          </button>
          <button
            className={`filter-button ${statusFilter === 'paused' ? 'active' : ''}`}
            onClick={() => setStatusFilter('paused')}
          >
            ⏸️ In Pausa ({projects.filter(p => p.status === 'paused').length})
          </button>
        </div>
      </div>

      {/* LISTA PROGETTI */}
      <div className="projects-list">
        <h2>📋 Progetti ({filteredProjects.length})</h2>

        {filteredProjects.length === 0 ? (
          <div className="empty-state">
            <p>📁 Nessun progetto trovato</p>
            <p>
              {statusFilter === 'all'
                ? 'Usa il pulsante "Nuovo Progetto" per crearne uno!'
                : `Nessun progetto con stato "${getStatusLabel(statusFilter).split(' ')[1]}"`
              }
            </p>
          </div>
        ) : (
          <div className="projects-grid">
            {filteredProjects.map(project => (
              <div key={project.id} className="project-card">
                {/* Header Card */}
                <div className="card-header">
                  <div className="project-title">
                    <h3>{project.name}</h3>
                    <span
                      className="status-badge"
                      style={{ backgroundColor: getStatusColor(project.status) }}
                    >
                      {getStatusLabel(project.status)}
                    </span>
                  </div>
                  <div className="card-actions">
                    <button
                      onClick={() => startEdit(project)}
                      className="edit-button"
                      title="Modifica progetto"
                    >
                      ✏️
                    </button>
                    <button
                      onClick={() => setDeleteConfirm(project.id)}
                      className="delete-button"
                      title="Elimina progetto"
                    >
                      🗑️
                    </button>
                  </div>
                </div>

                {/* Descrizione */}
                <div className="project-description">
                  <p>{project.description}</p>
                </div>

                {/* Info Progetto */}
                <div className="project-info">
                  {project.start_date && (
                    <div className="info-row">
                      <span className="label">📅 Inizio:</span>
                      <span>{new Date(project.start_date).toLocaleDateString('it-IT')}</span>
                    </div>
                  )}

                  {project.end_date && (
                    <div className="info-row">
                      <span className="label">🏁 Fine:</span>
                      <span>{new Date(project.end_date).toLocaleDateString('it-IT')}</span>
                    </div>
                  )}

                  {project.cup && (
                    <div className="info-row">
                      <span className="label">🏷️ CUP:</span>
                      <span>{project.cup}</span>
                    </div>
                  )}

                  {project.ente_erogatore && (
                    <div className="info-row">
                      <span className="label">🏛️ Ente:</span>
                      <span>{project.ente_erogatore}</span>
                    </div>
                  )}

                  <div className="info-row">
                    <span className="label">🗓️ Creato:</span>
                    <span>{new Date(project.created_at).toLocaleDateString('it-IT')}</span>
                  </div>
                </div>

                {/* Footer con statistiche */}
                <div className="project-stats">
                  <div className="stat">
                    <span className="stat-number">ID: {project.id}</span>
                    <span className="stat-label">Codice Progetto</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* MODAL CONFERMA ELIMINAZIONE */}
      {deleteConfirm && (
        <div className="modal-overlay">
          <div className="confirm-modal">
            <h3>⚠️ Conferma Eliminazione</h3>
            <p>Sei sicuro di voler eliminare questo progetto?</p>
            <p><strong>Verranno eliminate anche tutte le presenze associate!</strong></p>
            <p>Questa azione non può essere annullata.</p>

            <div className="modal-buttons">
              <button
                onClick={() => setDeleteConfirm(null)}
                className="cancel-button"
              >
                Annulla
              </button>
              <button
                onClick={() => handleDelete(deleteConfirm)}
                className="delete-button"
              >
                🗑️ Elimina
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ProjectManager;