/**
 * COMPONENTE GESTIONE COLLABORATORI REFACTORED
 *
 * Questa interfaccia permette di:
 * - Aggiungere nuovi collaboratori tramite form
 * - Visualizzare lista completa collaboratori
 * - Modificare collaboratori esistenti
 * - Eliminare collaboratori
 * - Gestire associazioni con progetti
 */

import React, { useMemo, useState, useCallback } from 'react';
import {
  assignCollaboratorToProject,
  removeCollaboratorFromProject,
  generateContract,
  bulkImportCollaborators
} from '../services/apiService';
import { useCollaborators, useProjects, useAssignments, useNotifications } from '../hooks/useEntity';
import useDocumentUpload from '../hooks/useDocumentUpload';
import CollaboratorForm from './collaborators/CollaboratorForm';
import CollaboratorsTable from './collaborators/CollaboratorsTable';
import CollaboratorBulkImport from './collaborators/CollaboratorBulkImport';
import AssignmentModal from './AssignmentModal';
import DocumentiCollaboratore from './DocumentiCollaboratore';
import './CollaboratorManager.css';

const CONTRACT_TYPE_LABELS = {
  professionale: 'Professionale',
  occasionale: 'Occasionale',
  ordine_servizio: 'Ordine di servizio',
  contratto_progetto: 'Contratto a progetto',
};

const ROLE_EXPERIENCE = {
  admin: {
    label: 'Amministratore',
    eyebrow: 'Controllo completo',
    summary: 'Puoi gestire anagrafiche, import, relazioni progetto e scarico contratti dopo preflight.',
  },
  manager: {
    label: 'Manager operativo',
    eyebrow: 'Coordinamento operativo',
    summary: 'Focus su assegnazioni, qualità dati contrattuali e verifica dei collaboratori in attenzione.',
  },
  user: {
    label: 'Operatore',
    eyebrow: 'Esecuzione guidata',
    summary: 'Focus su consultazione, aggiornamento dati e generazione contratti solo dopo controlli di completezza.',
  },
};

