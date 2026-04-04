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

import React, { useState, useMemo, useEffect } from 'react';
import { useProjects, useImplementingEntities, useNotifications } from '../hooks/useEntity';
import { getAvvisi, getContractTemplates } from '../services/apiService';
import './ProjectManager.css';

const ROLE_EXPERIENCE = {
  admin: {
    eyebrow: 'Controllo strutturale',
    label: 'Amministratore',
    summary: 'Puoi creare, modificare e dismettere i progetti, oltre a presidiare gli elementi amministrativi piu sensibili.',
    ctaLabel: '➕ Nuovo Progetto',
  },
  manager: {
    eyebrow: 'Presidio operativo',
    label: 'Operatore',
    summary: 'Concentrati sull’aggiornamento di delivery, stato e coerenza progettuale. Creazione ed eliminazione restano presidiate dagli admin.',
    ctaLabel: '✏️ Aggiorna Progetto',
  },
  user: {
    eyebrow: 'Presidio operativo',
    label: 'Operatore',
    summary: 'Concentrati sull’aggiornamento di delivery, stato e coerenza progettuale. Creazione ed eliminazione restano presidiate dagli admin.',
    ctaLabel: '✏️ Aggiorna Progetto',
  },
};

const PROJECT_FORM_STEPS = [
  {
    id: 'base',
    title: 'Base',
    description: 'Identita del progetto, stato e calendario operativo.',
    fields: ['name', 'status', 'start_date', 'end_date', 'description'],
  },
  {
    id: 'governance',
    title: 'Governance',
    description: 'CUP, atto di approvazione e riferimenti amministrativi.',
    fields: ['cup', 'atto_approvazione'],
  },
  {
    id: 'delivery',
    title: 'Delivery',
    description: 'Sede operativa, ente attuatore, ente erogatore e avviso.',
    fields: ['sede_aziendale_comune', 'sede_aziendale_via', 'sede_aziendale_numero_civico', 'ente_attuatore_id', 'template_piano_finanziario_id', 'ente_erogatore', 'avviso'],
  },
];

const PROJECT_ENTI_EROGATORI = [
  'FAPI',
  'FONDIMPRESA',
  'FORMAZIENDA',
  'REGIONE CAMPANIA',
  'REGIONE LOMBARDIA',
  'MIMIT',
  'ALTRO',
];

const normalizeText = (value) => String(value || '').trim().toLowerCase();

