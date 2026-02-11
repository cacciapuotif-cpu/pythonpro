/**
 * COMPONENTE GESTIONE TEMPLATE CONTRATTI
 *
 * Questa interfaccia permette di:
 * - Visualizzare lista completa dei template contratti
 * - Aggiungere nuovi template (professionale, occasionale, ordine servizio, contratto a progetto)
 * - Modificare template esistenti
 * - Disattivare template
 * - Impostare template come default per ogni tipo
 * - Ricercare template per nome e tipo
 */

import React, { useState } from 'react';
import { useContractTemplates, useNotifications } from '../hooks/useEntity';
import ContractTemplateModal from './ContractTemplateModal';
import './ContractTemplatesManager.css';

// Costanti per i tipi di contratto
const TIPI_CONTRATTO = {
  professionale: '👔 Professionale',
  occasionale: '📝 Occasionale',
  ordine_servizio: '📋 Ordine di Servizio',
  contratto_progetto: '📄 Contratto a Progetto'
};

const ContractTemplatesManager = () => {
  // ==========================================
  // CONTEXT E HOOKS
  // ==========================================

  // Usa il Context per gestire i template contratti
  const { data: templates, loading, error: contextError, refresh, create, update, remove } = useContractTemplates();
  const { showSuccess, showError } = useNotifications();

  // Modal per creare/modificare template
  const [showModal, setShowModal] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState(null);

  // Stati locali per UI
  const [searchTerm, setSearchTerm] = useState('');
  const [tipoFilter, setTipoFilter] = useState('all'); // 'all' o uno dei tipi
  const [activeFilter, setActiveFilter] = useState('all'); // 'all', 'active', 'inactive'

  // ==========================================
  // GESTIONE TEMPLATE
  // ==========================================

  /**
   * APRE IL MODAL PER CREARE UN NUOVO TEMPLATE
   */
  const handleCreateNew = () => {
    setEditingTemplate(null);
    setShowModal(true);
  };

  /**
   * APRE IL MODAL PER MODIFICARE UN TEMPLATE ESISTENTE
   */
  const handleEdit = (template) => {
    setEditingTemplate(template);
    setShowModal(true);
  };

  /**
   * GESTISCE IL SALVATAGGIO (CREA O MODIFICA) DI UN TEMPLATE
   */
  const handleSave = async (templateData) => {
    try {
      if (editingTemplate) {
        // Aggiorna template esistente
        await update(editingTemplate.id, templateData);
        showSuccess(`Template "${templateData.nome_template}" aggiornato con successo!`);
      } else {
        // Crea nuovo template
        await create(templateData);
        showSuccess(`Template "${templateData.nome_template}" creato con successo!`);
      }

      // Ricarica la lista e chiudi il modal
      await refresh();
      setShowModal(false);
      setEditingTemplate(null);

    } catch (err) {
      console.error('Errore salvataggio template:', err);
      const errorMsg = err.response?.data?.detail || 'Errore nel salvataggio del template';
      showError(errorMsg);
    }
  };

  /**
   * DISATTIVA UN TEMPLATE (SOFT DELETE)
   */
  const handleDelete = async (template) => {
    if (!window.confirm(`Sei sicuro di voler disattivare il template "${template.nome_template}"?\n\nIl template non verrà eliminato ma solo disattivato.`)) {
      return;
    }

    try {
      await remove(template.id);
      showSuccess(`Template "${template.nome_template}" disattivato con successo`);
      await refresh();
    } catch (err) {
      console.error('Errore disattivazione template:', err);
      showError(err.response?.data?.detail || 'Errore nella disattivazione del template');
    }
  };

  /**
   * DUPLICA UN TEMPLATE
   */
  const handleDuplicate = async (template) => {
    const newTemplate = {
      ...template,
      nome_template: `${template.nome_template} (Copia)`,
      is_default: false, // La copia non può essere default
      versione: '1.0' // Reset versione
    };

    // Rimuovi campi che non servono per la creazione
    delete newTemplate.id;
    delete newTemplate.created_at;
    delete newTemplate.updated_at;
    delete newTemplate.numero_utilizzi;
    delete newTemplate.ultimo_utilizzo;
    delete newTemplate.created_by;
    delete newTemplate.updated_by;

    try {
      await create(newTemplate);
      showSuccess(`Template duplicato con successo!`);
      await refresh();
    } catch (err) {
      console.error('Errore duplicazione template:', err);
      showError(err.response?.data?.detail || 'Errore nella duplicazione del template');
    }
  };

  // ==========================================
  // FILTRI E RICERCA
  // ==========================================

  /**
   * FILTRA I TEMPLATE IN BASE A RICERCA, TIPO E STATO
   */
  const filteredTemplates = templates.filter(template => {
    // Filtro per stato attivo/inattivo
    if (activeFilter === 'active' && !template.is_active) return false;
    if (activeFilter === 'inactive' && template.is_active) return false;

    // Filtro per tipo contratto
    if (tipoFilter !== 'all' && template.tipo_contratto !== tipoFilter) return false;

    // Filtro per ricerca testuale
    if (searchTerm) {
      const search = searchTerm.toLowerCase();
      return (
        template.nome_template?.toLowerCase().includes(search) ||
        template.descrizione?.toLowerCase().includes(search) ||
        template.tipo_contratto?.toLowerCase().includes(search)
      );
    }

    return true;
  });

  // ==========================================
  // RENDER COMPONENTE
  // ==========================================

  if (loading) {
    return (
      <div className="templates-manager">
        <div className="loading-spinner">
          <div className="spinner"></div>
          <p>Caricamento template contratti...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="templates-manager">
      {/* HEADER */}
      <div className="templates-header">
        <div className="header-title">
          <h2>📋 Gestione Template Contratti</h2>
          <p>Crea e gestisci i template per i diversi tipi di contratto</p>
        </div>
        <button className="btn-primary" onClick={handleCreateNew}>
          ➕ Nuovo Template
        </button>
      </div>

      {/* MESSAGGI DI FEEDBACK */}
      {contextError && (
        <div className="alert alert-error">
          <span className="alert-icon">⚠️</span>
          {contextError.message || 'Errore nel caricamento dei template'}
        </div>
      )}

      {/* BARRA RICERCA E FILTRI */}
      <div className="templates-filters">
        <div className="search-box">
          <input
            type="text"
            placeholder="🔍 Cerca per nome, descrizione..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="search-input"
          />
        </div>

        <div className="filter-row">
          {/* Filtro per tipo contratto */}
          <div className="filter-group">
            <label>Tipo Contratto:</label>
            <select
              value={tipoFilter}
              onChange={(e) => setTipoFilter(e.target.value)}
              className="filter-select"
            >
              <option value="all">Tutti i tipi</option>
              {Object.entries(TIPI_CONTRATTO).map(([key, label]) => (
                <option key={key} value={key}>{label}</option>
              ))}
            </select>
          </div>

          {/* Filtro per stato */}
          <div className="filter-buttons">
            <button
              className={`filter-btn ${activeFilter === 'all' ? 'active' : ''}`}
              onClick={() => setActiveFilter('all')}
            >
              Tutti ({templates.length})
            </button>
            <button
              className={`filter-btn ${activeFilter === 'active' ? 'active' : ''}`}
              onClick={() => setActiveFilter('active')}
            >
              Attivi ({templates.filter(t => t.is_active).length})
            </button>
            <button
              className={`filter-btn ${activeFilter === 'inactive' ? 'active' : ''}`}
              onClick={() => setActiveFilter('inactive')}
            >
              Inattivi ({templates.filter(t => !t.is_active).length})
            </button>
          </div>
        </div>
      </div>

      {/* LISTA TEMPLATE */}
      {filteredTemplates.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">📋</div>
          <h3>{searchTerm || tipoFilter !== 'all' ? 'Nessun template trovato' : 'Nessun template contratto'}</h3>
          <p>
            {searchTerm || tipoFilter !== 'all'
              ? 'Prova a modificare i criteri di ricerca'
              : 'Inizia aggiungendo il tuo primo template contratto'}
          </p>
          {!searchTerm && tipoFilter === 'all' && (
            <button className="btn-primary" onClick={handleCreateNew}>
              ➕ Aggiungi Primo Template
            </button>
          )}
        </div>
      ) : (
        <div className="templates-grid">
          {filteredTemplates.map(template => (
            <div
              key={template.id}
              className={`template-card ${!template.is_active ? 'inactive' : ''}`}
            >
              {/* Header Card */}
              <div className="template-card-header">
                <div className="template-name">
                  <h3>{template.nome_template}</h3>
                  <span className={`template-type type-${template.tipo_contratto}`}>
                    {TIPI_CONTRATTO[template.tipo_contratto] || template.tipo_contratto}
                  </span>
                </div>
                <div className="template-badges">
                  {template.is_default && (
                    <span className="badge badge-default">⭐ Default</span>
                  )}
                  {!template.is_active && (
                    <span className="badge badge-inactive">Inattivo</span>
                  )}
                </div>
              </div>

              {/* Descrizione */}
              {template.descrizione && (
                <div className="template-description">
                  <p>{template.descrizione}</p>
                </div>
              )}

              {/* Informazioni */}
              <div className="template-info">
                <div className="info-row">
                  <span className="info-label">📦 Versione:</span>
                  <span className="info-value">{template.versione || '1.0'}</span>
                </div>

                <div className="info-row">
                  <span className="info-label">📊 Utilizzi:</span>
                  <span className="info-value">{template.numero_utilizzi || 0}</span>
                </div>

                <div className="info-row">
                  <span className="info-label">🖼️ Logo ente:</span>
                  <span className="info-value">{template.include_logo_ente ? '✅ Sì' : '❌ No'}</span>
                </div>

                {template.ultimo_utilizzo && (
                  <div className="info-row">
                    <span className="info-label">🕒 Ultimo uso:</span>
                    <span className="info-value">
                      {new Date(template.ultimo_utilizzo).toLocaleDateString('it-IT')}
                    </span>
                  </div>
                )}
              </div>

              {/* Azioni */}
              <div className="template-actions">
                <button
                  className="btn-secondary btn-small"
                  onClick={() => handleEdit(template)}
                  title="Modifica template"
                >
                  ✏️ Modifica
                </button>
                <button
                  className="btn-secondary btn-small"
                  onClick={() => handleDuplicate(template)}
                  title="Duplica template"
                >
                  📋 Duplica
                </button>
                {template.is_active && (
                  <button
                    className="btn-danger btn-small"
                    onClick={() => handleDelete(template)}
                    title="Disattiva template"
                  >
                    🗑️ Disattiva
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* INFO BOX */}
      <div className="info-box">
        <h4>ℹ️ Informazioni sui Template Contratti</h4>
        <ul>
          <li><strong>Template Default:</strong> Ogni tipo di contratto può avere un template predefinito che verrà usato automaticamente se non ne viene specificato uno.</li>
          <li><strong>Variabili disponibili:</strong> Puoi usare variabili come <code>{'{{collaboratore_nome}}'}</code>, <code>{'{{progetto_nome}}'}</code>, <code>{'{{ente_ragione_sociale}}'}</code> nel contenuto HTML.</li>
          <li><strong>Logo ente:</strong> Se abilitato, il logo dell'ente attuatore verrà incluso nel contratto generato.</li>
          <li><strong>Versione:</strong> Aggiorna la versione quando modifichi significativamente un template già utilizzato.</li>
        </ul>
      </div>

      {/* MODAL CREAZIONE/MODIFICA */}
      {showModal && (
        <ContractTemplateModal
          template={editingTemplate}
          onClose={() => {
            setShowModal(false);
            setEditingTemplate(null);
          }}
          onSave={handleSave}
        />
      )}
    </div>
  );
};

export default ContractTemplatesManager;
