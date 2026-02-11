/**
 * Context globale per state management ottimizzato
 * Implementa caching, error handling e performance optimization
 */

import React, { createContext, useContext, useReducer, useCallback, useEffect, useRef } from 'react';
// Import dinamico per evitare problemi di inizializzazione
// import { apiService } from '../services/apiService';

// Initial state
const initialState = {
  // Authentication
  user: null,
  isAuthenticated: false,
  token: localStorage.getItem('access_token'),

  // Data entities con cache
  collaborators: {
    data: [],
    loading: false,
    error: null,
    lastFetch: null,
    filters: { search: '', isActive: true },
    pagination: { skip: 0, limit: 100 }
  },

  projects: {
    data: [],
    loading: false,
    error: null,
    lastFetch: null,
    filters: { status: 'active' },
    pagination: { skip: 0, limit: 100 }
  },

  attendances: {
    data: [],
    loading: false,
    error: null,
    lastFetch: null,
    filters: { startDate: null, endDate: null },
    pagination: { skip: 0, limit: 100 }
  },

  assignments: {
    data: [],
    loading: false,
    error: null,
    lastFetch: null,
    pagination: { skip: 0, limit: 100 }
  },

  implementing_entities: {
    data: [],
    loading: false,
    error: null,
    lastFetch: null,
    filters: { search: '', isActive: true },
    pagination: { skip: 0, limit: 100 }
  },

  contract_templates: {
    data: [],
    loading: false,
    error: null,
    lastFetch: null,
    filters: { tipo_contratto: '', isActive: true, search: '' },
    pagination: { skip: 0, limit: 100 }
  },

  // UI State
  ui: {
    sidebarOpen: true,
    theme: 'light',
    notifications: [],
    modals: {},
    activeSection: 'calendar'
  },

  // System state
  system: {
    isOnline: true,
    lastSync: null,
    retryQueue: [],
    optimisticUpdates: {}
  }
};

// Action types
const ActionTypes = {
  // Authentication
  LOGIN_START: 'LOGIN_START',
  LOGIN_SUCCESS: 'LOGIN_SUCCESS',
  LOGIN_FAILURE: 'LOGIN_FAILURE',
  LOGOUT: 'LOGOUT',
  REFRESH_TOKEN: 'REFRESH_TOKEN',

  // Data operations
  FETCH_START: 'FETCH_START',
  FETCH_SUCCESS: 'FETCH_SUCCESS',
  FETCH_FAILURE: 'FETCH_FAILURE',
  UPDATE_FILTERS: 'UPDATE_FILTERS',
  RESET_ENTITY: 'RESET_ENTITY',

  // CRUD operations
  CREATE_ENTITY: 'CREATE_ENTITY',
  UPDATE_ENTITY: 'UPDATE_ENTITY',
  DELETE_ENTITY: 'DELETE_ENTITY',

  // Optimistic updates
  OPTIMISTIC_ADD: 'OPTIMISTIC_ADD',
  OPTIMISTIC_UPDATE: 'OPTIMISTIC_UPDATE',
  OPTIMISTIC_DELETE: 'OPTIMISTIC_DELETE',
  OPTIMISTIC_REVERT: 'OPTIMISTIC_REVERT',

  // UI
  SET_ACTIVE_SECTION: 'SET_ACTIVE_SECTION',
  TOGGLE_SIDEBAR: 'TOGGLE_SIDEBAR',
  SET_THEME: 'SET_THEME',
  ADD_NOTIFICATION: 'ADD_NOTIFICATION',
  REMOVE_NOTIFICATION: 'REMOVE_NOTIFICATION',
  OPEN_MODAL: 'OPEN_MODAL',
  CLOSE_MODAL: 'CLOSE_MODAL',

  // System
  SET_ONLINE_STATUS: 'SET_ONLINE_STATUS',
  ADD_TO_RETRY_QUEUE: 'ADD_TO_RETRY_QUEUE',
  REMOVE_FROM_RETRY_QUEUE: 'REMOVE_FROM_RETRY_QUEUE',
  UPDATE_LAST_SYNC: 'UPDATE_LAST_SYNC'
};

