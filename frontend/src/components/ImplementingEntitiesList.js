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

const ROLE_EXPERIENCE = {
  admin: {
    eyebrow: 'Presidio anagrafico',
    label: 'Amministratore',
    summary: 'Gestisci gli enti attuatori che alimentano progetti, contratti e riferimenti amministrativi del sistema.',
  },
};

const ImplementingEntitiesList = ({ currentUser }) => {
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
  const roleExperience = ROLE_EXPERIENCE[currentUser?.role] || ROLE_EXPERIENCE.admin;

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
      let savedEntity;
      if (editingEntity) {
        // Aggiorna ente esistente
        savedEntity = await update(editingEntity.id, entityData);
        showSuccess(`Ente "${entityData.ragione_sociale}" aggiornato con successo!`);
        await refresh();
        setEditingEntity(savedEntity);
      } else {
        // Crea nuovo ente e lascia il modal aperto per il caricamento del logo
        savedEntity = await create(entityData);
        showSuccess(`Ente "${entityData.ragione_sociale}" creato con successo! Ora puoi caricare il logo.`);
        await refresh();
        setEditingEntity(savedEntity);
      }

      return savedEntity;

    } catch (err) {
      console.error('Errore salvataggio ente:', err);
      const errorMsg = err.response?.data?.detail || 'Errore nel salvataggio dell\'ente';
      showError(errorMsg);
      throw err;
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

  const entitySummary = entities.reduce((summary, entity) => {
    summary.total += 1;
    if (entity.is_active) {
      summary.active += 1;
    } else {
      summary.inactive += 1;
    }
    if (!entity.pec || !entity.legale_rappresentante_nome_completo) {
      summary.attention += 1;
    }
    return summary;
  }, { total: 0, active: 0, inactive: 0, attention: 0 });

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

          <div className="role-operations-banner entity-role-banner">
            <div>
              <span className="role-operations-eyebrow">{roleExperience.eyebrow}</span>
              <strong>{roleExperience.label}</strong>
            </div>
            <p>{roleExperience.summary}</p>
          </div>
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

      <div className="entities-ops-summary">
        <div className="ops-summary-card info">
          <span>Enti attivi</span>
          <strong>{entitySummary.active}</strong>
          <small>Perimetro attualmente operativo</small>
        </div>
        <div className="ops-summary-card neutral">
          <span>Enti censiti</span>
          <strong>{entitySummary.total}</strong>
          <small>Anagrafiche complessive disponibili</small>
        </div>
        <div className="ops-summary-card warning">
          <span>In attenzione</span>
          <strong>{entitySummary.attention}</strong>
          <small>PEC o legale rappresentante da completare</small>
        </div>
      </div>

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

                {entity.legale_rappresentante_nome_completo && (
                  <div className="info-row">
                    <span className="info-label">👤 Legale Rappresentante:</span>
                    <span className="info-value">{entity.legale_rappresentante_nome_completo}</span>
                  </div>
                )}

                {!entity.pec || !entity.legale_rappresentante_nome_completo ? (
                  <div className="entity-attention-note">
                    Completare {[
                      !entity.pec ? 'PEC' : null,
                      !entity.legale_rappresentante_nome_completo ? 'legale rappresentante' : null,
                    ].filter(Boolean).join(' e ')} per una gestione contrattuale piu solida.
                  </div>
                ) : null}
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