const CollaboratorManager = ({ currentUser }) => {
  // ==========================================
  // CONTEXT E HOOKS
  // ==========================================

  // Carica dati dal Context con caching automatico
  const {
    data: collaborators,
    loading: loadingCollaborators,
    error: contextError,
    refresh: refreshCollaborators,
    create: createCollab,
    update: updateCollab,
    remove: removeCollab
  } = useCollaborators();

  const { data: projects, loading: loadingProjects, refresh: refreshProjects } = useProjects();
  const { data: assignments, loading: loadingAssignments, refresh: refreshAssignments } = useAssignments();
  const { showSuccess, showError } = useNotifications();

  // Hook per gestione documenti
  const documentUploadHandlers = useDocumentUpload(showSuccess, showError, refreshCollaborators);

  // ==========================================
  // STATI LOCALI
  // ==========================================

  // Trigger per forzare refresh della tabella server-side dopo ogni operazione CRUD
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const triggerRefresh = useCallback(() => setRefreshTrigger(n => n + 1), []);

  // Stati per le assegnazioni dettagliate
  const [showAssignmentModal, setShowAssignmentModal] = useState(false);
  const [selectedCollaborator, setSelectedCollaborator] = useState(null);
  const [selectedProject, setSelectedProject] = useState(null);
  const [editingAssignment, setEditingAssignment] = useState(null);

  // Stati dell'interfaccia form
  const [editingCollaborator, setEditingCollaborator] = useState(null);
  const [showForm, setShowForm] = useState(false);

  // Stato per importazione massiva
  const [showBulkImport, setShowBulkImport] = useState(false);
  const [bulkImporting, setBulkImporting] = useState(false);

  // Stato per conferma eliminazione
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [selectedDocumentCollaborator, setSelectedDocumentCollaborator] = useState(null);
  const [contractPreflight, setContractPreflight] = useState(null);
  const [contractGenerating, setContractGenerating] = useState(false);

  // Combina gli stati di loading
  const loading = loadingCollaborators || loadingProjects || loadingAssignments;
  const isAdmin = currentUser?.role === 'admin';
  const roleExperience = ROLE_EXPERIENCE[currentUser?.role] || ROLE_EXPERIENCE.user;

  const collaboratorIndex = useMemo(
    () => new Map(collaborators.map((item) => [item.id, item])),
    [collaborators]
  );
  const projectIndex = useMemo(
    () => new Map(projects.map((item) => [item.id, item])),
    [projects]
  );

  const getContractPreflight = (assignment) => {
    const collaborator = collaboratorIndex.get(assignment.collaborator_id);
    const project = projectIndex.get(assignment.project_id);
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    const checks = [
      {
        label: 'Collaboratore associato',
        status: collaborator ? 'ok' : 'blocked',
        detail: collaborator
          ? `${collaborator.first_name} ${collaborator.last_name}`
          : 'Assegnazione senza anagrafica collaboratore caricata.',
      },
      {
        label: 'Progetto associato',
        status: project ? 'ok' : 'blocked',
        detail: project ? project.name : 'Assegnazione senza progetto valido.',
      },
      {
        label: 'Tipo contratto',
        status: assignment.contract_type ? 'ok' : 'blocked',
        detail: assignment.contract_type
          ? CONTRACT_TYPE_LABELS[assignment.contract_type] || assignment.contract_type
          : 'Manca il tipo contratto richiesto per un flusso contrattuale pulito.',
      },
      {
        label: 'Mansione',
        status: assignment.role ? 'ok' : 'blocked',
        detail: assignment.role || 'Mansione non valorizzata.',
      },
      {
        label: 'Dati economici',
        status: assignment.assigned_hours > 0 && assignment.hourly_rate > 0 ? 'ok' : 'blocked',
        detail: assignment.assigned_hours > 0 && assignment.hourly_rate > 0
          ? `${assignment.assigned_hours}h a €${assignment.hourly_rate}/h`
          : 'Ore previste o tariffa oraria mancanti/non valide.',
      },
    ];

    const startDate = assignment.start_date ? new Date(assignment.start_date) : null;
    const endDate = assignment.end_date ? new Date(assignment.end_date) : null;
    const validDates = startDate && endDate && !Number.isNaN(startDate.getTime()) && !Number.isNaN(endDate.getTime()) && endDate > startDate;
    checks.push({
      label: 'Periodo contrattuale',
      status: validDates ? 'ok' : 'blocked',
      detail: validDates
        ? `${startDate.toLocaleDateString('it-IT')} → ${endDate.toLocaleDateString('it-IT')}`
        : 'Date mancanti o intervallo non coerente.',
    });

    if (collaborator) {
      checks.push({
        label: 'Dati anagrafici essenziali',
        status: collaborator.fiscal_code && collaborator.birth_date ? 'ok' : 'warning',
        detail: collaborator.fiscal_code && collaborator.birth_date
          ? 'Codice fiscale e data di nascita presenti.'
          : 'Per alcuni template conviene completare codice fiscale e data di nascita.',
      });

      const hasIdentityDocument = Boolean(collaborator.documento_identita_filename);
      const identityExpiry = collaborator.documento_identita_scadenza ? new Date(collaborator.documento_identita_scadenza) : null;
      let documentStatus = 'warning';
      let documentDetail = 'Documento identita non caricato.';

      if (hasIdentityDocument && identityExpiry && !Number.isNaN(identityExpiry.getTime())) {
        identityExpiry.setHours(0, 0, 0, 0);
        const diffDays = Math.ceil((identityExpiry - today) / (1000 * 60 * 60 * 24));
        if (diffDays < 0) {
          documentStatus = 'blocked';
          documentDetail = `Documento scaduto il ${identityExpiry.toLocaleDateString('it-IT')}.`;
        } else if (diffDays <= 30) {
          documentStatus = 'warning';
          documentDetail = `Documento in scadenza il ${identityExpiry.toLocaleDateString('it-IT')} (${diffDays} giorni).`;
        } else {
          documentStatus = 'ok';
          documentDetail = `Documento valido fino al ${identityExpiry.toLocaleDateString('it-IT')}.`;
        }
      } else if (hasIdentityDocument) {
        documentDetail = 'Documento presente ma senza data di scadenza.';
      }

      checks.push({
        label: 'Documento identita',
        status: documentStatus,
        detail: documentDetail,
      });
    }

    if (project) {
      checks.push({
        label: 'Ente attuatore',
        status: project.ente_attuatore_id ? 'ok' : 'blocked',
        detail: project.ente_attuatore_id
          ? `Ente collegato ID ${project.ente_attuatore_id}: il backend usera template e logo configurati.`
          : 'Nessun ente attuatore collegato: il flusso template-based non puo essere eseguito.',
      });
    }

    const blockers = checks.filter((item) => item.status === 'blocked');
    const warnings = checks.filter((item) => item.status === 'warning');

    return {
      assignment,
      collaborator,
      project,
      checks,
      blockers,
      warnings,
      canGenerate: blockers.length === 0,
    };
  };

  // ==========================================
  // FUNZIONE DI REFRESH DATI
  // ==========================================

  /**
   * RICARICA TUTTI I DATI (collaboratori, progetti, assegnazioni)
   */
  const refreshAllData = async () => {
    try {
      await Promise.all([
        refreshCollaborators(),
        refreshProjects(),
        refreshAssignments()
      ]);
    } catch (err) {
      console.error('Errore ricaricamento dati:', err);
      showError('Errore nel caricamento dei dati. Riprova più tardi.');
    }
  };

  // ==========================================
  // GESTIONE FORM COLLABORATORE
  // ==========================================

  /**
   * APRI FORM PER NUOVO COLLABORATORE
   */
  const openNewCollaboratorForm = () => {
    setEditingCollaborator(null);
    setShowForm(true);
  };

  /**
   * APRI FORM PER MODIFICA COLLABORATORE
   */
  const openEditCollaboratorForm = (collaborator) => {
    // Prepara i dati per il form
    const formData = {
      first_name: collaborator.first_name,
      last_name: collaborator.last_name,
      email: collaborator.email,
      phone: collaborator.phone || '',
      position: collaborator.position || '',
      birthplace: collaborator.birthplace || '',
      birth_date: collaborator.birth_date ? collaborator.birth_date.split('T')[0] : '',
      gender: collaborator.gender || '',
      fiscal_code: collaborator.fiscal_code || '',
      partita_iva: collaborator.partita_iva || '',
      city: collaborator.city || '',
      address: collaborator.address || '',
      education: collaborator.education || '',
      profilo_professionale: collaborator.profilo_professionale || '',
      competenze_principali: collaborator.competenze_principali || '',
      certificazioni: collaborator.certificazioni || '',
      sito_web: collaborator.sito_web || '',
      portfolio_url: collaborator.portfolio_url || '',
      linkedin_url: collaborator.linkedin_url || '',
      facebook_url: collaborator.facebook_url || '',
      instagram_url: collaborator.instagram_url || '',
      tiktok_url: collaborator.tiktok_url || '',
      is_agency: Boolean(collaborator.is_agency),
      is_consultant: Boolean(collaborator.is_consultant),
    };
    formData.documento_identita_scadenza = collaborator.documento_identita_scadenza
      ? collaborator.documento_identita_scadenza.split('T')[0]
      : '';
    formData.documento_identita_filename = collaborator.documento_identita_filename || '';
    formData.curriculum_filename = collaborator.curriculum_filename || '';
    setEditingCollaborator({ id: collaborator.id, ...formData });
    setShowForm(true);
  };

  /**
   * CHIUDI FORM
   */
  const closeForm = () => {
    setEditingCollaborator(null);
    setShowForm(false);
  };

  /**
   * GESTISCI SUBMIT FORM (creazione o modifica)
   */
  const handleFormSubmit = async (collaboratorData) => {
    try {
      const {
        documento_identita_file,
        curriculum_file,
        documento_identita_scadenza,
        ...baseCollaboratorData
      } = collaboratorData;

      const payload = {
        ...baseCollaboratorData,
        documento_identita_scadenza: documento_identita_scadenza
          ? `${documento_identita_scadenza}T00:00:00Z`
          : null
      };

      let savedCollaborator;

      if (editingCollaborator) {
        // MODALITÀ MODIFICA
        savedCollaborator = await updateCollab(editingCollaborator.id, payload);
        if (documento_identita_file) {
          await documentUploadHandlers.uploadDocumento(
            editingCollaborator.id,
            documento_identita_file,
            payload.documento_identita_scadenza
          );
        }
        if (curriculum_file) {
          await documentUploadHandlers.uploadCurriculum(editingCollaborator.id, curriculum_file);
        }
        showSuccess('Collaboratore aggiornato con successo!');
      } else {
        // MODALITÀ CREAZIONE
        savedCollaborator = await createCollab(payload);
        if (documento_identita_file) {
          await documentUploadHandlers.uploadDocumento(
            savedCollaborator.id,
            documento_identita_file,
            payload.documento_identita_scadenza
          );
        }
        if (curriculum_file) {
          await documentUploadHandlers.uploadCurriculum(savedCollaborator.id, curriculum_file);
        }
        showSuccess('Collaboratore aggiunto con successo!');
      }

      // Ricarica i dati e chiudi il form
      await refreshCollaborators();
      triggerRefresh();
      closeForm();

    } catch (err) {
      console.error('Errore salvataggio:', err);
      if (err.response?.status === 409) {
        // Errore di duplicato (email o CF)
        throw new Error(err.response?.data?.detail || 'Email, Codice Fiscale o Partita IVA già esistente');
      } else if (err.response?.status === 400 || err.response?.status === 422) {
        // Errore di validazione
        throw new Error(err.response?.data?.detail || 'Dati non validi. Controlla i campi obbligatori');
      } else {
        throw new Error('Errore nel salvataggio. Riprova.');
      }
    }
  };

  // ==========================================
  // AZIONI SUI COLLABORATORI
  // ==========================================

  /**
   * ELIMINA COLLABORATORE
   */
  const handleDelete = async (collaboratorId) => {
    try {
      await removeCollab(collaboratorId);
      showSuccess('Collaboratore eliminato con successo!');
      await refreshCollaborators();
      triggerRefresh();
      setDeleteConfirm(null);
    } catch (err) {
      console.error('Errore eliminazione:', err);
      showError('Errore nell\'eliminazione. Riprova.');
    }
  };

  // ==========================================
  // GESTIONE ASSOCIAZIONI PROGETTI
  // ==========================================

  /**
   * ASSEGNA COLLABORATORE A PROGETTO
   */
  const handleAssignProject = async (collaboratorId, projectId) => {
    try {
      await assignCollaboratorToProject(collaboratorId, projectId);
      showSuccess('Collaboratore assegnato al progetto!');
      await refreshAllData();
    } catch (err) {
      console.error('Errore assegnazione:', err);
      showError('Errore nell\'assegnazione al progetto.');
    }
  };

  /**
   * RIMUOVI COLLABORATORE DA PROGETTO
   */
  const handleRemoveProject = async (collaboratorId, projectId) => {
    try {
      await removeCollaboratorFromProject(collaboratorId, projectId);
      showSuccess('Collaboratore rimosso dal progetto!');
      await refreshAllData();
    } catch (err) {
      console.error('Errore rimozione:', err);
      showError('Errore nella rimozione dal progetto.');
    }
  };

  // ==========================================
  // GESTIONE ASSEGNAZIONI DETTAGLIATE
  // ==========================================

  /**
   * APRI MODAL PER NUOVA ASSEGNAZIONE
   */
  const openNewAssignmentModal = (collaborator, project = null) => {
    setSelectedCollaborator(collaborator);
    setSelectedProject(project);
    setEditingAssignment(null);
    setShowAssignmentModal(true);
  };

  /**
   * APRI MODAL PER MODIFICA ASSEGNAZIONE
   */
  const openEditAssignmentModal = (assignment) => {
    setEditingAssignment(assignment);
    setSelectedCollaborator(null);
    setSelectedProject(null);
    setShowAssignmentModal(true);
  };

  /**
   * CHIUDI MODAL ASSEGNAZIONI
   */
  const closeAssignmentModal = () => {
    setShowAssignmentModal(false);
    setSelectedCollaborator(null);
    setSelectedProject(null);
    setEditingAssignment(null);
  };

  /**
   * GESTISCI SUCCESSO OPERAZIONI ASSEGNAZIONI
   */
  const handleAssignmentSuccess = (message) => {
    showSuccess(message);
    refreshAllData();
  };

  // ==========================================
  // GESTIONE IMPORTAZIONE MASSIVA
  // ==========================================

  /**
   * GESTISCI IMPORTAZIONE MASSIVA DA EXCEL
   */
  const handleBulkImport = async (collaboratorsData) => {
    setBulkImporting(true);

    try {
      // Usa l'endpoint di importazione massiva
      const result = await bulkImportCollaborators(collaboratorsData);

      // Refresh dei dati
      await refreshCollaborators();
      triggerRefresh();

      // Mostra risultati
      if (result.success_count > 0) {
        showSuccess(
          `Importazione completata: ${result.success_count} collaboratori su ${result.total} importati con successo!`
        );
      }

      if (result.error_count > 0) {
        // Mostra i primi 5 errori
        const errorDetails = result.errors.slice(0, 5).map(err =>
          `• ${err.name}: ${err.error}`
        ).join('\n');

        const errorMessage = `${result.error_count} collaboratori non sono stati importati:\n\n${errorDetails}${
          result.errors.length > 5 ? '\n\n... e altri errori' : ''
        }`;

        showError(errorMessage);
        console.error('Dettagli errori importazione:', result.errors);
      }

      // Chiudi il modal se tutti sono stati importati
      if (result.error_count === 0) {
        setShowBulkImport(false);
      }

    } catch (err) {
      console.error('Errore generale importazione:', err);
      const errorMsg = err.response?.data?.detail || err.message || 'Errore sconosciuto';
      showError(`Errore durante l'importazione massiva: ${errorMsg}`);
    } finally {
      setBulkImporting(false);
    }
  };

  const closeContractPreflight = () => {
    setContractPreflight(null);
    setContractGenerating(false);
  };

  const downloadContract = async (assignment) => {
    const extractBlobErrorMessage = async (error) => {
      const responseData = error?.response?.data;

      if (responseData instanceof Blob) {
        const text = await responseData.text();
        if (!text) {
          return 'Errore nella generazione del contratto. Riprova.';
        }

        try {
          const parsed = JSON.parse(text);
          return parsed?.detail || parsed?.message || text;
        } catch {
          return text;
        }
      }

      return error?.response?.data?.detail || error?.message || 'Errore nella generazione del contratto. Riprova.';
    };

    let previewWindow = null;

    try {
      setContractGenerating(true);
      showSuccess('Apertura contratto in corso...');
      previewWindow = window.open('', '_blank', 'noopener,noreferrer');

      if (previewWindow) {
        previewWindow.document.title = 'Generazione contratto...';
        previewWindow.document.body.innerHTML = '<p style="font-family: sans-serif; padding: 24px;">Generazione contratto in corso...</p>';
      }

      const project = projectIndex.get(assignment.project_id);
      const collaborator = collaboratorIndex.get(assignment.collaborator_id);
      if (!project?.ente_attuatore_id) {
        throw new Error('Progetto senza ente attuatore: impossibile generare il contratto template-based.');
      }

      if (!assignment.contract_type) {
        throw new Error('Tipo contratto mancante: impossibile selezionare il template di default.');
      }

      const responseBlob = await generateContract({
        collaboratore_id: assignment.collaborator_id,
        progetto_id: assignment.project_id,
        ente_attuatore_id: project.ente_attuatore_id,
        mansione: assignment.role,
        ore_previste: assignment.assigned_hours,
        tariffa_oraria: assignment.hourly_rate,
        data_inizio: assignment.start_date,
        data_fine: assignment.end_date,
        contract_signed_date: assignment.contract_signed_date || null,
        tipo_contratto: assignment.contract_type,
      });

      const pdfBlob = responseBlob instanceof Blob
        ? responseBlob
        : new Blob([responseBlob], { type: 'application/pdf' });

      if (pdfBlob.type && !pdfBlob.type.includes('pdf')) {
        const text = await pdfBlob.text();
        try {
          const parsed = JSON.parse(text);
          throw new Error(parsed?.detail || parsed?.message || 'Il server non ha restituito un PDF valido.');
        } catch {
          throw new Error(text || 'Il server non ha restituito un PDF valido.');
        }
      }

      const collaboratorName = (collaborator?.last_name && collaborator?.first_name)
        ? `${collaborator.last_name}_${collaborator.first_name}`.replace(/\s/g, '_')
        : 'collaboratore';
      const projectName = project?.name
        ? project.name.replace(/\s/g, '_')
        : 'progetto';
      const filename = `contratto_${collaboratorName}_${projectName}.pdf`;

      const url = window.URL.createObjectURL(pdfBlob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';

      if (previewWindow) {
        previewWindow.location.href = url;
      } else {
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      }

      window.setTimeout(() => window.URL.revokeObjectURL(url), 60000);
      showSuccess('Contratto aperto con successo!');
      closeContractPreflight();
    } catch (err) {
      if (previewWindow && !previewWindow.closed) {
        previewWindow.close();
      }
      console.error('Errore generazione contratto:', err);
      const errorMessage = await extractBlobErrorMessage(err);
      showError(errorMessage);
    } finally {
      setContractGenerating(false);
    }
  };

  /**
   * SCARICA IL CONTRATTO PDF PER UNA ASSEGNAZIONE
   */
  const handleDownloadContract = async (assignment) => {
    setContractPreflight(getContractPreflight(assignment));
  };

  const handleOpenDocuments = (collaborator) => {
    setSelectedDocumentCollaborator((current) => (
      current?.id === collaborator.id ? null : collaborator
    ));
  };

  // ==========================================
  // RENDER DEL COMPONENTE
  // ==========================================

  if (loading && collaborators.length === 0) {
    return (
      <div className="collaborator-manager">
        <div className="loading">
          <div className="spinner"></div>
          <p>Caricamento collaboratori...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="collaborator-manager">
      {/* INTESTAZIONE */}
      <div className="manager-header">
        <h1>👥 Gestione Collaboratori</h1>
        <p>Aggiungi, modifica e gestisci tutti i collaboratori del sistema</p>

        <div className="role-operations-banner">
          <div>
            <span className="role-operations-eyebrow">{roleExperience.eyebrow}</span>
            <strong>{roleExperience.label}</strong>
          </div>
          <p>{roleExperience.summary}</p>
        </div>

        <div className="header-buttons">
          <button
            className={`add-button ${showForm ? 'active' : ''}`}
            onClick={() => {
              if (showForm) {
                closeForm();
              } else {
                setShowBulkImport(false); // Chiudi import se aperto
                openNewCollaboratorForm();
              }
            }}
          >
            {showForm ? '❌ Chiudi Form' : '➕ Nuovo Collaboratore'}
          </button>

          <button
            className={`import-button ${showBulkImport ? 'active' : ''}`}
            onClick={() => {
              if (showBulkImport) {
                setShowBulkImport(false);
              } else {
                closeForm(); // Chiudi form se aperto
                setShowBulkImport(true);
              }
            }}
            disabled={bulkImporting}
            hidden={!isAdmin}
          >
            {showBulkImport ? '❌ Chiudi Import' : '📥 Importa Excel'}
          </button>
        </div>
      </div>

      {/* MESSAGGI DI STATO */}
      {contextError && (
        <div className="message error-message">
          ⚠️ {contextError.message || 'Errore nel caricamento dei dati'}
        </div>
      )}

      {/* FORM AGGIUNTA/MODIFICA */}
      {showForm && (
        <div className="modal-overlay collaborator-form-overlay" onClick={(event) => event.target === event.currentTarget && closeForm()}>
          <div className="collaborator-form-modal">
            <CollaboratorForm
              key={editingCollaborator?.id || 'new-collaborator'}
              initialData={editingCollaborator}
              onSubmit={handleFormSubmit}
              onCancel={closeForm}
              isLoading={loading || documentUploadHandlers.uploadingDocumento || documentUploadHandlers.uploadingCurriculum}
              documentActions={documentUploadHandlers}
            />
          </div>
        </div>
      )}

      {/* IMPORTAZIONE MASSIVA */}
      {showBulkImport && (
        <CollaboratorBulkImport
          onImport={handleBulkImport}
          onClose={() => setShowBulkImport(false)}
          isLoading={bulkImporting}
        />
      )}

      {/* TABELLA COLLABORATORI */}
      <CollaboratorsTable
        projects={projects}
        assignments={assignments}
        currentUser={currentUser}
        onEdit={openEditCollaboratorForm}
        onDelete={setDeleteConfirm}
        onOpenDocuments={handleOpenDocuments}
        onOpenAssignmentModal={openNewAssignmentModal}
        onAssignProject={handleAssignProject}
        onRemoveProject={handleRemoveProject}
        onEditAssignment={openEditAssignmentModal}
        onDownloadContract={handleDownloadContract}
        refreshTrigger={refreshTrigger}
      />

      {selectedDocumentCollaborator && (
        <div style={{ marginTop: '1.5rem' }}>
          <DocumentiCollaboratore
            collaboratore_id={selectedDocumentCollaborator.id}
            currentUser={currentUser}
            onUpdated={refreshCollaborators}
          />
        </div>
      )}

      {contractPreflight && (
        <div className="modal-overlay" onClick={(event) => event.target === event.currentTarget && closeContractPreflight()}>
          <div className="contract-preflight-modal">
            <div className="contract-preflight-header">
              <div>
                <span className="contract-preflight-eyebrow">Contract Preflight</span>
                <h3>Verifica prima della generazione PDF</h3>
                <p>
                  {contractPreflight.collaborator
                    ? `${contractPreflight.collaborator.first_name} ${contractPreflight.collaborator.last_name}`
                    : 'Collaboratore non disponibile'}
                  {' · '}
                  {contractPreflight.project?.name || 'Progetto non disponibile'}
                </p>
              </div>
              <button type="button" className="close-button" onClick={closeContractPreflight}>✕</button>
            </div>

            <div className="contract-preflight-summary">
              <div className={`preflight-summary-card ${contractPreflight.canGenerate ? 'ready' : 'blocked'}`}>
                <span>Esito</span>
                <strong>{contractPreflight.canGenerate ? 'Pronto' : 'Bloccato'}</strong>
                <small>
                  {contractPreflight.canGenerate
                    ? 'Puoi procedere alla generazione del contratto.'
                    : 'Completa prima i punti bloccanti evidenziati sotto.'}
                </small>
              </div>
              <div className="preflight-summary-card warning">
                <span>Warning</span>
                <strong>{contractPreflight.warnings.length}</strong>
                <small>Elementi da rifinire per un output più solido.</small>
              </div>
              <div className="preflight-summary-card neutral">
                <span>Tipo contratto</span>
                <strong>{CONTRACT_TYPE_LABELS[contractPreflight.assignment.contract_type] || 'Non impostato'}</strong>
                <small>
                  {contractPreflight.project?.ente_attuatore_id
                    ? 'Flusso template-based attivo lato backend.'
                    : 'Serve associare un ente attuatore prima di generare il contratto.'}
                </small>
              </div>
            </div>

            <div className="preflight-checks">
              {contractPreflight.checks.map((check) => (
                <div key={check.label} className={`preflight-check ${check.status}`}>
                  <div className="preflight-check-status">
                    {check.status === 'ok' && 'OK'}
                    {check.status === 'warning' && 'WARN'}
                    {check.status === 'blocked' && 'STOP'}
                  </div>
                  <div>
                    <strong>{check.label}</strong>
                    <p>{check.detail}</p>
                  </div>
                </div>
              ))}
            </div>

            <div className="contract-preflight-actions">
              <button type="button" className="cancel-button" onClick={closeContractPreflight}>
                Chiudi
              </button>
              <button
                type="button"
                className="generate-button"
                onClick={() => downloadContract(contractPreflight.assignment)}
                disabled={!contractPreflight.canGenerate || contractGenerating}
              >
                {contractGenerating ? 'Generazione in corso...' : 'Genera contratto PDF'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL CONFERMA ELIMINAZIONE */}
      {deleteConfirm && (
        <div className="modal-overlay">
          <div className="confirm-modal">
            <h3>⚠️ Conferma Eliminazione</h3>
            <p>Sei sicuro di voler eliminare questo collaboratore?</p>
            <p><strong>Questa azione non può essere annullata!</strong></p>

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

      {/* MODAL GESTIONE ASSEGNAZIONI */}
      <AssignmentModal
        isOpen={showAssignmentModal}
        onClose={closeAssignmentModal}
        onSuccess={handleAssignmentSuccess}
        collaborator={selectedCollaborator}
        project={selectedProject}
        assignment={editingAssignment}
        availableProjects={projects}
        availableCollaborators={collaborators}
      />
    </div>
  );
};

export default CollaboratorManager;