// Reducer function
const appReducer = (state, action) => {
  switch (action.type) {
    case ActionTypes.LOGIN_START:
      return {
        ...state,
        user: null,
        isAuthenticated: false
      };

    case ActionTypes.LOGIN_SUCCESS:
      return {
        ...state,
        user: action.payload.user,
        isAuthenticated: true,
        token: action.payload.access_token
      };

    case ActionTypes.LOGIN_FAILURE:
      return {
        ...state,
        user: null,
        isAuthenticated: false,
        token: null
      };

    case ActionTypes.LOGOUT:
      return {
        ...initialState,
        token: null,
        user: null,
        isAuthenticated: false
      };

    case ActionTypes.FETCH_START:
      return {
        ...state,
        [action.entity]: {
          ...state[action.entity],
          loading: true,
          error: null
        }
      };

    case ActionTypes.FETCH_SUCCESS:
      return {
        ...state,
        [action.entity]: {
          ...state[action.entity],
          data: action.payload,
          loading: false,
          error: null,
          lastFetch: Date.now()
        }
      };

    case ActionTypes.FETCH_FAILURE:
      return {
        ...state,
        [action.entity]: {
          ...state[action.entity],
          loading: false,
          error: action.error
        }
      };

    case ActionTypes.UPDATE_FILTERS:
      return {
        ...state,
        [action.entity]: {
          ...state[action.entity],
          filters: { ...state[action.entity].filters, ...action.filters }
        }
      };

    case ActionTypes.CREATE_ENTITY:
      return {
        ...state,
        [action.entity]: {
          ...state[action.entity],
          data: [...state[action.entity].data, action.payload]
        }
      };

    case ActionTypes.UPDATE_ENTITY:
      return {
        ...state,
        [action.entity]: {
          ...state[action.entity],
          data: state[action.entity].data.map(item =>
            item.id === action.payload.id ? action.payload : item
          )
        }
      };

    case ActionTypes.DELETE_ENTITY:
      return {
        ...state,
        [action.entity]: {
          ...state[action.entity],
          data: state[action.entity].data.filter(item => item.id !== action.id)
        }
      };

    case ActionTypes.OPTIMISTIC_ADD:
      return {
        ...state,
        [action.entity]: {
          ...state[action.entity],
          data: [...state[action.entity].data, { ...action.payload, id: action.tempId }]
        },
        system: {
          ...state.system,
          optimisticUpdates: {
            ...state.system.optimisticUpdates,
            [action.tempId]: action.payload
          }
        }
      };

    case ActionTypes.OPTIMISTIC_UPDATE:
      return {
        ...state,
        [action.entity]: {
          ...state[action.entity],
          data: state[action.entity].data.map(item =>
            item.id === action.id ? { ...item, ...action.payload } : item
          )
        },
        system: {
          ...state.system,
          optimisticUpdates: {
            ...state.system.optimisticUpdates,
            [action.id]: action.originalData
          }
        }
      };

    case ActionTypes.OPTIMISTIC_REVERT:
      return {
        ...state,
        [action.entity]: {
          ...state[action.entity],
          data: state[action.entity].data.map(item => {
            if (item.id === action.id && state.system.optimisticUpdates[action.id]) {
              return state.system.optimisticUpdates[action.id];
            }
            return item;
          }).filter(item => !action.remove || item.id !== action.id)
        },
        system: {
          ...state.system,
          optimisticUpdates: Object.fromEntries(
            Object.entries(state.system.optimisticUpdates).filter(([key]) => key !== action.id)
          )
        }
      };

    case ActionTypes.SET_ACTIVE_SECTION:
      return {
        ...state,
        ui: {
          ...state.ui,
          activeSection: action.section
        }
      };

    case ActionTypes.ADD_NOTIFICATION:
      return {
        ...state,
        ui: {
          ...state.ui,
          notifications: [
            ...state.ui.notifications,
            { ...action.notification, id: Date.now() }
          ]
        }
      };

    case ActionTypes.REMOVE_NOTIFICATION:
      return {
        ...state,
        ui: {
          ...state.ui,
          notifications: state.ui.notifications.filter(n => n.id !== action.id)
        }
      };

    case ActionTypes.OPEN_MODAL:
      return {
        ...state,
        ui: {
          ...state.ui,
          modals: {
            ...state.ui.modals,
            [action.modalType]: { isOpen: true, data: action.data }
          }
        }
      };

    case ActionTypes.CLOSE_MODAL:
      return {
        ...state,
        ui: {
          ...state.ui,
          modals: {
            ...state.ui.modals,
            [action.modalType]: { isOpen: false, data: null }
          }
        }
      };

    case ActionTypes.SET_ONLINE_STATUS:
      return {
        ...state,
        system: {
          ...state.system,
          isOnline: action.isOnline
        }
      };

    case ActionTypes.ADD_TO_RETRY_QUEUE:
      return {
        ...state,
        system: {
          ...state.system,
          retryQueue: [...state.system.retryQueue, action.operation]
        }
      };

    case ActionTypes.REMOVE_FROM_RETRY_QUEUE:
      return {
        ...state,
        system: {
          ...state.system,
          retryQueue: state.system.retryQueue.filter(op => op.id !== action.operationId)
        }
      };

    default:
      return state;
  }
};

