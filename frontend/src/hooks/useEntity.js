/**
 * Custom hooks per facilitare l'uso di AppContext
 * Forniscono interfacce semplificate per operazioni CRUD
 */

import { useCallback, useEffect } from 'react';
import { useAppContext } from '../context/AppContext';

/**
 * Hook generico per gestire una singola entità
 * @param {string} entityType - Tipo di entità (collaborators, projects, etc.)
 * @returns {Object} - Stato e funzioni per gestire l'entità
 */
export const useEntity = (entityType) => {
  const { state, fetchEntity, createEntity, updateEntity, deleteEntity, updateFilters } = useAppContext();

  const entityState = state[entityType];

  // Fetch automatico al mount se non ci sono dati
  useEffect(() => {
    if (!entityState.data.length && !entityState.loading && !entityState.lastFetch) {
      fetchEntity(entityType);
    }
  }, [entityType, fetchEntity, entityState.data.length, entityState.loading, entityState.lastFetch]);

  const refresh = useCallback(() => {
    return fetchEntity(entityType, true);
  }, [entityType, fetchEntity]);

  const create = useCallback((data) => {
    return createEntity(entityType, data);
  }, [entityType, createEntity]);

  const update = useCallback((id, data) => {
    return updateEntity(entityType, id, data);
  }, [entityType, updateEntity]);

  const remove = useCallback((id) => {
    return deleteEntity(entityType, id);
  }, [entityType, deleteEntity]);

  const setFilters = useCallback((filters) => {
    updateFilters(entityType, filters);
  }, [entityType, updateFilters]);

  return {
    data: entityState.data,
    loading: entityState.loading,
    error: entityState.error,
    filters: entityState.filters,
    pagination: entityState.pagination,
    refresh,
    create,
    update,
    remove,
    setFilters
  };
};

/**
 * Hook specifico per collaboratori
 */
export const useCollaborators = () => {
  return useEntity('collaborators');
};

/**
 * Hook specifico per progetti
 */
export const useProjects = () => {
  return useEntity('projects');
};

/**
 * Hook specifico per presenze
 */
export const useAttendances = () => {
  return useEntity('attendances');
};

/**
 * Hook specifico per assegnazioni
 */
export const useAssignments = () => {
  return useEntity('assignments');
};

/**
 * Hook specifico per enti attuatori
 */
export const useImplementingEntities = () => {
  return useEntity('implementing_entities');
};

/**
 * Hook specifico per template contratti
 */
export const useContractTemplates = () => {
  return useEntity('contract_templates');
};

/**
 * Hook per gestire le notifiche
 */
export const useNotifications = () => {
  const { state, addNotification, removeNotification } = useAppContext();

  const showSuccess = useCallback((message, title = 'Successo') => {
    addNotification({
      type: 'success',
      title,
      message,
      autoHide: true,
      duration: 3000
    });
  }, [addNotification]);

  const showError = useCallback((message, title = 'Errore') => {
    addNotification({
      type: 'error',
      title,
      message,
      autoHide: false,
      duration: 5000
    });
  }, [addNotification]);

  const showInfo = useCallback((message, title = 'Info') => {
    addNotification({
      type: 'info',
      title,
      message,
      autoHide: true,
      duration: 4000
    });
  }, [addNotification]);

  const showWarning = useCallback((message, title = 'Attenzione') => {
    addNotification({
      type: 'warning',
      title,
      message,
      autoHide: true,
      duration: 4000
    });
  }, [addNotification]);

  return {
    notifications: state.ui.notifications,
    showSuccess,
    showError,
    showInfo,
    showWarning,
    remove: removeNotification
  };
};

/**
 * Hook per gestire lo stato dell'UI
 */
export const useUI = () => {
  const { state, setActiveSection, openModal, closeModal } = useAppContext();

  return {
    activeSection: state.ui.activeSection,
    theme: state.ui.theme,
    sidebarOpen: state.ui.sidebarOpen,
    modals: state.ui.modals,
    setActiveSection,
    openModal,
    closeModal
  };
};

/**
 * Hook per gestire lo stato del sistema
 */
export const useSystemStatus = () => {
  const { state } = useAppContext();

  return {
    isOnline: state.system.isOnline,
    lastSync: state.system.lastSync,
    retryQueueLength: state.system.retryQueue.length
  };
};