const ProjectManager = ({ currentUser }) => {
  // ==========================================
  // CONTEXT E HOOKS
  // ==========================================

  // Carica dati dal Context
  const { data: projects, loading: loadingProjects, error: contextError, refresh, create, update, remove } = useProjects();
  const { data: allEntities, loading: loadingEntities } = useImplementingEntities();
  const { showSuccess, showError } = useNotifications();
  const isAdmin = currentUser?.role === 'admin';
  const roleExperience = ROLE_EXPERIENCE[currentUser?.role] || ROLE_EXPERIENCE.user;

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
    ente_erogatore: '',
    cup: '',
    atto_approvazione: '',
    sede_aziendale_comune: '',
    sede_aziendale_via: '',
    sede_aziendale_numero_civico: '',
    avviso: '',
    avviso_id: '',
    template_piano_finanziario_id: '',
    ente_attuatore_id: null // NUOVO: FK verso ente attuatore
  });
  const [financialTemplates, setFinancialTemplates] = useState([]);
  const [avvisiCatalogo, setAvvisiCatalogo] = useState([]);

  // Stati locali dell'interfaccia
  const [editingId, setEditingId] = useState(null); // ID del progetto in modifica
  const [showForm, setShowForm] = useState(false);  // Mostra/nascondi form
  const [deleteConfirm, setDeleteConfirm] = useState(null); // Stato per conferma eliminazione
  const [statusFilter, setStatusFilter] = useState('all'); // Filtri per la visualizzazione
  const [activeStepIndex, setActiveStepIndex] = useState(0);

  // Combina stati di loading
  const loading = loadingProjects || loadingEntities;
  useEffect(() => {
    let cancelled = false;

    const loadFinancialTemplates = async () => {
      try {
        const [data, avvisi] = await Promise.all([
          getContractTemplates({
            ambito_template: 'piano_finanziario',
            is_active: true,
            limit: 300,
          }),
          getAvvisi({ active_only: true, limit: 500 }),
        ]);
        if (!cancelled) {
          setFinancialTemplates(Array.isArray(data) ? data : []);
          setAvvisiCatalogo(Array.isArray(avvisi) ? avvisi : []);
        }
      } catch (error) {
        if (!cancelled) {
          setFinancialTemplates([]);
          setAvvisiCatalogo([]);
        }
      }
    };

    loadFinancialTemplates();
    return () => {
      cancelled = true;
    };
  }, []);

  const getTemplateLinkedAvvisi = (templateId) =>
    avvisiCatalogo.filter((item) => String(item.template_id || '') === String(templateId));

  const getTemplateAvvisoCodes = (template) => {
    const linkedCodes = getTemplateLinkedAvvisi(template?.id).map((item) => item.codice).filter(Boolean);
    if (linkedCodes.length > 0) {
      return linkedCodes;
    }
    return template?.avviso ? [template.avviso] : [];
  };

  const selectedFinancialTemplate = financialTemplates.find(
    (template) => String(template.id) === String(formData.template_piano_finanziario_id),
  );

  // ==========================================
  // GESTIONE FORM
  // ==========================================

  /**
   * GESTISCE I CAMBIAMENTI NEI CAMPI DEL FORM
   */
  const handleInputChange = (e) => {
    const { name, value } = e.target;

    if (name === 'template_piano_finanziario_id') {
      const nextTemplate = financialTemplates.find((template) => String(template.id) === String(value));
      const linkedAvvisi = nextTemplate ? getTemplateLinkedAvvisi(nextTemplate.id) : [];
      const linkedAvviso = linkedAvvisi[0] || null;
      setFormData(prev => ({
        ...prev,
        template_piano_finanziario_id: value,
        ...(nextTemplate ? {
          ente_erogatore: nextTemplate.ente_erogatore || prev.ente_erogatore,
          avviso: (linkedAvviso?.codice || nextTemplate.avviso || prev.avviso),
          avviso_id: linkedAvviso ? String(linkedAvviso.id) : prev.avviso_id,
        } : {
          avviso: '',
          avviso_id: '',
        })
      }));
      return;
    }

    if (name === 'avviso_id') {
      const selected = avvisiCatalogo.find((a) => String(a.id) === String(value));
      setFormData(prev => ({
        ...prev,
        avviso_id: value,
        avviso: selected?.codice || prev.avviso,
      }));
      return;
    }

    if (name === 'ente_erogatore') {
      setFormData(prev => {
        const currentTemplate = financialTemplates.find((template) => String(template.id) === String(prev.template_piano_finanziario_id));
        const templateEnte = normalizeText(currentTemplate?.ente_erogatore);
        const nextEnte = normalizeText(value);
        const shouldClearTemplate = currentTemplate && templateEnte && nextEnte && templateEnte !== nextEnte;
        return {
          ...prev,
          ente_erogatore: value,
          ...(shouldClearTemplate ? {
            template_piano_finanziario_id: '',
            avviso: '',
            avviso_id: '',
          } : {}),
        };
      });
      return;
    }

    setFormData(prev => ({
      ...prev,
      [name]: value,
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

    if (!formData.atto_approvazione.trim()) {
      errors.push('L\'atto di approvazione è obbligatorio');
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

  const getStepErrorCounts = () => {
    const errors = validateForm();
    return PROJECT_FORM_STEPS.map((step) =>
      step.fields.filter((field) =>
        errors.some((error) => {
          if (field === 'name') return error.includes('nome del progetto');
          if (field === 'description') return error.includes('descrizione');
          if (field === 'atto_approvazione') return error.includes("atto di approvazione");
          if (field === 'end_date' || field === 'start_date') return error.includes('data di fine');
          return false;
        })
      ).length
    );
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
        ente_attuatore_id: formData.ente_attuatore_id ? parseInt(formData.ente_attuatore_id, 10) : null,
        start_date: formData.start_date ? `${formData.start_date}T00:00:00Z` : null,
        end_date: formData.end_date ? `${formData.end_date}T23:59:59Z` : null,
        ente_erogatore: formData.ente_erogatore || null,
        avviso: formData.avviso || null,
        avviso_id: formData.avviso_id ? parseInt(formData.avviso_id, 10) : null,
        template_piano_finanziario_id: formData.template_piano_finanziario_id ? parseInt(formData.template_piano_finanziario_id, 10) : null,
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
      showError(err?.response?.data?.detail || err?.message || 'Errore nel salvataggio. Riprova.');
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
      ente_erogatore: '',
      cup: '',
      atto_approvazione: '',
      sede_aziendale_comune: '',
      sede_aziendale_via: '',
      sede_aziendale_numero_civico: '',
      avviso: '',
      avviso_id: '',
      template_piano_finanziario_id: '',
      ente_attuatore_id: null
    });
    setEditingId(null);
    setShowForm(false);
    setActiveStepIndex(0);
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
      ente_erogatore: project.ente_erogatore || '',
      cup: project.cup || '',
      atto_approvazione: project.atto_approvazione || '',
      sede_aziendale_comune: project.sede_aziendale_comune || '',
      sede_aziendale_via: project.sede_aziendale_via || '',
      sede_aziendale_numero_civico: project.sede_aziendale_numero_civico || '',
      avviso: project.avviso || '',
      avviso_id: project.avviso_id ? String(project.avviso_id) : '',
      template_piano_finanziario_id: project.template_piano_finanziario_id ? String(project.template_piano_finanziario_id) : '',
      ente_attuatore_id: project.ente_attuatore_id || null
    });
    setEditingId(project.id);
    setShowForm(true);
    setActiveStepIndex(0);
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
  const getProjectOperationalState = (project) => {
    const hasEntity = !!project.ente_attuatore_id;

    if (project.status === 'active' && project.end_date) {
      const endDate = new Date(project.end_date);
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      endDate.setHours(0, 0, 0, 0);
      const diffDays = Math.ceil((endDate - today) / (1000 * 60 * 60 * 24));

      if (diffDays < 0) {
        return 'overdue';
      }

      if (diffDays <= 30 || !hasEntity) {
        return 'attention';
      }
    }

    if (!hasEntity) {
      return 'attention';
    }

    return 'stable';
  };

  const filteredProjects = projects.filter(project => {
    if (statusFilter === 'all') return true;
    if (statusFilter === 'attention') return getProjectOperationalState(project) !== 'stable';
    return project.status === statusFilter;
  });

  const projectSummary = useMemo(() => {
    return projects.reduce((summary, project) => {
      const state = getProjectOperationalState(project);
      summary.total += 1;
      if (project.status === 'active') summary.active += 1;
      if (state === 'attention') summary.attention += 1;
      if (state === 'overdue') summary.overdue += 1;
      if (!project.ente_attuatore_id) summary.missingEntity += 1;
      return summary;
    }, {
      total: 0,
      active: 0,
      attention: 0,
      overdue: 0,
      missingEntity: 0,
    });
  }, [projects]);

  const stepErrorCounts = getStepErrorCounts();
  const completedFields = [
    formData.name,
    formData.description,
    formData.start_date,
    formData.end_date,
    formData.ente_erogatore,
    formData.cup,
    formData.atto_approvazione,
    formData.sede_aziendale_comune,
    formData.sede_aziendale_via,
    formData.sede_aziendale_numero_civico,
    formData.ente_attuatore_id,
  ].filter((value) => `${value ?? ''}`.trim() !== '').length;
  const completionPercentage = Math.round((completedFields / 12) * 100);
  const currentStep = PROJECT_FORM_STEPS[activeStepIndex];
  const selectedEntity = implementingEntities.find((entity) => String(entity.id) === String(formData.ente_attuatore_id));
  const avvisiFiltrati = selectedFinancialTemplate
    ? getTemplateLinkedAvvisi(selectedFinancialTemplate.id)
    : avvisiCatalogo.filter(
      (item) => !formData.ente_erogatore || normalizeText(item.ente_erogatore) === normalizeText(formData.ente_erogatore)
    );
  const showCreateAction = isAdmin || editingId !== null;

  const goToStep = (index) => {
    if (index < 0 || index >= PROJECT_FORM_STEPS.length) {
      return;
    }

    setActiveStepIndex(index);
  };

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

        <div className="role-operations-banner project-role-banner">
          <div>
            <span className="role-operations-eyebrow">{roleExperience.eyebrow}</span>
            <strong>{roleExperience.label}</strong>
          </div>
          <p>{roleExperience.summary}</p>
        </div>

        {showCreateAction ? (
          <button
            className={`add-button ${showForm ? 'active' : ''}`}
            onClick={() => {
              setShowForm(!showForm);
              if (showForm) {
                resetForm();
              } else {
                setActiveStepIndex(0);
              }
            }}
          >
            {showForm ? '❌ Chiudi Form' : roleExperience.ctaLabel}
          </button>
        ) : (
          <div className="project-guidance-pill">
            Apri un progetto esistente per aggiornarne stato, delivery e riferimenti attuativi.
          </div>
        )}
      </div>

      {/* MESSAGGI DI STATO */}
      {contextError && (
        <div className="message error-message">
          ⚠️ {contextError.message || 'Errore nel caricamento dei progetti'}
        </div>
      )}

      {/* FORM AGGIUNTA/MODIFICA */}
      {showForm && (
        <div className="form-section project-wizard">
          <div className="wizard-header">
            <div>
              <span className="wizard-eyebrow">Wizard progetto</span>
              <h2>{editingId ? 'Modifica progetto' : 'Nuovo progetto'}</h2>
              <p>
                Organizza il progetto in tre passaggi: base, governance e delivery operativo.
              </p>
            </div>
            <div className="wizard-progress-card project-progress-card">
              <span>Completamento</span>
              <strong>{completionPercentage}%</strong>
              <small>{completedFields} campi su 12 valorizzati</small>
            </div>
          </div>

          <div className="wizard-layout">
            <aside className="wizard-sidebar">
              <ol className="wizard-steps">
                {PROJECT_FORM_STEPS.map((step, index) => {
                  const isActive = index === activeStepIndex;
                  const isDone = index < activeStepIndex;
                  const hasErrors = stepErrorCounts[index] > 0;

                  return (
                    <li key={step.id}>
                      <button
                        type="button"
                        className={`wizard-step ${isActive ? 'active' : ''} ${isDone ? 'done' : ''}`}
                        onClick={() => goToStep(index)}
                      >
                        <span className={`wizard-step-index ${hasErrors ? 'error' : ''}`}>
                          {isDone ? '✓' : index + 1}
                        </span>
                        <span className="wizard-step-copy">
                          <strong>{step.title}</strong>
                          <small>{step.description}</small>
                          {hasErrors ? <em>{stepErrorCounts[index]} controlli aperti</em> : null}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ol>

              <div className="wizard-summary-card">
                <h3>Checkpoint progetto</h3>
                <ul>
                  <li className={formData.name ? 'done' : ''}>
                    Nome progetto {formData.name ? 'presente' : 'mancante'}
                  </li>
                  <li className={formData.atto_approvazione ? 'done' : ''}>
                    Atto di approvazione {formData.atto_approvazione ? 'presente' : 'mancante'}
                  </li>
                  <li className={formData.start_date && formData.end_date ? 'done' : ''}>
                    Finestra temporale {formData.start_date && formData.end_date ? 'impostata' : 'incompleta'}
                  </li>
                  <li className={formData.ente_attuatore_id ? 'done' : ''}>
                    Ente attuatore {formData.ente_attuatore_id ? 'selezionato' : 'non selezionato'}
                  </li>
                  <li className={formData.ente_erogatore ? 'done' : ''}>
                    Ente erogatore {formData.ente_erogatore ? 'selezionato' : 'non selezionato'}
                  </li>
                </ul>
              </div>
            </aside>

            <form onSubmit={handleSubmit} className="project-form wizard-form">
              <div className="wizard-step-panel">
                <div className="wizard-step-header">
                  <div>
                    <span className="wizard-step-label">
                      Step {activeStepIndex + 1} di {PROJECT_FORM_STEPS.length}
                    </span>
                    <h3>{currentStep.title}</h3>
                    <p>{currentStep.description}</p>
                  </div>
                </div>

                {currentStep.id === 'base' && (
                  <div className="form-grid">
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

                    <div className="form-group full-width">
                      <label htmlFor="description">Descrizione *</label>
                      <textarea
                        id="description"
                        name="description"
                        value={formData.description}
                        onChange={handleInputChange}
                        placeholder="Descrivi obiettivi, attivita, target e valore operativo del progetto..."
                        rows="5"
                        required
                      />
                    </div>
                  </div>
                )}

                {currentStep.id === 'governance' && (
                  <div className="form-grid">
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
                      <small className="field-hint">
                        Utile per tracciabilita, reporting e documentazione.
                      </small>
                    </div>

                    <div className="wizard-hint-card project-hint-card">
                      <h4>Governance minima</h4>
                      <p>
                        Atto di approvazione e date coerenti sono la base per evitare attriti a valle su presenze, assegnazioni e contratti.
                      </p>
                    </div>

                    <div className="form-group full-width">
                      <label htmlFor="atto_approvazione">Atto di Approvazione *</label>
                      <input
                        type="text"
                        id="atto_approvazione"
                        name="atto_approvazione"
                        value={formData.atto_approvazione}
                        onChange={handleInputChange}
                        placeholder="Es: DD n. 123 del 15/02/2026"
                        required
                      />
                    </div>
                  </div>
                )}

                {currentStep.id === 'delivery' && (
                  <div className="wizard-documents-grid">
                    <div className="form-grid">
                      <div className="form-group">
                        <label htmlFor="sede_aziendale_comune">Sede Aziendale - Comune</label>
                        <input
                          type="text"
                          id="sede_aziendale_comune"
                          name="sede_aziendale_comune"
                          value={formData.sede_aziendale_comune}
                          onChange={handleInputChange}
                          placeholder="Es: Napoli"
                        />
                      </div>

                      <div className="form-group">
                        <label htmlFor="sede_aziendale_via">Sede Aziendale - Via</label>
                        <input
                          type="text"
                          id="sede_aziendale_via"
                          name="sede_aziendale_via"
                          value={formData.sede_aziendale_via}
                          onChange={handleInputChange}
                          placeholder="Es: Via Roma"
                        />
                      </div>

                      <div className="form-group">
                        <label htmlFor="sede_aziendale_numero_civico">Sede Aziendale - Numero Civico</label>
                        <input
                          type="text"
                          id="sede_aziendale_numero_civico"
                          name="sede_aziendale_numero_civico"
                          value={formData.sede_aziendale_numero_civico}
                          onChange={handleInputChange}
                          placeholder="Es: 25"
                        />
                      </div>

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
                          Seleziona l'ente che attua il progetto.
                        </small>
                      </div>

                      <div className="form-group">
                        <label htmlFor="template_piano_finanziario_id">Template Piano Finanziario</label>
                        <select
                          id="template_piano_finanziario_id"
                          name="template_piano_finanziario_id"
                          value={formData.template_piano_finanziario_id}
                          onChange={handleInputChange}
                        >
                          <option value="">Nessun template collegato</option>
                          {financialTemplates.map((template) => (
                            <option key={template.id} value={template.id}>
                              {template.nome_template}
                              {template.ente_erogatore ? ` · ${template.ente_erogatore}` : ''}
                              {getTemplateAvvisoCodes(template).length > 0 ? ` · Avvisi ${getTemplateAvvisoCodes(template).join(', ')}` : ''}
                            </option>
                          ))}
                        </select>
                        <small className="field-hint">
                          Se selezionato, il progetto propone ente erogatore e avvisi collegati al template, ma puoi ancora scegliere l'avviso corretto.
                        </small>
                      </div>

                      <div className="form-group">
                        <label htmlFor="ente_erogatore">Ente Erogatore</label>
                        <select
                          id="ente_erogatore"
                          name="ente_erogatore"
                          value={formData.ente_erogatore}
                          onChange={handleInputChange}
                        >
                          <option value="">Seleziona Ente Erogatore</option>
                          {PROJECT_ENTI_EROGATORI.map((ente) => (
                            <option key={ente} value={ente}>
                              {ente}
                            </option>
                          ))}
                        </select>
                        <small className="field-hint">
                          Ente che eroga il finanziamento. Usato per agganciare il progetto al piano finanziario corretto.
                        </small>
                      </div>

                      <div className="form-group">
                        <label htmlFor="avviso">Avviso</label>
                        <select
                          id="avviso_id"
                          name="avviso_id"
                          value={formData.avviso_id}
                          onChange={handleInputChange}
                        >
                          <option value="">Seleziona avviso</option>
                          {avvisiFiltrati.map((avvisoItem) => (
                            <option key={avvisoItem.id} value={avvisoItem.id}>
                              {avvisoItem.codice}
                            </option>
                          ))}
                        </select>
                        <small className="field-hint">
                          {selectedFinancialTemplate
                            ? 'Avvisi collegati al template selezionato.'
                            : 'Catalogo centralizzato avvisi filtrato per ente erogatore.'}
                        </small>
                      </div>
                    </div>

                    <div className="project-delivery-card">
                      <h4>Riepilogo delivery</h4>
                      <div className="project-delivery-list">
                        <div>
                          <span>Ente attuatore</span>
                          <strong>{selectedEntity ? selectedEntity.ragione_sociale : 'Non selezionato'}</strong>
                        </div>
                        <div>
                          <span>Sede operativa</span>
                          <strong>
                            {[formData.sede_aziendale_via, formData.sede_aziendale_numero_civico, formData.sede_aziendale_comune]
                              .filter(Boolean)
                              .join(', ') || 'Non impostata'}
                          </strong>
                        </div>
                        <div>
                          <span>Template piano</span>
                          <strong>
                            {financialTemplates.find((template) => String(template.id) === String(formData.template_piano_finanziario_id))?.nome_template || 'Non impostato'}
                          </strong>
                        </div>
                        <div>
                          <span>Ente erogatore</span>
                          <strong>{formData.ente_erogatore || 'Non impostato'}</strong>
                        </div>
                        <div>
                          <span>Avviso</span>
                          <strong>{formData.avviso || 'Non impostato'}</strong>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              <div className="form-buttons wizard-actions">
                <button
                  type="button"
                  onClick={resetForm}
                  className="cancel-button"
                >
                  Annulla
                </button>

                <div className="wizard-actions-right">
                  <button
                    type="button"
                    onClick={() => goToStep(activeStepIndex - 1)}
                    className="secondary-button"
                    disabled={activeStepIndex === 0}
                  >
                    Indietro
                  </button>

                  {activeStepIndex < PROJECT_FORM_STEPS.length - 1 ? (
                    <button
                      type="button"
                      onClick={() => goToStep(activeStepIndex + 1)}
                      className="submit-button"
                    >
                      Continua
                    </button>
                  ) : (
                    <button
                      type="submit"
                      className="submit-button"
                      disabled={loading}
                    >
                      {loading ? '⏳ Salvando...' : (editingId ? '✏️ Aggiorna' : isAdmin ? '➕ Crea Progetto' : '✏️ Aggiorna Progetto')}
                    </button>
                  )}
                </div>
              </div>
            </form>
          </div>
        </div>
      )}

      <div className="projects-ops-summary">
        <div className="ops-summary-card info">
          <span>Progetti attivi</span>
          <strong>{projectSummary.active}</strong>
          <small>Pipeline operativa corrente</small>
        </div>
        <div className="ops-summary-card warning">
          <span>In attenzione</span>
          <strong>{projectSummary.attention}</strong>
          <small>Scadenza vicina o ente mancante</small>
        </div>
        <div className="ops-summary-card critical">
          <span>Oltre termine</span>
          <strong>{projectSummary.overdue}</strong>
          <small>Ancora attivi oltre data fine</small>
        </div>
      </div>

      {!isAdmin ? (
        <div className="project-ops-note">
          Le azioni strutturali su creazione ed eliminazione progetto sono riservate agli admin. Da qui puoi comunque presidiare stato, date, ente attuatore e dati di delivery.
        </div>
      ) : null}

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
          <button
            className={`filter-button ${statusFilter === 'attention' ? 'active' : ''}`}
            onClick={() => setStatusFilter('attention')}
          >
            ⚠️ Attenzione ({projectSummary.attention + projectSummary.overdue})
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
              <div key={project.id} className={`project-card project-state-${getProjectOperationalState(project)}`}>
                {/* Header Card */}
                <div className="card-header">
                  <div className="project-title">
                    <h3>{project.name}</h3>
                    <div className="project-attention-row">
                      {getProjectOperationalState(project) === 'attention' && (
                        <span className="project-operational-pill attention">Scadenza/ente da verificare</span>
                      )}
                      {getProjectOperationalState(project) === 'overdue' && (
                        <span className="project-operational-pill overdue">Oltre data fine</span>
                      )}
                      {!project.ente_attuatore_id && (
                        <span className="project-operational-pill neutral">Ente attuatore mancante</span>
                      )}
                    </div>
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
                      hidden={!isAdmin}
                      disabled={!isAdmin}
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

                  <div className="info-row">
                    <span className="label">📄 Atto:</span>
                    <span>{project.atto_approvazione || 'Non impostato'}</span>
                  </div>

                  {(project.sede_aziendale_comune || project.sede_aziendale_via || project.sede_aziendale_numero_civico) && (
                    <div className="info-row">
                      <span className="label">🏢 Sede:</span>
                      <span>
                        {[project.sede_aziendale_via, project.sede_aziendale_numero_civico, project.sede_aziendale_comune]
                          .filter(Boolean)
                          .join(', ')}
                      </span>
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

                  {project.avviso && (
                    <div className="info-row">
                      <span className="label">📢 Avviso:</span>
                      <span>{project.avviso}</span>
                    </div>
                  )}

                  <div className="info-row">
                    <span className="label">🤝 Attuatore:</span>
                    <span>
                      {implementingEntities.find((entity) => entity.id === project.ente_attuatore_id)?.ragione_sociale || 'Non associato'}
                    </span>
                  </div>

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
                disabled={!isAdmin}
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
