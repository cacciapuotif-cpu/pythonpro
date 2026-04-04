/**
 * COMPONENTE GESTIONE TEMPLATE DOCUMENTI
 *
 * Questa interfaccia permette di:
 * - Visualizzare lista completa dei template documentali
 * - Filtrare per ambito, profilo tecnico e stato
 * - Modificare, duplicare e disattivare template esistenti
 * - Evidenziare i default reali del perimetro contratti
 */

import React, { useEffect, useMemo, useState } from 'react';
import { useContractTemplates, useNotifications } from '../hooks/useEntity';
import ContractTemplateModal from './ContractTemplateModal';
import { getAvvisi, updateAvviso } from '../services/apiService';
import './ContractTemplatesManager.css';

const AMBITI_TEMPLATE = {
  contratto:         '📄 Contratto',
  preventivo:        '🧾 Preventivo',
  listino:           '🏷️ Listino',
  piano_finanziario: '💼 Piano Finanziario',
  timesheet:         '🕒 Timesheet',
  ordine:            '🛒 Ordine',
  generico:          '🗂️ Generico',
};

// Costanti per i tipi di contratto
const TIPI_CONTRATTO = {
  professionale: '👔 Professionale',
  occasionale: '📝 Occasionale',
  ordine_servizio: '📋 Ordine di Servizio',
  contratto_progetto: '📄 Contratto a Progetto',
  documento_generico: '🗂️ Documento Generico'
};

const getTemplateScopeLabel = (template) => {
  const hasProject = Boolean(template.progetto_id);
  const hasEntity = Boolean(template.ente_attuatore_id);
  const financialBits = [template.ente_erogatore, template.avviso ? `Avviso ${template.avviso}` : null].filter(Boolean);

  if (hasProject && hasEntity) {
    return [`Progetto #${template.progetto_id}`, `Ente #${template.ente_attuatore_id}`, ...financialBits].join(' · ');
  }

  if (hasProject) {
    return [`Progetto #${template.progetto_id}`, ...financialBits].join(' · ');
  }

  if (hasEntity) {
    return [`Ente #${template.ente_attuatore_id}`, ...financialBits].join(' · ');
  }

  if (financialBits.length > 0) {
    return financialBits.join(' · ');
  }

  return 'Globale';
};

