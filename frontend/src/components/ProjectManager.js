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
import { getAvvisi, getAvvisiPianoFinanziario, getTemplatePianiFinanziari, getAziendeClienti, getAllievi } from '../services/apiService';
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
    description: 'Sede operativa, ente attuatore, aziende coinvolte e collegamento gerarchico template -> avviso piano.',
    fields: ['sede_aziendale_comune', 'sede_aziendale_via', 'sede_aziendale_numero_civico', 'ente_attuatore_id', 'azienda_ids', 'template_piano_finanziario_id', 'avviso_pf_id'],
  },
];

const normalizeText = (value) => String(value || '').trim().toLowerCase();
const formatTipoFondo = (value) => {
  const normalized = normalizeText(value);
  const mapping = {
    formazienda: 'FORMAZIENDA',
    fapi: 'FAPI',
    fondimpresa: 'FONDIMPRESA',
    fse: 'FSE',
  };
  return mapping[normalized] || String(value || '').trim().toUpperCase();
};

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
    avviso_pf_id: '',
    avviso_selection: '',
    template_piano_finanziario_id: '',
    azienda_ids: [],
    allievo_ids: [],
    ente_attuatore_id: null // NUOVO: FK verso ente attuatore
  });
  const [financialTemplates, setFinancialTemplates] = useState([]);
  const [avvisiCatalogo, setAvvisiCatalogo] = useState([]);
  const [legacyAvvisi, setLegacyAvvisi] = useState([]);
  const [aziendaOptions, setAziendaOptions] = useState([]);
  const [aziendaToAdd, setAziendaToAdd] = useState('');
  const [allievoOptions, setAllievoOptions] = useState([]);
  const [allievoToAdd, setAllievoToAdd] = useState('');

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
        const [data, avvisi, legacyAvvisiData, aziendeData, allieviData] = await Promise.all([
          getTemplatePianiFinanziari({
            solo_attivi: true,
            limit: 200,
          }),
          getAvvisiPianoFinanziario({ limit: 200 }),
          getAvvisi({ active_only: true, limit: 1000 }),
          getAziendeClienti({ limit: 100, page: 1 }),
          getAllievi({ limit: 100, page: 1 }),
        ]);
        if (!cancelled) {
          setFinancialTemplates(Array.isArray(data) ? data : []);
          setAvvisiCatalogo(Array.isArray(avvisi) ? avvisi : []);
          setLegacyAvvisi(Array.isArray(legacyAvvisiData) ? legacyAvvisiData : []);
          setAziendaOptions(Array.isArray(aziendeData?.items) ? aziendeData.items : (Array.isArray(aziendeData) ? aziendeData : []));
          setAllievoOptions(Array.isArray(allieviData?.items) ? allieviData.items : (Array.isArray(allieviData) ? allieviData : []));
        }
      } catch (error) {
        if (!cancelled) {
          setFinancialTemplates([]);
          setAvvisiCatalogo([]);
          setLegacyAvvisi([]);
          setAziendaOptions([]);
          setAllievoOptions([]);
        }
      }
    };

    loadFinancialTemplates();
    return () => {
      cancelled = true;
    };
  }, []);

  const avvisiOptions = useMemo(() => {
    const seen = new Set();
    const nextOptions = [];

    avvisiCatalogo.forEach((item) => {
      const key = `${item.template_id || ''}:${normalizeText(item.codice_avviso)}`;
      if (seen.has(key)) {
        return;
      }
      seen.add(key);
      nextOptions.push({
        source: 'pf',
        optionKey: `pf:${item.id}`,
        id: item.id,
        template_id: item.template_id,
        codice: item.codice_avviso,
        titolo: item.titolo,
        ente_erogatore: formatTipoFondo(
          financialTemplates.find((template) => String(template.id) === String(item.template_id))?.tipo_fondo || ''
        ),
      });
    });

    legacyAvvisi.forEach((item) => {
      const normalizedEnte = normalizeText(item.ente_erogatore);
      const inferredTemplate = financialTemplates.find(
        (template) => normalizeText(template.tipo_fondo) === normalizedEnte
      ) || null;
      const key = `${inferredTemplate?.id || ''}:${normalizeText(item.codice)}`;
      if (seen.has(key)) {
        return;
      }
      seen.add(key);
      nextOptions.push({
        source: 'legacy',
        optionKey: `legacy:${item.id}`,
        id: item.id,
        template_id: inferredTemplate?.id || null,
        codice: item.codice,
        titolo: item.descrizione || item.codice,
        ente_erogatore: item.ente_erogatore,
      });
    });

    return nextOptions.sort((a, b) => {
      const enteCompare = String(a.ente_erogatore || '').localeCompare(String(b.ente_erogatore || ''));
      if (enteCompare !== 0) {
        return enteCompare;
      }
      return String(a.codice || '').localeCompare(String(b.codice || ''));
    });
  }, [avvisiCatalogo, financialTemplates, legacyAvvisi]);

  const getTemplateLinkedAvvisi = (templateId) =>
    avvisiOptions.filter((item) => String(item.template_id || '') === String(templateId));

  const getTemplateAvvisoCodes = (template) =>
    getTemplateLinkedAvvisi(template?.id).map((item) => item.codice_avviso).filter(Boolean);

  const selectedFinancialTemplate = financialTemplates.find(
    (template) => String(template.id) === String(formData.template_piano_finanziario_id),
  );
  const selectedAvvisoOption = avvisiOptions.find(
    (avviso) => avviso.optionKey === formData.avviso_selection,
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
      const currentAvviso = linkedAvvisi.find((item) => item.optionKey === formData.avviso_selection);
      const linkedAvviso = currentAvviso || linkedAvvisi[0] || null;
      setFormData(prev => ({
        ...prev,
        template_piano_finanziario_id: value,
        ...(nextTemplate ? {
          ente_erogatore: formatTipoFondo(nextTemplate.tipo_fondo),
          avviso: linkedAvviso?.codice || '',
          avviso_pf_id: linkedAvviso?.source === 'pf' ? String(linkedAvviso.id) : '',
          avviso_id: linkedAvviso?.source === 'legacy' ? String(linkedAvviso.id) : '',
          avviso_selection: linkedAvviso?.optionKey || '',
        } : {
          ente_erogatore: '',
          avviso: '',
          avviso_pf_id: '',
          avviso_id: '',
          avviso_selection: '',
        })
      }));
      return;
    }

    if (name === 'avviso_selection') {
      const selected = avvisiOptions.find((a) => a.optionKey === value);
      const template = financialTemplates.find((item) => String(item.id) === String(selected?.template_id || ''));
      setFormData(prev => ({
        ...prev,
        avviso_selection: value,
        avviso_pf_id: selected?.source === 'pf' ? String(selected.id) : '',
        avviso_id: selected?.source === 'legacy' ? String(selected.id) : '',
        avviso: selected?.codice || '',
        template_piano_finanziario_id: template ? String(template.id) : prev.template_piano_finanziario_id,
        ente_erogatore: template ? formatTipoFondo(template.tipo_fondo) : (selected?.ente_erogatore || prev.ente_erogatore),
      }));
      return;
    }

    setFormData(prev => ({
      ...prev,
      [name]: value,
    }));
  };

  const handleAddAzienda = () => {
    const selectedId = Number(aziendaToAdd);
    if (!selectedId) {
      return;
    }

    setFormData((prev) => {
      if (prev.azienda_ids.includes(selectedId)) {
        return prev;
      }
      return {
        ...prev,
        azienda_ids: [...prev.azienda_ids, selectedId],
      };
    });
    setAziendaToAdd('');
  };

  const handleRemoveAzienda = (aziendaIdToRemove) => {
    setFormData((prev) => ({
      ...prev,
      azienda_ids: prev.azienda_ids.filter((aziendaId) => aziendaId !== aziendaIdToRemove),
    }));
  };

  const handleAddAllievo = () => {
    const selectedId = Number(allievoToAdd);
    if (!selectedId) {
      return;
    }

    setFormData((prev) => {
      if (prev.allievo_ids.includes(selectedId)) {
        return prev;
      }
      return {
        ...prev,
        allievo_ids: [...prev.allievo_ids, selectedId],
      };
    });
    setAllievoToAdd('');
  };

  const handleRemoveAllievo = (allievoIdToRemove) => {
    setFormData((prev) => ({
      ...prev,
      allievo_ids: prev.allievo_ids.filter((allievoId) => allievoId !== allievoIdToRemove),
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
        azienda_ids: Array.isArray(formData.azienda_ids) ? formData.azienda_ids.map((id) => parseInt(id, 10)) : [],
        allievo_ids: Array.isArray(formData.allievo_ids) ? formData.allievo_ids.map((id) => parseInt(id, 10)) : [],
        start_date: formData.start_date ? `${formData.start_date}T00:00:00Z` : null,
        end_date: formData.end_date ? `${formData.end_date}T23:59:59Z` : null,
        ente_erogatore: formData.ente_erogatore || null,
        avviso: formData.avviso || null,
        avviso_id: formData.avviso_id ? parseInt(formData.avviso_id, 10) : null,
        avviso_pf_id: formData.avviso_pf_id ? parseInt(formData.avviso_pf_id, 10) : null,
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
      avviso_pf_id: '',
      avviso_selection: '',
      template_piano_finanziario_id: '',
      azienda_ids: [],
      allievo_ids: [],
      ente_attuatore_id: null
    });
    setAziendaToAdd('');
    setAllievoToAdd('');
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
      avviso_pf_id: project.avviso_pf_id ? String(project.avviso_pf_id) : '',
      avviso_selection: project.avviso_pf_id ? `pf:${project.avviso_pf_id}` : (project.avviso_id ? `legacy:${project.avviso_id}` : ''),
      template_piano_finanziario_id: project.template_piano_finanziario_id ? String(project.template_piano_finanziario_id) : '',
      azienda_ids: Array.isArray(project.azienda_ids) ? project.azienda_ids.map((id) => Number(id)) : [],
      allievo_ids: Array.isArray(project.allievo_ids) ? project.allievo_ids.map((id) => Number(id)) : [],
      ente_attuatore_id: project.ente_attuatore_id || null
    });
    setAziendaToAdd('');
    setAllievoToAdd('');
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
    formData.template_piano_finanziario_id,
    formData.avviso_selection || formData.avviso_pf_id || formData.avviso_id,
    formData.cup,
    formData.atto_approvazione,
    formData.sede_aziendale_comune,
    formData.sede_aziendale_via,
    formData.sede_aziendale_numero_civico,
    formData.ente_attuatore_id,
    formData.azienda_ids.length > 0 ? 'aziende' : '',
    formData.allievo_ids.length > 0 ? 'allievi' : '',
  ].filter((value) => `${value ?? ''}`.trim() !== '').length;
  const completionPercentage = Math.round((completedFields / 14) * 100);
  const currentStep = PROJECT_FORM_STEPS[activeStepIndex];
  const selectedEntity = implementingEntities.find((entity) => String(entity.id) === String(formData.ente_attuatore_id));
  const avvisiFiltrati = selectedFinancialTemplate ? getTemplateLinkedAvvisi(selectedFinancialTemplate.id) : avvisiOptions;
  const selectedAziende = formData.azienda_ids
    .map((aziendaId) => aziendaOptions.find((azienda) => Number(azienda.id) === Number(aziendaId)))
    .filter(Boolean);
  const availableAziende = aziendaOptions.filter(
    (azienda) => !formData.azienda_ids.includes(Number(azienda.id))
  );
  const selectedAllievi = formData.allievo_ids
    .map((allievoId) => allievoOptions.find((allievo) => Number(allievo.id) === Number(allievoId)))
    .filter(Boolean);
  const availableAllievi = allievoOptions.filter(
    (allievo) => !formData.allievo_ids.includes(Number(allievo.id))
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
                  <li className={formData.azienda_ids.length > 0 ? 'done' : ''}>
                    Aziende coinvolte {formData.azienda_ids.length > 0 ? 'associate' : 'non associate'}
                  </li>
                  <li className={formData.allievo_ids.length > 0 ? 'done' : ''}>
                    Allievi coinvolti {formData.allievo_ids.length > 0 ? 'associati' : 'non associati'}
                  </li>
                  <li className={formData.template_piano_finanziario_id ? 'done' : ''}>
                    Template piano {formData.template_piano_finanziario_id ? 'selezionato' : 'non selezionato'}
                  </li>
                  <li className={(formData.avviso_selection || formData.avviso_pf_id || formData.avviso_id) ? 'done' : ''}>
                    Avviso piano {(formData.avviso_selection || formData.avviso_pf_id || formData.avviso_id) ? 'selezionato' : 'non selezionato'}
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

                      <div className="form-group full-width">
                        <label htmlFor="azienda_coinvolta">Aziende coinvolte</label>
                        <div className="project-company-picker">
                          <select
                            id="azienda_coinvolta"
                            value={aziendaToAdd}
                            onChange={(e) => setAziendaToAdd(e.target.value)}
                          >
                            <option value="">Seleziona azienda cliente</option>
                            {availableAziende.map((azienda) => (
                              <option key={azienda.id} value={azienda.id}>
                                {azienda.ragione_sociale}
                                {azienda.partita_iva ? ` · ${azienda.partita_iva}` : ''}
                              </option>
                            ))}
                          </select>
                          <button
                            type="button"
                            className="secondary-button"
                            onClick={handleAddAzienda}
                            disabled={!aziendaToAdd}
                          >
                            Aggiungi azienda
                          </button>
                        </div>
                        <small className="field-hint">
                          Le aziende aggiunte qui compariranno anche nella loro scheda, sotto i progetti associati.
                        </small>
                        <div className="project-company-list">
                          {selectedAziende.length > 0 ? (
                            selectedAziende.map((azienda) => (
                              <div key={azienda.id} className="project-company-item">
                                <div>
                                  <strong>{azienda.ragione_sociale}</strong>
                                  {azienda.partita_iva ? <small>{azienda.partita_iva}</small> : null}
                                </div>
                                <button
                                  type="button"
                                  className="delete-button"
                                  onClick={() => handleRemoveAzienda(Number(azienda.id))}
                                  title="Rimuovi azienda"
                                >
                                  Rimuovi
                                </button>
                              </div>
                            ))
                          ) : (
                            <div className="project-company-empty">
                              Nessuna azienda collegata a questo progetto.
                            </div>
                          )}
                        </div>
                      </div>

                      <div className="form-group full-width">
                        <label htmlFor="allievo_coinvolto">Allievi coinvolti</label>
                        <div className="project-company-picker">
                          <select
                            id="allievo_coinvolto"
                            value={allievoToAdd}
                            onChange={(e) => setAllievoToAdd(e.target.value)}
                          >
                            <option value="">Seleziona allievo</option>
                            {availableAllievi.map((allievo) => (
                              <option key={allievo.id} value={allievo.id}>
                                {allievo.nome} {allievo.cognome}
                                {allievo.email ? ` · ${allievo.email}` : ''}
                              </option>
                            ))}
                          </select>
                          <button
                            type="button"
                            className="secondary-button"
                            onClick={handleAddAllievo}
                            disabled={!allievoToAdd}
                          >
                            Aggiungi allievo
                          </button>
                        </div>
                        <small className="field-hint">
                          Gli allievi associati qui compariranno anche nella loro scheda, tra i progetti collegati.
                        </small>
                        <div className="project-company-list">
                          {selectedAllievi.length > 0 ? (
                            selectedAllievi.map((allievo) => (
                              <div key={allievo.id} className="project-company-item">
                                <div>
                                  <strong>{allievo.nome} {allievo.cognome}</strong>
                                  {allievo.email ? <small>{allievo.email}</small> : null}
                                </div>
                                <button
                                  type="button"
                                  className="delete-button"
                                  onClick={() => handleRemoveAllievo(Number(allievo.id))}
                                  title="Rimuovi allievo"
                                >
                                  Rimuovi
                                </button>
                              </div>
                            ))
                          ) : (
                            <div className="project-company-empty">
                              Nessun allievo collegato a questo progetto.
                            </div>
                          )}
                        </div>
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
                              {template.nome}
                              {template.tipo_fondo ? ` · ${formatTipoFondo(template.tipo_fondo)}` : ''}
                              {getTemplateAvvisoCodes(template).length > 0 ? ` · Avvisi ${getTemplateAvvisoCodes(template).join(', ')}` : ''}
                            </option>
                          ))}
                        </select>
                        <small className="field-hint">
                          Seleziona il template economico principale del progetto.
                        </small>
                      </div>

                      <div className="form-group">
                        <label htmlFor="avviso_selection">Avviso Piano</label>
                        <select
                          id="avviso_selection"
                          name="avviso_selection"
                          value={formData.avviso_selection}
                          onChange={handleInputChange}
                        >
                          <option value="">Seleziona avviso</option>
                          {avvisiFiltrati.map((avvisoItem) => (
                            <option key={avvisoItem.optionKey} value={avvisoItem.optionKey}>
                              {avvisoItem.codice}
                              {avvisoItem.ente_erogatore ? ` · ${avvisoItem.ente_erogatore}` : ''}
                              {avvisoItem.source === 'legacy' ? ' · legacy' : ''}
                            </option>
                          ))}
                        </select>
                        <small className="field-hint">
                          {selectedFinancialTemplate
                            ? 'Avvisi filtrati dal template selezionato.'
                            : 'Puoi selezionare prima l’avviso: il template verra collegato automaticamente quando possibile.'}
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
                            {financialTemplates.find((template) => String(template.id) === String(formData.template_piano_finanziario_id))?.nome || 'Non impostato'}
                          </strong>
                        </div>
                        <div>
                          <span>Aziende coinvolte</span>
                          <strong>{selectedAziende.length > 0 ? selectedAziende.map((azienda) => azienda.ragione_sociale).join(', ') : 'Non impostate'}</strong>
                        </div>
                        <div>
                          <span>Allievi coinvolti</span>
                          <strong>{selectedAllievi.length > 0 ? selectedAllievi.map((allievo) => `${allievo.nome} ${allievo.cognome}`).join(', ') : 'Non impostati'}</strong>
                        </div>
                        <div>
                          <span>Ente erogatore</span>
                          <strong>{formData.ente_erogatore || (selectedFinancialTemplate ? formatTipoFondo(selectedFinancialTemplate.tipo_fondo) : 'Non impostato')}</strong>
                        </div>
                        <div>
                          <span>Avviso</span>
                          <strong>{selectedAvvisoOption?.codice || formData.avviso || 'Non impostato'}</strong>
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

                  <div className="info-row info-row-multi">
                    <span className="label">🏢 Aziende coinvolte:</span>
                    <span>
                      {Array.isArray(project.aziende_coinvolte) && project.aziende_coinvolte.length > 0
                        ? project.aziende_coinvolte.map((azienda) => azienda.ragione_sociale).join(', ')
                        : 'Nessuna azienda associata'}
                    </span>
                  </div>

                  <div className="info-row info-row-multi">
                    <span className="label">🎓 Allievi:</span>
                    <span>
                      {Array.isArray(project.allievi_coinvolti) && project.allievi_coinvolti.length > 0
                        ? project.allievi_coinvolti.map((allievo) => `${allievo.nome} ${allievo.cognome}`).join(', ')
                        : 'Nessun allievo associato'}
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
