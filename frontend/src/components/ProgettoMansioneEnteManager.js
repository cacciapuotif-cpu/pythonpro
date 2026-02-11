/**
 * COMPONENTE GESTIONE ASSOCIAZIONI PROGETTO-MANSIONE-ENTE
 *
 * Permette di collegare progetti con enti attuatori specificando:
 * - La mansione/ruolo da svolgere
 * - Il periodo di attività
 * - Le ore previste ed effettive
 * - La tariffa oraria e il budget
 * - Il tipo di contratto
 */

import React, { useState, useEffect } from 'react';
import ErrorBanner from './ErrorBanner';
import './ProgettoMansioneEnteManager.css';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8001';

const ProgettoMansioneEnteManager = () => {
  // ==========================================
  // STATE MANAGEMENT
  // ==========================================

  // Dati principali
  const [associazioni, setAssociazioni] = useState([]);
  const [progetti, setProgetti] = useState([]);
  const [entiAttuatori, setEntiAttuatori] = useState([]);

  // Stati UI
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [editingAssociazione, setEditingAssociazione] = useState(null);

  // Form data
  const [formData, setFormData] = useState({
    progetto_id: '',
    ente_attuatore_id: '',
    mansione: '',
    descrizione_mansione: '',
    data_inizio: '',
    data_fine: '',
    ore_previste: 0,
    ore_effettive: 0,
    tariffa_oraria: 0,
    budget_totale: 0,
    tipo_contratto: '',
    is_active: true,
    note: ''
  });

  // Filtri
  const [filters, setFilters] = useState({
    progetto_id: '',
    ente_attuatore_id: '',
    mansione: '',
    is_active: ''
  });

  // ==========================================
  // CARICAMENTO DATI
  // ==========================================

  useEffect(() => {
    loadAllData();
  }, [filters]);

  const loadAllData = async () => {
    try {
      setLoading(true);
      setError(null);

      // Costruisce query params per i filtri
      const params = new URLSearchParams();
      if (filters.progetto_id) params.append('progetto_id', filters.progetto_id);
      if (filters.ente_attuatore_id) params.append('ente_attuatore_id', filters.ente_attuatore_id);
      if (filters.mansione) params.append('mansione', filters.mansione);
      if (filters.is_active !== '') params.append('is_active', filters.is_active);

      const [associazioniRes, progettiRes, entiRes] = await Promise.all([
        fetch(`${API_BASE_URL}/api/v1/project-assignments/?${params}`),
        fetch(`${API_BASE_URL}/api/v1/projects/?limit=200`),
        fetch(`${API_BASE_URL}/api/v1/entities/?limit=200`)
      ]);

      if (!associazioniRes.ok || !progettiRes.ok || !entiRes.ok) {
        throw new Error('Errore nel caricamento dei dati');
      }

      const [associazioniData, progettiData, entiData] = await Promise.all([
        associazioniRes.json(),
        progettiRes.json(),
        entiRes.json()
      ]);

      setAssociazioni(associazioniData);
      setProgetti(progettiData);
      setEntiAttuatori(entiData);

    } catch (err) {
      console.error('Errore caricamento dati:', err);
      setError('Errore nel caricamento dei dati. Riprova più tardi.');
    } finally {
      setLoading(false);
    }
  };

  // ==========================================
  // GESTIONE FORM
  // ==========================================

  const handleInputChange = (field, value) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleFilterChange = (field, value) => {
    setFilters(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const resetForm = () => {
    setFormData({
      progetto_id: '',
      ente_attuatore_id: '',
      mansione: '',
      descrizione_mansione: '',
      data_inizio: '',
      data_fine: '',
      ore_previste: 0,
      ore_effettive: 0,
      tariffa_oraria: 0,
      budget_totale: 0,
      tipo_contratto: '',
      is_active: true,
      note: ''
    });
    setEditingAssociazione(null);
  };

  const openCreateModal = () => {
    resetForm();
    setShowModal(true);
  };

  const openEditModal = (associazione) => {
    setFormData({
      progetto_id: associazione.progetto_id,
      ente_attuatore_id: associazione.ente_attuatore_id,
      mansione: associazione.mansione || '',
      descrizione_mansione: associazione.descrizione_mansione || '',
      data_inizio: associazione.data_inizio ? associazione.data_inizio.split('T')[0] : '',
      data_fine: associazione.data_fine ? associazione.data_fine.split('T')[0] : '',
      ore_previste: associazione.ore_previste || 0,
      ore_effettive: associazione.ore_effettive || 0,
      tariffa_oraria: associazione.tariffa_oraria || 0,
      budget_totale: associazione.budget_totale || 0,
      tipo_contratto: associazione.tipo_contratto || '',
      is_active: associazione.is_active !== false,
      note: associazione.note || ''
    });
    setEditingAssociazione(associazione);
    setShowModal(true);
  };

  const closeModal = () => {
    setShowModal(false);
    resetForm();
  };

  // ==========================================
  // OPERAZIONI CRUD
  // ==========================================

  const handleSubmit = async (e) => {
    e.preventDefault();

    try {
      // Validazioni base
      if (!formData.progetto_id || !formData.ente_attuatore_id || !formData.mansione) {
        alert('Compilare tutti i campi obbligatori (Progetto, Ente, Mansione)');
        return;
      }

      if (!formData.data_inizio || !formData.data_fine) {
        alert('Specificare date di inizio e fine');
        return;
      }

      if (formData.ore_previste <= 0) {
        alert('Le ore previste devono essere maggiori di zero');
        return;
      }

      // Prepara i dati per l'API (converte stringhe date in datetime)
      const payload = {
        ...formData,
        progetto_id: parseInt(formData.progetto_id),
        ente_attuatore_id: parseInt(formData.ente_attuatore_id),
        ore_previste: parseFloat(formData.ore_previste),
        ore_effettive: parseFloat(formData.ore_effettive),
        tariffa_oraria: formData.tariffa_oraria ? parseFloat(formData.tariffa_oraria) : null,
        budget_totale: formData.budget_totale ? parseFloat(formData.budget_totale) : null,
        data_inizio: `${formData.data_inizio}T00:00:00`,
        data_fine: `${formData.data_fine}T23:59:59`
      };

      let response;
      if (editingAssociazione) {
        // Update
        response = await fetch(`${API_BASE_URL}/api/v1/project-assignments/${editingAssociazione.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
      } else {
        // Create
        response = await fetch(`${API_BASE_URL}/api/v1/project-assignments/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
      }

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Errore nel salvataggio');
      }

      // Ricarica i dati e chiudi il modal
      await loadAllData();
      closeModal();
      alert(editingAssociazione ? 'Associazione aggiornata!' : 'Associazione creata!');

    } catch (err) {
      console.error('Errore salvataggio:', err);
      alert(`Errore: ${err.message}`);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Confermi l\'eliminazione di questa associazione?')) {
      return;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/project-assignments/${id}?soft_delete=true`, {
        method: 'DELETE'
      });

      if (!response.ok) {
        throw new Error('Errore nell\'eliminazione');
      }

      await loadAllData();
      alert('Associazione disattivata con successo');

    } catch (err) {
      console.error('Errore eliminazione:', err);
      alert(`Errore: ${err.message}`);
    }
  };

  // ==========================================
  // HELPER FUNCTIONS
  // ==========================================

  const getProgettoName = (id) => {
    const progetto = progetti.find(p => p.id === id);
    return progetto ? progetto.name : 'N/D';
  };

  const getEnteName = (id) => {
    const ente = entiAttuatori.find(e => e.id === id);
    return ente ? ente.ragione_sociale : 'N/D';
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'N/D';
    const date = new Date(dateString);
    return date.toLocaleDateString('it-IT');
  };

  // ==========================================
  // RENDER
  // ==========================================

  if (loading && associazioni.length === 0) {
    return (
      <div className="progetto-mansione-ente-manager">
        <div className="loading-spinner">
          <div className="spinner"></div>
          <p>Caricamento...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="progetto-mansione-ente-manager">
      {/* HEADER */}
      <div className="manager-header">
        <div className="header-title">
          <h2>Gestione Associazioni Progetto-Mansione-Ente</h2>
          <p>Collega progetti con enti attuatori specificando mansioni, ore e costi</p>
        </div>
        <button className="btn-primary" onClick={openCreateModal}>
          + Nuova Associazione
        </button>
      </div>

      {/* MESSAGGI ERRORE */}
      {error && (
        <div className="alert alert-error">
          <span className="alert-icon">⚠️</span>
          <ErrorBanner error={error} />
        </div>
      )}

      {/* FILTRI */}
      <div className="filters-section">
        <div className="filters-grid">
          <div className="filter-group">
            <label>Progetto</label>
            <select
              value={filters.progetto_id}
              onChange={(e) => handleFilterChange('progetto_id', e.target.value)}
            >
              <option value="">Tutti i progetti</option>
              {progetti.map(p => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>

          <div className="filter-group">
            <label>Ente Attuatore</label>
            <select
              value={filters.ente_attuatore_id}
              onChange={(e) => handleFilterChange('ente_attuatore_id', e.target.value)}
            >
              <option value="">Tutti gli enti</option>
              {entiAttuatori.map(e => (
                <option key={e.id} value={e.id}>{e.ragione_sociale}</option>
              ))}
            </select>
          </div>

          <div className="filter-group">
            <label>Mansione</label>
            <input
              type="text"
              placeholder="Cerca mansione..."
              value={filters.mansione}
              onChange={(e) => handleFilterChange('mansione', e.target.value)}
            />
          </div>

          <div className="filter-group">
            <label>Stato</label>
            <select
              value={filters.is_active}
              onChange={(e) => handleFilterChange('is_active', e.target.value)}
            >
              <option value="">Tutti</option>
              <option value="true">Attive</option>
              <option value="false">Disattivate</option>
            </select>
          </div>
        </div>
      </div>

      {/* TABELLA ASSOCIAZIONI */}
      <div className="associations-table-container">
        {associazioni.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">📋</div>
            <h4>Nessuna associazione trovata</h4>
            <p>Crea una nuova associazione per collegare un progetto con un ente attuatore</p>
          </div>
        ) : (
          <table className="associations-table">
            <thead>
              <tr>
                <th>Progetto</th>
                <th>Ente Attuatore</th>
                <th>Mansione</th>
                <th>Periodo</th>
                <th>Ore Prev.</th>
                <th>Ore Eff.</th>
                <th>Progress</th>
                <th>Tariffa</th>
                <th>Stato</th>
                <th>Azioni</th>
              </tr>
            </thead>
            <tbody>
              {associazioni.map(ass => (
                <tr key={ass.id} className={!ass.is_active ? 'row-inactive' : ''}>
                  <td>{getProgettoName(ass.progetto_id)}</td>
                  <td>{getEnteName(ass.ente_attuatore_id)}</td>
                  <td>
                    <strong>{ass.mansione}</strong>
                    {ass.tipo_contratto && (
                      <span className="contract-badge">{ass.tipo_contratto}</span>
                    )}
                  </td>
                  <td className="date-range">
                    {formatDate(ass.data_inizio)} → {formatDate(ass.data_fine)}
                  </td>
                  <td className="hours-cell">{ass.ore_previste}h</td>
                  <td className="hours-cell">{ass.ore_effettive}h</td>
                  <td>
                    <div className="progress-bar">
                      <div
                        className="progress-fill"
                        style={{ width: `${Math.min(100, ass.percentuale_completamento || 0)}%` }}
                      ></div>
                      <span className="progress-text">
                        {(ass.percentuale_completamento || 0).toFixed(0)}%
                      </span>
                    </div>
                  </td>
                  <td className="price-cell">
                    {ass.tariffa_oraria ? `€${ass.tariffa_oraria}/h` : '-'}
                  </td>
                  <td>
                    <span className={`status-badge ${ass.is_active ? 'active' : 'inactive'}`}>
                      {ass.is_active ? 'Attiva' : 'Disattivata'}
                    </span>
                  </td>
                  <td className="actions-cell">
                    <button
                      className="btn-icon btn-edit"
                      onClick={() => openEditModal(ass)}
                      title="Modifica"
                    >
                      ✏️
                    </button>
                    <button
                      className="btn-icon btn-delete"
                      onClick={() => handleDelete(ass.id)}
                      title="Elimina"
                    >
                      🗑️
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* MODAL CREA/MODIFICA */}
      {showModal && (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{editingAssociazione ? 'Modifica Associazione' : 'Nuova Associazione'}</h3>
              <button className="modal-close" onClick={closeModal}>×</button>
            </div>

            <form onSubmit={handleSubmit} className="association-form">
              <div className="form-grid">
                {/* PROGETTO */}
                <div className="form-group full-width">
                  <label>Progetto *</label>
                  <select
                    value={formData.progetto_id}
                    onChange={(e) => handleInputChange('progetto_id', e.target.value)}
                    required
                  >
                    <option value="">Seleziona un progetto</option>
                    {progetti.map(p => (
                      <option key={p.id} value={p.id}>{p.name}</option>
                    ))}
                  </select>
                </div>

                {/* ENTE ATTUATORE */}
                <div className="form-group full-width">
                  <label>Ente Attuatore *</label>
                  <select
                    value={formData.ente_attuatore_id}
                    onChange={(e) => handleInputChange('ente_attuatore_id', e.target.value)}
                    required
                  >
                    <option value="">Seleziona un ente</option>
                    {entiAttuatori.map(e => (
                      <option key={e.id} value={e.id}>{e.ragione_sociale}</option>
                    ))}
                  </select>
                </div>

                {/* MANSIONE */}
                <div className="form-group full-width">
                  <label>Mansione *</label>
                  <input
                    type="text"
                    value={formData.mansione}
                    onChange={(e) => handleInputChange('mansione', e.target.value)}
                    placeholder="es. Docente, Tutor, Coordinatore..."
                    required
                  />
                </div>

                {/* DESCRIZIONE MANSIONE */}
                <div className="form-group full-width">
                  <label>Descrizione Mansione</label>
                  <textarea
                    value={formData.descrizione_mansione}
                    onChange={(e) => handleInputChange('descrizione_mansione', e.target.value)}
                    rows="3"
                    placeholder="Descrizione dettagliata delle attività..."
                  />
                </div>

                {/* DATE */}
                <div className="form-group">
                  <label>Data Inizio *</label>
                  <input
                    type="date"
                    value={formData.data_inizio}
                    onChange={(e) => handleInputChange('data_inizio', e.target.value)}
                    required
                  />
                </div>

                <div className="form-group">
                  <label>Data Fine *</label>
                  <input
                    type="date"
                    value={formData.data_fine}
                    onChange={(e) => handleInputChange('data_fine', e.target.value)}
                    required
                  />
                </div>

                {/* ORE */}
                <div className="form-group">
                  <label>Ore Previste *</label>
                  <input
                    type="number"
                    min="0"
                    step="0.5"
                    value={formData.ore_previste}
                    onChange={(e) => handleInputChange('ore_previste', e.target.value)}
                    required
                  />
                </div>

                <div className="form-group">
                  <label>Ore Effettive</label>
                  <input
                    type="number"
                    min="0"
                    step="0.5"
                    value={formData.ore_effettive}
                    onChange={(e) => handleInputChange('ore_effettive', e.target.value)}
                  />
                </div>

                {/* COSTI */}
                <div className="form-group">
                  <label>Tariffa Oraria (€)</label>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={formData.tariffa_oraria}
                    onChange={(e) => handleInputChange('tariffa_oraria', e.target.value)}
                  />
                </div>

                <div className="form-group">
                  <label>Budget Totale (€)</label>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={formData.budget_totale}
                    onChange={(e) => handleInputChange('budget_totale', e.target.value)}
                  />
                </div>

                {/* TIPO CONTRATTO */}
                <div className="form-group full-width">
                  <label>Tipo Contratto</label>
                  <select
                    value={formData.tipo_contratto}
                    onChange={(e) => handleInputChange('tipo_contratto', e.target.value)}
                  >
                    <option value="">Seleziona tipo</option>
                    <option value="Professionale">Professionale</option>
                    <option value="Occasionale">Occasionale</option>
                    <option value="Ordine di servizio">Ordine di servizio</option>
                    <option value="Contratto a progetto">Contratto a progetto</option>
                  </select>
                </div>

                {/* NOTE */}
                <div className="form-group full-width">
                  <label>Note</label>
                  <textarea
                    value={formData.note}
                    onChange={(e) => handleInputChange('note', e.target.value)}
                    rows="2"
                    placeholder="Note aggiuntive..."
                  />
                </div>

                {/* STATO */}
                <div className="form-group full-width">
                  <label className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={formData.is_active}
                      onChange={(e) => handleInputChange('is_active', e.target.checked)}
                    />
                    <span>Associazione attiva</span>
                  </label>
                </div>
              </div>

              <div className="modal-footer">
                <button type="button" className="btn-secondary" onClick={closeModal}>
                  Annulla
                </button>
                <button type="submit" className="btn-primary">
                  {editingAssociazione ? 'Salva Modifiche' : 'Crea Associazione'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default ProgettoMansioneEnteManager;