const normalizeText = (value) => String(value || '').trim().toLowerCase();

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
  const [ambitoFilter, setAmbitoFilter] = useState('all');
  const [tipoFilter, setTipoFilter] = useState('all'); // 'all' o uno dei tipi
  const [activeFilter, setActiveFilter] = useState('all'); // 'all', 'active', 'inactive'
  const [linkedAvvisiByTemplate, setLinkedAvvisiByTemplate] = useState({});

  useEffect(() => {
    if (ambitoFilter === 'contratto' && tipoFilter === 'documento_generico') {
      setTipoFilter('all');
      return;
    }

    if (ambitoFilter !== 'all' && ambitoFilter !== 'contratto' && tipoFilter !== 'all' && tipoFilter !== 'documento_generico') {
      setTipoFilter('documento_generico');
    }
  }, [ambitoFilter, tipoFilter]);

  useEffect(() => {
    let cancelled = false;

    const loadAvvisi = async () => {
      try {
        const avvisi = await getAvvisi({ active_only: false, limit: 2000 });
        if (cancelled) {
          return;
        }

        const grouped = (Array.isArray(avvisi) ? avvisi : []).reduce((accumulator, avviso) => {
          if (!avviso?.template_id) {
            return accumulator;
          }
          const key = String(avviso.template_id);
          accumulator[key] = accumulator[key] || [];
          accumulator[key].push(avviso);
          return accumulator;
        }, {});

        Object.values(grouped).forEach((items) => {
          items.sort((left, right) => String(left.codice || '').localeCompare(String(right.codice || '')));
        });

        setLinkedAvvisiByTemplate(grouped);
      } catch (err) {
        if (!cancelled) {
          setLinkedAvvisiByTemplate({});
        }
      }
    };

    loadAvvisi();
    return () => {
      cancelled = true;
    };
  }, [templates]);

  const getLinkedAvvisi = useMemo(
    () => (templateId) => linkedAvvisiByTemplate[String(templateId)] || [],
    [linkedAvvisiByTemplate],
  );

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
      const linkedAvvisoIds = Array.isArray(templateData.linked_avviso_ids)
        ? templateData.linked_avviso_ids.map((id) => Number(id)).filter((id) => Number.isFinite(id))
        : [];
      const payload = { ...templateData };
      delete payload.linked_avviso_ids;
      let savedTemplate;

      if (editingTemplate) {
        // Aggiorna template esistente
        savedTemplate = await update(editingTemplate.id, payload);
        showSuccess(`Template "${payload.nome_template}" aggiornato con successo!`);
      } else {
        // Crea nuovo template
        savedTemplate = await create(payload);
        showSuccess(`Template "${payload.nome_template}" creato con successo!`);
      }

      if ((payload.ambito_template || '').toLowerCase() === 'piano_finanziario' && savedTemplate?.id) {
        const avvisi = await getAvvisi({ active_only: false, limit: 2000 });
        const currentlyLinked = (Array.isArray(avvisi) ? avvisi : []).filter(
          (a) => String(a.template_id || '') === String(savedTemplate.id)
        );

        // Unlink avvisi non più selezionati
        for (const a of currentlyLinked) {
          if (!linkedAvvisoIds.includes(Number(a.id))) {
            await updateAvviso(a.id, { template_id: null });
          }
        }
        // Link avvisi selezionati
        for (const avvisoId of linkedAvvisoIds) {
          await updateAvviso(avvisoId, { template_id: savedTemplate.id });
        }
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

  const availableTypeFilterOptions = Object.entries(TIPI_CONTRATTO).filter(([key]) => {
    if (ambitoFilter === 'contratto') {
      return key !== 'documento_generico';
    }

    if (ambitoFilter !== 'all') {
      return key === 'documento_generico';
    }

    return true;
  });

  /**
   * FILTRA I TEMPLATE IN BASE A RICERCA, TIPO E STATO
   */
  const filteredTemplates = templates.filter(template => {
    const currentScope = template.ambito_template || 'contratto';
    const linkedAvvisi = getLinkedAvvisi(template.id);

    // Filtro per stato attivo/inattivo
    if (activeFilter === 'active' && !template.is_active) return false;
    if (activeFilter === 'inactive' && template.is_active) return false;

    if (ambitoFilter !== 'all' && currentScope !== ambitoFilter) return false;

    // Filtro per profilo tecnico
    if (tipoFilter !== 'all') {
      if (currentScope === 'contratto') {
        if (template.tipo_contratto !== tipoFilter) return false;
      } else if (tipoFilter !== 'documento_generico') {
        return false;
      }
    }

    // Filtro per ricerca testuale
    if (searchTerm) {
      const search = normalizeText(searchTerm);
      const linkedAvvisiMatch = linkedAvvisi.some((avviso) =>
        normalizeText(avviso.codice).includes(search)
        || normalizeText(avviso.descrizione).includes(search)
      );
      return (
        template.nome_template?.toLowerCase().includes(search) ||
        template.descrizione?.toLowerCase().includes(search) ||
        template.tipo_contratto?.toLowerCase().includes(search) ||
        template.chiave_documento?.toLowerCase().includes(search) ||
        template.ente_erogatore?.toLowerCase().includes(search) ||
        template.avviso?.toLowerCase().includes(search) ||
        linkedAvvisiMatch ||
        currentScope.toLowerCase().includes(search)
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
          <p>Caricamento template documenti...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="templates-manager">
      {/* HEADER */}
      <div className="templates-header">
        <div className="header-title">
          <h2>📋 Gestione Template Documenti</h2>
          <p>Crea e gestisci template per contratti, preventivi, ordini, piani finanziari e documenti generici.</p>
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
          <div className="filter-group">
            <label>Ambito:</label>
            <select
              value={ambitoFilter}
              onChange={(e) => setAmbitoFilter(e.target.value)}
              className="filter-select"
            >
              <option value="all">Tutti gli ambiti</option>
              {Object.entries(AMBITI_TEMPLATE).map(([key, label]) => (
                <option key={key} value={key}>{label}</option>
              ))}
            </select>
          </div>

          <div className="filter-group">
            <label>{ambitoFilter === 'contratto' ? 'Tipo contratto:' : 'Profilo tecnico:'}</label>
            <select
              value={tipoFilter}
              onChange={(e) => setTipoFilter(e.target.value)}
              className="filter-select"
            >
              <option value="all">
                {ambitoFilter === 'contratto' ? 'Tutti i tipi contratto' : 'Tutti i profili'}
              </option>
              {availableTypeFilterOptions.map(([key, label]) => (
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
          <h3>{searchTerm || tipoFilter !== 'all' || ambitoFilter !== 'all' ? 'Nessun template trovato' : 'Nessun template documento'}</h3>
          <p>
            {searchTerm || tipoFilter !== 'all' || ambitoFilter !== 'all'
              ? 'Prova a modificare i criteri di ricerca'
              : 'Inizia aggiungendo il tuo primo template documento'}
          </p>
          {!searchTerm && tipoFilter === 'all' && ambitoFilter === 'all' && (
            <button className="btn-primary" onClick={handleCreateNew}>
              ➕ Aggiungi Primo Template
            </button>
          )}
        </div>
      ) : (
        <div className="templates-grid">
          {filteredTemplates.map(template => {
            const linkedAvvisi = getLinkedAvvisi(template.id);
            const linkedAvvisiLabel = linkedAvvisi.map((item) => item.codice).join(', ');
            return (
              <div
                key={template.id}
                className={`template-card ${!template.is_active ? 'inactive' : ''}`}
              >
              {/* Header Card */}
              <div className="template-card-header">
                <div className="template-name">
                  <h3>{template.nome_template}</h3>
                  <span className="badge">{AMBITI_TEMPLATE[template.ambito_template || 'contratto'] || (template.ambito_template || 'contratto')}</span>
                  <span className={`template-type type-${template.tipo_contratto}`}>
                    {(template.ambito_template || 'contratto') === 'contratto'
                      ? (TIPI_CONTRATTO[template.tipo_contratto] || template.tipo_contratto)
                      : (template.ambito_template || 'contratto') === 'piano_finanziario'
                        ? `💼 ${template.ente_erogatore || 'Fondo n.d.'}`
                      : (template.ambito_template || 'contratto') === 'listino'
                        ? `🏷️ ${template.chiave_documento || 'Listino'}`
                      : (template.ambito_template || 'contratto') === 'preventivo'
                        ? `🧾 ${template.chiave_documento || 'Preventivo'}`
                      : `🗂️ ${template.chiave_documento || template.ambito_template || 'Generico'}`}
                  </span>
                </div>
                <div className="template-badges">
                  {template.is_default && (template.ambito_template || 'contratto') === 'contratto' && (
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
                {template.chiave_documento && (
                  <div className="info-row">
                    <span className="info-label">🔑 Chiave:</span>
                    <span className="info-value">{template.chiave_documento}</span>
                  </div>
                )}

                <div className="info-row">
                  <span className="info-label">🎯 Scope:</span>
                  <span className="info-value">{getTemplateScopeLabel(template)}</span>
                </div>

                <div className="info-row">
                  <span className="info-label">🧭 Uso reale:</span>
                  <span className="info-value">
                    {(template.ambito_template || 'contratto') === 'contratto'
                      ? `Selezione per tipo ${TIPI_CONTRATTO[template.tipo_contratto] || template.tipo_contratto}`
                      : (template.ambito_template || 'contratto') === 'piano_finanziario'
                        ? `Piano per ${template.ente_erogatore || 'ente n.d.'}${linkedAvvisiLabel ? ` · Avvisi ${linkedAvvisiLabel}` : template.avviso ? ` · Avviso ${template.avviso}` : ''}`
                        : `Chiave: ${template.chiave_documento || 'non impostata'}`}
                  </span>
                </div>

                {(template.ambito_template || 'contratto') === 'piano_finanziario' && (
                  <div className="info-row">
                    <span className="info-label">📌 Avvisi collegati:</span>
                    <span className="info-value">
                      {linkedAvvisi.length > 0 ? linkedAvvisiLabel : template.avviso || 'Nessun avviso collegato'}
                    </span>
                  </div>
                )}

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
            );
          })}
        </div>
      )}

      {/* INFO BOX */}
      <div className="info-box">
        <h4>ℹ️ Informazioni sui Template Documenti</h4>
        <ul>
          <li><strong>Template default:</strong> il default automatico oggi vale solo per i contratti.</li>
          <li><strong>Ambito documento:</strong> puoi classificare il template come contratto, preventivo, ordine, piano finanziario o generico.</li>
          <li><strong>Template non contrattuali:</strong> usano il profilo tecnico `documento_generico` e vanno distinti tramite `chiave_documento`.</li>
          <li><strong>Template piano finanziario:</strong> gestisce direttamente anche gli avvisi collegati; non serve una sezione separata per gli avvisi.</li>
          <li><strong>Ambito applicativo:</strong> puoi lasciare il template globale oppure associarlo a uno specifico ente o progetto.</li>
          <li><strong>Variabili disponibili:</strong> puoi usare placeholder come <code>{'{{collaboratore_nome}}'}</code>, <code>{'{{progetto_nome}}'}</code>, <code>{'{{ente_ragione_sociale}}'}</code>.</li>
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
