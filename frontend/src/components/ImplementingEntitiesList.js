/**
 * COMPONENTE GESTIONE ENTI ATTUATORI
 *
 * Questa interfaccia permette di:
 * - Visualizzare lista completa degli enti attuatori
 * - Aggiungere nuovi enti (piemmei, Next Group, Wonder, etc.)
 * - Modificare enti esistenti
 * - Disattivare enti (soft delete)
 * - Ricercare enti per nome, P.IVA, città
 */

import React, { useState } from 'react';
import { useImplementingEntities, useNotifications } from '../hooks/useEntity';
import ImplementingEntityModal from './ImplementingEntityModal';
import './ImplementingEntitiesList.css';

const ImplementingEntitiesList = () => {
  // ==========================================
  // CONTEXT E HOOKS
  // ==========================================

  // Usa il Context per gestire gli enti attuatori
  const { data: entities, loading, error: contextError, refresh, create, update, remove } = useImplementingEntities();
  const { showSuccess, showError } = useNotifications();

  // Modal per creare/modificare ente
  const [showModal, setShowModal] = useState(false);
  const [editingEntity, setEditingEntity] = useState(null);

  // Stati locali per UI
  const [searchTerm, setSearchTerm] = useState('');
  const [activeFilter, setActiveFilter] = useState('all'); // 'all', 'active', 'inactive'

  // ==========================================
  // GESTIONE ENTI
  // ==========================================

  /**
   * APRE IL MODAL PER CREARE UN NUOVO ENTE
   */
  const handleCreateNew = () => {
    setEditingEntity(null);
    setShowModal(true);
  };

  /**
   * APRE IL MODAL PER MODIFICARE UN ENTE ESISTENTE
   */
  const handleEdit = (entity) => {
    setEditingEntity(entity);
    setShowModal(true);
  };

  /**
   * GESTISCE IL SALVATAGGIO (CREA O MODIFICA) DI UN ENTE
   */
  const handleSave = async (entityData) => {
    try {
      if (editingEntity) {
        // Aggiorna ente esistente
        await update(editingEntity.id, entityData);
        showSuccess(`Ente "${entityData.ragione_sociale}" aggiornato con successo!`);
      } else {
        // Crea nuovo ente
        await create(entityData);
        showSuccess(`Ente "${entityData.ragione_sociale}" creato con successo!`);
      }

      // Ricarica la lista e chiudi il modal
      await refresh();
      setShowModal(false);
      setEditingEntity(null);

    } catch (err) {
      console.error('Errore salvataggio ente:', err);
      const errorMsg = err.response?.data?.detail || 'Errore nel salvataggio dell\'ente';
      showError(errorMsg);
    }
  };

  /**
   * DISATTIVA UN ENTE (SOFT DELETE)
   */
  const handleDelete = async (entity) => {
    if (!window.confirm(`Sei sicuro di voler disattivare "${entity.ragione_sociale}"?\n\nL'ente non verrà eliminato ma solo disattivato.`)) {
      return;
    }

    try {
      await remove(entity.id);
      showSuccess(`Ente "${entity.ragione_sociale}" disattivato con successo`);
      await refresh();
    } catch (err) {
      console.error('Errore disattivazione ente:', err);
      showError(err.response?.data?.detail || 'Errore nella disattivazione dell\'ente');
    }
  };

  // ==========================================
  // FILTRI E RICERCA
  // ==========================================

  /**
   * FILTRA GLI ENTI IN BASE A RICERCA E STATO
   */
  const filteredEntities = entities.filter(entity => {
    // Filtro per stato attivo/inattivo
    if (activeFilter === 'active' && !entity.is_active) return false;
    if (activeFilter === 'inactive' && entity.is_active) return false;

    // Filtro per ricerca testuale
    if (searchTerm) {
      const search = searchTerm.toLowerCase();
      return (
        entity.ragione_sociale?.toLowerCase().includes(search) ||
        entity.partita_iva?.includes(search) ||
        entity.citta?.toLowerCase().includes(search) ||
        entity.provincia?.toLowerCase().includes(search)
      );
    }

    return true;
  });

  // ==========================================
  // RENDER COMPONENTE
  // ==========================================

  if (loading) {
    return (
      <div className="entities-manager">
        <div className="loading-spinner">
          <div className="spinner"></div>
          <p>Caricamento enti attuatori...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="entities-manager">
      {/* HEADER */}
      <div className="entities-header">
        <div className="header-title">
          <h2>🏢 Gestione Enti Attuatori</h2>
          <p>Gestisci gli enti che attuano i progetti formativi</p>
        </div>
        <button className="btn-primary" onClick={handleCreateNew}>
          ➕ Nuovo Ente Attuatore
        </button>
      </div>

      {/* MESSAGGI DI FEEDBACK */}
      {contextError && (
        <div className="alert alert-error">
          <span className="alert-icon">⚠️</span>
          {contextError.message || 'Errore nel caricamento degli enti'}
        </div>
      )}

      {/* BARRA RICERCA E FILTRI */}
      <div className="entities-filters">
        <div className="search-box">
          <input
            type="text"
            placeholder="🔍 Cerca per nome, P.IVA, città..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="search-input"
          />
        </div>

        <div className="filter-buttons">
          <button
            className={`filter-btn ${activeFilter === 'all' ? 'active' : ''}`}
            onClick={() => setActiveFilter('all')}
          >
            Tutti ({entities.length})
          </button>
          <button
            className={`filter-btn ${activeFilter === 'active' ? 'active' : ''}`}
            onClick={() => setActiveFilter('active')}
          >
            Attivi ({entities.filter(e => e.is_active).length})
          </button>
          <button
            className={`filter-btn ${activeFilter === 'inactive' ? 'active' : ''}`}
            onClick={() => setActiveFilter('inactive')}
          >
            Inattivi ({entities.filter(e => !e.is_active).length})
          </button>
        </div>
      </div>

      {/* LISTA ENTI */}
      {filteredEntities.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">🏢</div>
          <h3>{searchTerm ? 'Nessun ente trovato' : 'Nessun ente attuatore'}</h3>
          <p>
            {searchTerm
              ? 'Prova a modificare i criteri di ricerca'
              : 'Inizia aggiungendo il tuo primo ente attuatore'}
          </p>
          {!searchTerm && (
            <button className="btn-primary" onClick={handleCreateNew}>
              ➕ Aggiungi Primo Ente
            </button>
          )}
        </div>
      ) : (
        <div className="entities-grid">
          {filteredEntities.map(entity => (
            <div
              key={entity.id}
              className={`entity-card ${!entity.is_active ? 'inactive' : ''}`}
            >
              {/* Header Card */}
              <div className="entity-card-header">
                <div className="entity-name">
                  <h3>{entity.ragione_sociale}</h3>
                  {entity.forma_giuridica && (
                    <span className="entity-type">{entity.forma_giuridica}</span>
                  )}
                </div>
                {!entity.is_active && (
                  <span className="badge badge-inactive">Inattivo</span>
                )}
              </div>

              {/* Informazioni Principali */}
              <div className="entity-info">
                <div className="info-row">
                  <span className="info-label">📍 Sede:</span>
                  <span className="info-value">{entity.indirizzo_completo || 'N/D'}</span>
                </div>

                <div className="info-row">
                  <span className="info-label">💼 P.IVA:</span>
                  <span className="info-value">{entity.partita_iva}</span>
                </div>

                {entity.pec && (
                  <div className="info-row">
                    <span className="info-label">📧 PEC:</span>
                    <span className="info-value">{entity.pec}</span>
                  </div>
                )}

                {entity.referente_nome_completo && (
                  <div className="info-row">
                    <span className="info-label">👤 Referente:</span>
                    <span className="info-value">{entity.referente_nome_completo}</span>
                  </div>
                )}
              </div>

              {/* Azioni */}
              <div className="entity-actions">
                <button
                  className="btn-secondary"
                  onClick={() => handleEdit(entity)}
                  title="Modifica ente"
                >
                  ✏️ Modifica
                </button>
                {entity.is_active && (
                  <button
                    className="btn-danger"
                    onClick={() => handleDelete(entity)}
                    title="Disattiva ente"
                  >
                    🗑️ Disattiva
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* MODAL CREAZIONE/MODIFICA */}
      {showModal && (
        <ImplementingEntityModal
          entity={editingEntity}
          onClose={() => {
            setShowModal(false);
            setEditingEntity(null);
          }}
          onSave={handleSave}
        />
      )}
    </div>
  );
};

export default ImplementingEntitiesList;
