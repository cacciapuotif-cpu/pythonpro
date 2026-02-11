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

import React, { useState } from 'react';
import {
  assignCollaboratorToProject,
  removeCollaboratorFromProject,
  generateContractPdf,
  bulkImportCollaborators
} from '../services/apiService';
import { useCollaborators, useProjects, useAssignments, useNotifications } from '../hooks/useEntity';
import useDocumentUpload from '../hooks/useDocumentUpload';
import CollaboratorForm from './collaborators/CollaboratorForm';
import CollaboratorsTable from './collaborators/CollaboratorsTable';
import CollaboratorBulkImport from './collaborators/CollaboratorBulkImport';
import AssignmentModal from './AssignmentModal';
import './CollaboratorManager.css';

const CollaboratorManager = () => {
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

  // Combina gli stati di loading
  const loading = loadingCollaborators || loadingProjects || loadingAssignments;

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
      city: collaborator.city || '',
      address: collaborator.address || '',
      education: collaborator.education || ''
    };
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
      if (editingCollaborator) {
        // MODALITÀ MODIFICA
        await updateCollab(editingCollaborator.id, collaboratorData);
        showSuccess('Collaboratore aggiornato con successo!');
      } else {
        // MODALITÀ CREAZIONE
        await createCollab(collaboratorData);
        showSuccess('Collaboratore aggiunto con successo!');
      }

      // Ricarica i dati e chiudi il form
      await refreshCollaborators();
      closeForm();

    } catch (err) {
      console.error('Errore salvataggio:', err);
      if (err.response?.status === 409) {
        // Errore di duplicato (email o CF)
        throw new Error(err.response?.data?.detail || 'Email o Codice Fiscale già esistente');
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

  /**
   * SCARICA IL CONTRATTO PDF PER UNA ASSEGNAZIONE
   */
  const handleDownloadContract = async (assignment) => {
    try {
      showSuccess('Generazione contratto in corso...');

      // Chiama l'API per generare il PDF
      const pdfBlob = await generateContractPdf(assignment.id);

      // Crea un nome file descrittivo
      const collaboratorName = (assignment.collaborator?.last_name && assignment.collaborator?.first_name)
        ? `${assignment.collaborator.last_name}_${assignment.collaborator.first_name}`.replace(/\s/g, '_')
        : 'collaboratore';
      const projectName = assignment.project?.name
        ? assignment.project.name.replace(/\s/g, '_')
        : 'progetto';

      const safeCollaboratorName = (collaboratorName && collaboratorName !== 'null' && collaboratorName !== 'undefined')
        ? collaboratorName
        : 'collaboratore';
      const safeProjectName = (projectName && projectName !== 'null' && projectName !== 'undefined')
        ? projectName
        : 'progetto';
      const filename = `contratto_${safeCollaboratorName}_${safeProjectName}.pdf`;

      // Download del file
      const url = window.URL.createObjectURL(pdfBlob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);

      showSuccess('Contratto scaricato con successo!');
    } catch (err) {
      console.error('Errore generazione contratto:', err);
      showError('Errore nella generazione del contratto. Riprova.');
    }
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
        <CollaboratorForm
          initialData={editingCollaborator}
          onSubmit={handleFormSubmit}
          onCancel={closeForm}
          isLoading={loading}
        />
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
        collaborators={collaborators}
        projects={projects}
        assignments={assignments}
        onEdit={openEditCollaboratorForm}
        onDelete={setDeleteConfirm}
        onOpenAssignmentModal={openNewAssignmentModal}
        onAssignProject={handleAssignProject}
        onRemoveProject={handleRemoveProject}
        onEditAssignment={openEditAssignmentModal}
        onDownloadContract={handleDownloadContract}
      />

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