// Create context
const AppContext = createContext();

// Custom hook per usare il context
export const useAppContext = () => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useAppContext must be used within an AppProvider');
  }
  return context;
};

// Cache TTL (5 minuti)
const CACHE_TTL = 5 * 60 * 1000;

// Provider component
export const AppProvider = ({ children }) => {
  const [state, dispatch] = useReducer(appReducer, initialState);

  // Use ref to store functions and state to avoid dependency cycles
  const refreshTokenRef = useRef();
  const processRetryQueueRef = useRef();
  const stateRef = useRef(state);

  // Keep state ref updated
  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  // Auto-refresh token
  useEffect(() => {
    if (state.token && refreshTokenRef.current) {
      const refreshInterval = setInterval(() => {
        refreshTokenRef.current();
      }, 25 * 60 * 1000); // Refresh ogni 25 minuti

      return () => clearInterval(refreshInterval);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.token]);

  // Network status monitoring
  useEffect(() => {
    const handleOnline = () => {
      dispatch({ type: ActionTypes.SET_ONLINE_STATUS, isOnline: true });
      if (processRetryQueueRef.current) {
        processRetryQueueRef.current();
      }
    };

    const handleOffline = () => {
      dispatch({ type: ActionTypes.SET_ONLINE_STATUS, isOnline: false });
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Helper functions
  const addNotification = useCallback((notification) => {
    dispatch({
      type: ActionTypes.ADD_NOTIFICATION,
      notification: {
        type: 'info',
        autoHide: true,
        duration: 5000,
        ...notification
      }
    });
  }, []);

  const removeNotification = useCallback((id) => {
    dispatch({ type: ActionTypes.REMOVE_NOTIFICATION, id });
  }, []);

  const handleError = useCallback((error, context = '') => {
    console.error(`Error in ${context}:`, error);

    let message = 'Si è verificato un errore';
    if (error.response?.status === 401) {
      message = 'Sessione scaduta. Effettua nuovamente il login.';
      // Dispatch logout direttamente invece di chiamare il callback
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      dispatch({ type: ActionTypes.LOGOUT });
    } else if (error.response?.status === 403) {
      message = 'Non hai i permessi per questa operazione';
    } else if (error.response?.status === 429) {
      message = 'Troppe richieste. Riprova tra poco.';
    } else if (error.message) {
      message = error.message;
    }

    // Dispatch notification direttamente invece di chiamare addNotification
    dispatch({
      type: ActionTypes.ADD_NOTIFICATION,
      notification: {
        type: 'error',
        title: 'Errore',
        message,
        autoHide: false,
        duration: 5000
      }
    });

    return error;
  }, []); // Nessuna dipendenza - usa solo dispatch

  // API operations with caching and error handling
  const fetchEntity = useCallback(async (entityType, forceRefresh = false) => {
    const currentState = stateRef.current;

    // Check cache
    const entityData = currentState[entityType];
    if (!forceRefresh && entityData && entityData.lastFetch) {
      const cacheAge = Date.now() - entityData.lastFetch;
      if (cacheAge < CACHE_TTL) {
        return entityData.data;
      }
    }

    dispatch({ type: ActionTypes.FETCH_START, entity: entityType });

    try {
      // Import dinamico dell'API service
      const { apiService } = await import('../services/apiService');

      let data;
      const entityState = currentState[entityType];

      switch (entityType) {
        case 'collaborators':
          data = await apiService.getCollaborators(entityState.filters, entityState.pagination);
          break;
        case 'projects':
          data = await apiService.getProjects(entityState.filters, entityState.pagination);
          break;
        case 'attendances':
          data = await apiService.getAttendances(entityState.filters, entityState.pagination);
          break;
        case 'assignments':
          data = await apiService.getAssignments(entityState.pagination);
          break;
        case 'implementing_entities':
          // Import named export
          const { getImplementingEntities } = await import('../services/apiService');
          data = await getImplementingEntities(
            entityState.pagination.skip,
            entityState.pagination.limit,
            entityState.filters.search,
            entityState.filters.isActive
          );
          break;
        case 'contract_templates':
          // Import named export
          const { getContractTemplates } = await import('../services/apiService');
          data = await getContractTemplates({
            skip: entityState.pagination.skip,
            limit: entityState.pagination.limit,
            tipo_contratto: entityState.filters.tipo_contratto,
            is_active: entityState.filters.isActive,
            search: entityState.filters.search
          });
          break;
        default:
          throw new Error(`Unknown entity type: ${entityType}`);
      }

      dispatch({
        type: ActionTypes.FETCH_SUCCESS,
        entity: entityType,
        payload: data
      });

      return data;
    } catch (error) {
      dispatch({
        type: ActionTypes.FETCH_FAILURE,
        entity: entityType,
        error: handleError(error, `fetch ${entityType}`)
      });

      if (!currentState.system.isOnline) {
        dispatch({
          type: ActionTypes.ADD_TO_RETRY_QUEUE,
          operation: { type: 'fetch', entity: entityType, id: Date.now() }
        });
      }

      throw error;
    }
  }, [handleError]); // Solo handleError, non state

  // Authentication
  const login = useCallback(async (credentials) => {
    dispatch({ type: ActionTypes.LOGIN_START });

    try {
      const { apiService } = await import('../services/apiService');
      const response = await apiService.login(credentials);

      localStorage.setItem('access_token', response.access_token);
      localStorage.setItem('refresh_token', response.refresh_token);

      dispatch({
        type: ActionTypes.LOGIN_SUCCESS,
        payload: response
      });

      addNotification({
        type: 'success',
        title: 'Login effettuato',
        message: `Benvenuto, ${response.user.full_name}!`
      });

      return response;
    } catch (error) {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');

      dispatch({ type: ActionTypes.LOGIN_FAILURE });
      handleError(error, 'login');
      throw error;
    }
  }, [addNotification, handleError]);

  const logout = useCallback(() => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    dispatch({ type: ActionTypes.LOGOUT });

    addNotification({
      type: 'info',
      title: 'Logout effettuato',
      message: 'Sessione terminata con successo'
    });
  }, [addNotification]);

  const refreshToken = useCallback(async () => {
    try {
      const { apiService } = await import('../services/apiService');
      const refreshToken = localStorage.getItem('refresh_token');
      if (!refreshToken) throw new Error('No refresh token');

      const response = await apiService.refreshToken(refreshToken);
      localStorage.setItem('access_token', response.access_token);

      dispatch({ type: ActionTypes.REFRESH_TOKEN, token: response.access_token });
    } catch (error) {
      logout();
    }
  }, [logout]);

  // Keep ref updated
  useEffect(() => {
    refreshTokenRef.current = refreshToken;
  }, [refreshToken]);

  // CRUD operations with optimistic updates
  const createEntity = useCallback(async (entityType, data) => {
    const tempId = `temp_${Date.now()}`;

    // Optimistic update
    dispatch({
      type: ActionTypes.OPTIMISTIC_ADD,
      entity: entityType,
      payload: data,
      tempId
    });

    try {
      const { apiService } = await import('../services/apiService');
      let createdEntity;

      switch (entityType) {
        case 'collaborators':
          createdEntity = await apiService.createCollaborator(data);
          break;
        case 'projects':
          createdEntity = await apiService.createProject(data);
          break;
        case 'attendances':
          createdEntity = await apiService.createAttendance(data);
          break;
        case 'assignments':
          createdEntity = await apiService.createAssignment(data);
          break;
        case 'implementing_entities':
          const { createImplementingEntity } = await import('../services/apiService');
          createdEntity = await createImplementingEntity(data);
          break;
        case 'contract_templates':
          const { createContractTemplate } = await import('../services/apiService');
          createdEntity = await createContractTemplate(data);
          break;
        default:
          throw new Error(`Unknown entity type: ${entityType}`);
      }

      // Replace optimistic update with real data
      dispatch({
        type: ActionTypes.UPDATE_ENTITY,
        entity: entityType,
        payload: createdEntity
      });

      addNotification({
        type: 'success',
        title: 'Creazione completata',
        message: `${entityType} creato con successo`
      });

      return createdEntity;
    } catch (error) {
      // Revert optimistic update
      dispatch({
        type: ActionTypes.OPTIMISTIC_REVERT,
        entity: entityType,
        id: tempId,
        remove: true
      });

      handleError(error, `create ${entityType}`);
      throw error;
    }
  }, [addNotification, handleError]);

  const updateEntity = useCallback(async (entityType, id, data) => {
    const currentState = stateRef.current;
    const originalData = currentState[entityType].data.find(item => item.id === id);

    // Optimistic update
    dispatch({
      type: ActionTypes.OPTIMISTIC_UPDATE,
      entity: entityType,
      id,
      payload: data,
      originalData
    });

    try {
      const { apiService } = await import('../services/apiService');
      let updatedEntity;

      switch (entityType) {
        case 'collaborators':
          updatedEntity = await apiService.updateCollaborator(id, data);
          break;
        case 'projects':
          updatedEntity = await apiService.updateProject(id, data);
          break;
        case 'attendances':
          updatedEntity = await apiService.updateAttendance(id, data);
          break;
        case 'assignments':
          updatedEntity = await apiService.updateAssignment(id, data);
          break;
        case 'implementing_entities':
          const { updateImplementingEntity } = await import('../services/apiService');
          updatedEntity = await updateImplementingEntity(id, data);
          break;
        case 'contract_templates':
          const { updateContractTemplate } = await import('../services/apiService');
          updatedEntity = await updateContractTemplate(id, data);
          break;
        default:
          throw new Error(`Unknown entity type: ${entityType}`);
      }

      dispatch({
        type: ActionTypes.UPDATE_ENTITY,
        entity: entityType,
        payload: updatedEntity
      });

      addNotification({
        type: 'success',
        title: 'Aggiornamento completato',
        message: `${entityType} aggiornato con successo`
      });

      return updatedEntity;
    } catch (error) {
      // Revert optimistic update
      dispatch({
        type: ActionTypes.OPTIMISTIC_REVERT,
        entity: entityType,
        id
      });

      handleError(error, `update ${entityType}`);
      throw error;
    }
  }, [addNotification, handleError]);

  const deleteEntity = useCallback(async (entityType, id) => {
    const currentState = stateRef.current;
    const originalData = currentState[entityType].data.find(item => item.id === id);

    // Optimistic delete
    dispatch({
      type: ActionTypes.DELETE_ENTITY,
      entity: entityType,
      id
    });

    try {
      const { apiService } = await import('../services/apiService');

      switch (entityType) {
        case 'collaborators':
          await apiService.deleteCollaborator(id);
          break;
        case 'projects':
          await apiService.deleteProject(id);
          break;
        case 'attendances':
          await apiService.deleteAttendance(id);
          break;
        case 'assignments':
          await apiService.deleteAssignment(id);
          break;
        case 'implementing_entities':
          const { deleteImplementingEntity } = await import('../services/apiService');
          await deleteImplementingEntity(id, true); // soft delete by default
          break;
        case 'contract_templates':
          const { deleteContractTemplate } = await import('../services/apiService');
          await deleteContractTemplate(id, true); // soft delete by default
          break;
        default:
          throw new Error(`Unknown entity type: ${entityType}`);
      }

      addNotification({
        type: 'success',
        title: 'Eliminazione completata',
        message: `${entityType} eliminato con successo`
      });
    } catch (error) {
      // Revert optimistic delete
      dispatch({
        type: ActionTypes.CREATE_ENTITY,
        entity: entityType,
        payload: originalData
      });

      handleError(error, `delete ${entityType}`);
      throw error;
    }
  }, [addNotification, handleError]);

  // Process retry queue when back online
  const processRetryQueue = useCallback(async () => {
    const currentState = stateRef.current;
    for (const operation of currentState.system.retryQueue) {
      try {
        await fetchEntity(operation.entity, true);
        dispatch({
          type: ActionTypes.REMOVE_FROM_RETRY_QUEUE,
          operationId: operation.id
        });
      } catch (error) {
        console.error('Retry failed:', error);
      }
    }
  }, [fetchEntity]);

  // Keep ref updated
  useEffect(() => {
    processRetryQueueRef.current = processRetryQueue;
  }, [processRetryQueue]);

  // UI helpers
  const setActiveSection = useCallback((section) => {
    dispatch({ type: ActionTypes.SET_ACTIVE_SECTION, section });
  }, []);

  const openModal = useCallback((modalType, data = null) => {
    dispatch({ type: ActionTypes.OPEN_MODAL, modalType, data });
  }, []);

  const closeModal = useCallback((modalType) => {
    dispatch({ type: ActionTypes.CLOSE_MODAL, modalType });
  }, []);

  const updateFilters = useCallback((entity, filters) => {
    dispatch({ type: ActionTypes.UPDATE_FILTERS, entity, filters });
  }, []);

  // Context value
  const value = {
    // State
    state,

    // Auth
    login,
    logout,
    refreshToken,

    // Data operations
    fetchEntity,
    createEntity,
    updateEntity,
    deleteEntity,

    // UI operations
    setActiveSection,
    openModal,
    closeModal,
    updateFilters,

    // Notifications
    addNotification,
    removeNotification,

    // Utils
    handleError
  };

  return (
    <AppContext.Provider value={value}>
      {children}
    </AppContext.Provider>
  );
};

export default AppContext;