/**
 * Servizio API avanzato con autenticazione, retry logic e caching
 * Updated to use shared http client from lib/http.js
 */

import { http, apiRootUrl } from '../lib/http';

// Retry logic per richieste fallite
const retryRequest = async (requestFn, maxRetries = 3, delay = 1000) => {
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await requestFn();
    } catch (error) {
      if (i === maxRetries - 1) {
        throw error;
      }

      // Exponential backoff
      await new Promise(resolve => setTimeout(resolve, delay * Math.pow(2, i)));
    }
  }
};

// API Service class
class ApiService {
  // Authentication
  async login(credentials) {
    const formData = new FormData();
    formData.append('username', credentials.username);
    formData.append('password', credentials.password);

    const response = await http.post('/auth/login', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });

    return response.data;
  }

  async refreshToken(refreshToken) {
    const formData = new FormData();
    formData.append('refresh_token', refreshToken);

    const response = await http.post('/auth/refresh', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  }

  async getCurrentUser() {
    const response = await http.get('/auth/me');
    return response.data;
  }

  async register(userData) {
    const formData = new FormData();
    Object.keys(userData).forEach(key => {
      formData.append(key, userData[key]);
    });

    const response = await http.post('/auth/register', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });

    return response.data;
  }

  // Collaborators
  async getCollaborators(filters = {}, pagination = {}) {
    const params = {};
    if (pagination.skip) params.skip = pagination.skip;
    if (pagination.limit) params.limit = pagination.limit;
    if (filters.search) params.search = filters.search;
    if (filters.isActive !== undefined) params.is_active = filters.isActive;

    const response = await retryRequest(() =>
      http.get('/collaborators', { params })
    );

    return response.data;
  }

  async getCollaborator(id) {
    const response = await http.get(`/collaborators/${id}`);
    return response.data;
  }

  async createCollaborator(data) {
    const response = await http.post('/collaborators', data);
    return response.data;
  }

  async updateCollaborator(id, data) {
    const response = await http.put(`/collaborators/${id}`, data);
    return response.data;
  }

  async deleteCollaborator(id) {
    const response = await http.delete(`/collaborators/${id}`);
    return response.data;
  }

  async bulkImportCollaborators(collaboratorsArray) {
    const response = await http.post('/collaborators/bulk-import', collaboratorsArray);
    return response.data;
  }

  async bulkImportAllievi(allieviArray) {
    const response = await http.post('/allievi/bulk-import', allieviArray);
    return response.data;
  }

  async bulkImportAziendeClienti(aziendeArray) {
    const response = await http.post('/aziende-clienti/bulk-import', aziendeArray);
    return response.data;
  }

  async getCollaboratorsWithProjects(pagination = {}) {
    const params = {};
    if (pagination.skip) params.skip = pagination.skip;
    if (pagination.limit) params.limit = pagination.limit;

    const response = await retryRequest(() =>
      http.get('/collaborators-with-projects', { params })
    );

    return response.data;
  }

  // Projects
  async getProjects(filters = {}, pagination = {}) {
    const params = {};
    if (pagination.skip) params.skip = pagination.skip;
    if (pagination.limit) params.limit = pagination.limit;
    if (filters.status) params.status = filters.status;

    const response = await retryRequest(() =>
      http.get('/projects', { params })
    );

    return response.data;
  }

  async getProject(id) {
    const response = await http.get(`/projects/${id}`);
    return response.data;
  }

  async createProject(data) {
    const response = await http.post('/projects', data);
    return response.data;
  }

  async updateProject(id, data) {
    const response = await http.put(`/projects/${id}`, data);
    return response.data;
  }

  async deleteProject(id) {
    const response = await http.delete(`/projects/${id}`);
    return response.data;
  }

  // Attendances
  async getAttendances(filters = {}, pagination = {}) {
    const params = {};
    if (pagination.skip) params.skip = pagination.skip;
    if (pagination.limit) params.limit = pagination.limit;
    if (filters.collaboratorId) params.collaborator_id = filters.collaboratorId;
    if (filters.projectId) params.project_id = filters.projectId;
    if (filters.startDate) params.start_date = filters.startDate;
    if (filters.endDate) params.end_date = filters.endDate;
    if (filters.includeDetails) params.include_details = filters.includeDetails;

    const response = await retryRequest(() =>
      http.get('/attendances', { params })
    );

    return response.data;
  }

  async getAttendance(id) {
    const response = await http.get(`/attendances/${id}`);
    return response.data;
  }

  async createAttendance(data) {
    const response = await http.post('/attendances', data);
    return response.data;
  }

  async updateAttendance(id, data) {
    const response = await http.put(`/attendances/${id}`, data);
    return response.data;
  }

  async deleteAttendance(id) {
    const response = await http.delete(`/attendances/${id}`);
    return response.data;
  }

  // Assignments
  async getAssignments(pagination = {}) {
    const params = {};
    if (pagination.skip) params.skip = pagination.skip;
    if (pagination.limit) params.limit = pagination.limit;

    const response = await retryRequest(() =>
      http.get('/assignments', { params })
    );

    return response.data;
  }

  async getAssignment(id) {
    const response = await http.get(`/assignments/${id}`);
    return response.data;
  }

  async createAssignment(data) {
    const response = await http.post('/assignments', data);
    return response.data;
  }

  async updateAssignment(id, data) {
    const response = await http.put(`/assignments/${id}`, data);
    return response.data;
  }

  async deleteAssignment(id) {
    const response = await http.delete(`/assignments/${id}`);
    return response.data;
  }

  async getAssignmentsByCollaborator(collaboratorId) {
    const response = await http.get(`/collaborators/${collaboratorId}/assignments`);
    return response.data;
  }

  async getAssignmentsByProject(projectId) {
    const response = await http.get(`/projects/${projectId}/assignments`);
    return response.data;
  }

  // Collaborator-Project associations
  async assignCollaboratorToProject(collaboratorId, projectId) {
    const response = await http.post(`/collaborators/${collaboratorId}/projects/${projectId}`);
    return response.data;
  }

  async removeCollaboratorFromProject(collaboratorId, projectId) {
    const response = await http.delete(`/collaborators/${collaboratorId}/projects/${projectId}`);
    return response.data;
  }

  // System endpoints
  async healthCheck() {
    const response = await fetch(`${apiRootUrl}/health`);
    if (!response.ok) {
      throw new Error(`Health check failed: ${response.status}`);
    }
    return await response.json();
  }

  async getSystemMetrics() {
    const response = await http.get('/admin/metrics');
    return response.data;
  }

  async getSecurityLogs(params = {}) {
    const response = await http.get('/admin/security-logs', { params });
    return response.data;
  }

  // Entities (Enti Attuatori)
  async getEntities(filters = {}, pagination = {}) {
    const params = {};
    if (pagination.skip) params.skip = pagination.skip;
    if (pagination.limit) params.limit = pagination.limit;
    if (filters.search) params.search = filters.search;
    if (filters.isActive !== undefined) params.is_active = filters.isActive;

    const response = await retryRequest(() =>
      http.get('/entities', { params })
    );
    return response.data;
  }

  async getEntity(id) {
    const response = await http.get(`/entities/${id}`);
    return response.data;
  }

  async createEntity(data) {
    const response = await http.post('/entities', data);
    return response.data;
  }

  async updateEntity(id, data) {
    const response = await http.put(`/entities/${id}`, data);
    return response.data;
  }

  async deleteEntity(id, softDelete = true) {
    const response = await http.delete(`/entities/${id}`, { params: { soft_delete: softDelete } });
    return response.data;
  }

  // Contract Templates
  async getContractTemplates(filters = {}) {
    const params = {
      skip: filters?.skip || 0,
      limit: filters?.limit || 100,
    };
    if (filters?.ambito_template) params.ambito_template = filters.ambito_template;
    if (filters?.chiave_documento) params.chiave_documento = filters.chiave_documento;
    if (filters?.ente_attuatore_id) params.ente_attuatore_id = filters.ente_attuatore_id;
    if (filters?.progetto_id) params.progetto_id = filters.progetto_id;
    if (filters?.ente_erogatore) params.ente_erogatore = filters.ente_erogatore;
    if (filters?.avviso !== undefined) params.avviso = filters.avviso;
    if (filters?.tipo_contratto) params.tipo_contratto = filters.tipo_contratto;
    if (filters?.is_active !== undefined) params.is_active = filters.is_active;
    if (filters?.search) params.search = filters.search;

    const response = await http.get('/contracts', { params });
    return response.data;
  }

  async getContractTemplate(id) {
    const response = await http.get(`/contracts/${id}`);
    return response.data;
  }

  async createContractTemplate(data) {
    const response = await http.post('/contracts', data);
    return response.data;
  }

  async updateContractTemplate(id, data) {
    const response = await http.put(`/contracts/${id}`, data);
    return response.data;
  }

  async deleteContractTemplate(id, softDelete = true) {
    const response = await http.delete(`/contracts/${id}`);
    return response.data;
  }

  async generateContract(data) {
    const response = await http.post('/contracts/generate-contract', data, {
      responseType: 'blob'
    });
    return response.data;
  }

  // Reporting
  async getTimesheetReport(filters = {}) {
    const response = await http.get('/reporting/timesheet', { params: filters });
    return response.data;
  }

  async startTimesheetExport(filters = {}) {
    const response = await http.post('/reporting/timesheet/export', filters);
    return response.data;
  }

  async getTimesheetExport(exportId) {
    const response = await http.get(`/reporting/timesheet/export/${exportId}`, {
      responseType: 'blob',
      validateStatus: () => true,
    });
    const contentType = response.headers['content-type'] || '';

    if (contentType.includes('application/json')) {
      const payload = JSON.parse(await response.data.text());
      return payload;
    }

    return {
      status: 'ready',
      blob: response.data,
      filename: `timesheet-${exportId}.csv`,
    };
  }

  async getSummaryReport(filters = {}) {
    const response = await http.get('/reporting/summary', { params: filters });
    return response.data;
  }

  async getCollaboratorStats(collaboratorId, filters = {}) {
    const response = await http.get(`/reporting/collaborator/${collaboratorId}/stats`, { params: filters });
    return response.data;
  }

  async getProjectStats(projectId, filters = {}) {
    const response = await http.get(`/reporting/project/${projectId}/stats`, { params: filters });
    return response.data;
  }

  // Piani finanziari
  async getPianiFinanziari(params = {}) {
    const response = await http.get('/piani-finanziari', { params });
    return response.data;
  }

  async getPianoFinanziario(id) {
    const response = await http.get(`/piani-finanziari/${id}`);
    return response.data;
  }

  async createPianoFinanziario(data) {
    const response = await http.post('/piani-finanziari', data);
    return response.data;
  }

  async updateVociPianoFinanziario(id, data) {
    const response = await http.put(`/piani-finanziari/${id}/voci`, data);
    return response.data;
  }

  async getRiepilogoPianoFinanziario(id) {
    const response = await http.get(`/piani-finanziari/${id}/riepilogo`);
    return response.data;
  }

  async exportPianoFinanziarioExcel(id) {
    const response = await http.get(`/piani-finanziari/${id}/export-excel`, {
      responseType: 'blob',
    });
    return response;
  }

  // Batch operations
  async batchUpdateAssignments(updates) {
    const response = await http.post('/assignments/batch-update', { updates });
    return response.data;
  }

  // File operations - Document upload for collaborators
  async uploadDocumentoIdentita(collaboratorId, file, dataScadenza = null) {
    const formData = new FormData();
    formData.append('file', file);
    if (dataScadenza) {
      formData.append('data_scadenza', dataScadenza);
    }

    const response = await http.post(`/collaborators/${collaboratorId}/upload-documento`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      timeout: 60000,
    });

    return response.data;
  }

  async uploadCurriculum(collaboratorId, file) {
    const formData = new FormData();
    formData.append('file', file);

    const response = await http.post(`/collaborators/${collaboratorId}/upload-curriculum`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      timeout: 60000,
    });

    return response.data;
  }

  async downloadDocumentoIdentita(collaboratorId) {
    const response = await http.get(`/collaborators/${collaboratorId}/download-documento`, {
      responseType: 'blob',
    });

    return response;
  }

  async downloadCurriculum(collaboratorId) {
    const response = await http.get(`/collaborators/${collaboratorId}/download-curriculum`, {
      responseType: 'blob',
    });

    return response;
  }

  async deleteDocumentoIdentita(collaboratorId) {
    const response = await http.delete(`/collaborators/${collaboratorId}/delete-documento`);
    return response.data;
  }

  async deleteCurriculum(collaboratorId) {
    const response = await http.delete(`/collaborators/${collaboratorId}/delete-curriculum`);
    return response.data;
  }

  // Generic file upload (for future use)
  async uploadFile(file, entityType, entityId) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('entity_type', entityType);
    formData.append('entity_id', entityId);

    const response = await http.post('/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      timeout: 60000,
    });

    return response.data;
  }

  // Export operations
  async exportData(entityType, format = 'excel', filters = {}) {
    const response = await http.get(`/export/${entityType}/${format}`, {
      params: filters,
      responseType: 'blob',
    });

    return response.data;
  }

  // Analytics
  async getDashboardData(dateRange = {}) {
    const response = await http.get('/analytics/dashboard', { params: dateRange });
    return response.data;
  }

  async getAttendanceReport(filters = {}) {
    const response = await http.get('/analytics/attendance-report', { params: filters });
    return response.data;
  }

  async getProjectProgress(projectId) {
    const response = await http.get(`/analytics/project-progress/${projectId}`);
    return response.data;
  }

  // Search
  async globalSearch(query, entityTypes = []) {
    const params = { q: query };
    if (entityTypes.length > 0) {
      params.types = entityTypes;
    }

    const response = await http.get('/search', { params });
    return response.data;
  }
}

// Crea istanza singleton
const apiService = new ApiService();

// Legacy exports per compatibilità
export const healthCheck = () => apiService.healthCheck();
export const getCollaborators = (skip, limit) => apiService.getCollaborators({}, { skip, limit });
export const getProjects = (skip, limit) => apiService.getProjects({}, { skip, limit });
export const getAttendances = (filters) => apiService.getAttendances(filters || {}, {});
export const createAttendance = (data) => apiService.createAttendance(data);
export const updateAttendance = (id, data) => apiService.updateAttendance(id, data);
export const getAssignments = (skip, limit) => apiService.getAssignments({ skip, limit });

// Collaborators
export const getCollaboratorsWithProjects = (skip, limit) => apiService.getCollaboratorsWithProjects({ skip, limit });
export const createCollaborator = (data) => apiService.createCollaborator(data);
export const updateCollaborator = (id, data) => apiService.updateCollaborator(id, data);
export const deleteCollaborator = (id) => apiService.deleteCollaborator(id);
export const bulkImportCollaborators = (collaboratorsArray) => apiService.bulkImportCollaborators(collaboratorsArray);
export const bulkImportAllievi = (allieviArray) => apiService.bulkImportAllievi(allieviArray);
export const bulkImportAziendeClienti = (aziendeArray) => apiService.bulkImportAziendeClienti(aziendeArray);
export const getCollaborator = (id) => apiService.getCollaborator(id);
export const uploadDocumentoIdentita = (collaboratorId, file, dataScadenza = null) =>
  apiService.uploadDocumentoIdentita(collaboratorId, file, dataScadenza);
export const uploadCurriculum = (collaboratorId, file) =>
  apiService.uploadCurriculum(collaboratorId, file);
export const downloadDocumentoIdentitaFile = (collaboratorId) =>
  apiService.downloadDocumentoIdentita(collaboratorId);
export const downloadCurriculumFile = (collaboratorId) =>
  apiService.downloadCurriculum(collaboratorId);

// Documenti richiesti
export const getDocumentiRichiesti = (params = {}) =>
  http.get('/documenti-richiesti/', { params }).then(r => r.data);
export const getDocumentoRichiesto = (docId) =>
  http.get(`/documenti-richiesti/${docId}`).then(r => r.data);
export const createDocumentoRichiesto = (data) =>
  http.post('/documenti-richiesti/', data).then(r => r.data);
export const updateDocumentoRichiesto = (docId, data) =>
  http.put(`/documenti-richiesti/${docId}`, data).then(r => r.data);
export const deleteDocumentoRichiesto = (docId) =>
  http.delete(`/documenti-richiesti/${docId}`).then(r => r.data);
export const getDocumentiCollaboratore = (collaboratoreId, params = {}) =>
  http.get(`/collaborators/${collaboratoreId}/documenti`, { params }).then(r => r.data);
export const getDocumentiMancantiCollaboratore = (collaboratoreId) =>
  http.get(`/collaborators/${collaboratoreId}/documenti-mancanti`).then(r => r.data);
export const validaDocumentoRichiesto = (docId, data) =>
  http.post(`/documenti-richiesti/${docId}/valida`, data).then(r => r.data);
export const rifiutaDocumentoRichiesto = (docId, data) =>
  http.post(`/documenti-richiesti/${docId}/rifiuta`, data).then(r => r.data);
export const uploadDocumentoRichiesto = (docId, file, dataScadenza = null) => {
  const formData = new FormData();
  formData.append('file', file);
  if (dataScadenza) {
    formData.append('data_scadenza', dataScadenza);
  }
  return http.post(`/documenti-richiesti/${docId}/upload`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    timeout: 60000,
  }).then(r => r.data);
};

// Projects
export const createProject = (data) => apiService.createProject(data);
export const updateProject = (id, data) => apiService.updateProject(id, data);
export const deleteProject = (id) => apiService.deleteProject(id);
export const getProject = (id) => apiService.getProject(id);

// Collaborator-Project associations
export const assignCollaboratorToProject = (collaboratorId, projectId) => apiService.assignCollaboratorToProject(collaboratorId, projectId);
export const removeCollaboratorFromProject = (collaboratorId, projectId) => apiService.removeCollaboratorFromProject(collaboratorId, projectId);

// Assignments
export const getCollaboratorAssignments = (collaboratorId) => apiService.getAssignmentsByCollaborator(collaboratorId);
export const getProjectAssignments = (projectId) => apiService.getAssignmentsByProject(projectId);
export const createAssignment = (data) => apiService.createAssignment(data);
export const updateAssignment = (id, data) => apiService.updateAssignment(id, data);
export const deleteAssignment = (id) => apiService.deleteAssignment(id);
// Implementing Entities
export const getImplementingEntities = (skip, limit, search, is_active) => apiService.getEntities({ search, isActive: is_active }, { skip, limit });
export const getImplementingEntity = (id) => apiService.getEntity(id);
export const createImplementingEntity = (data) => apiService.createEntity(data);
export const updateImplementingEntity = (id, data) => apiService.updateEntity(id, data);
export const deleteImplementingEntity = (id, soft_delete = true) => apiService.deleteEntity(id, soft_delete);

// Contract Templates
export const getContractTemplates = (filters) => apiService.getContractTemplates(filters);
export const getContractTemplate = (id) => apiService.getContractTemplate(id);
export const createContractTemplate = (data) => apiService.createContractTemplate(data);
export const updateContractTemplate = (id, data) => apiService.updateContractTemplate(id, data);
export const deleteContractTemplate = (id, soft_delete = true) => apiService.deleteContractTemplate(id, soft_delete);
export const generateContract = (data) => apiService.generateContract(data);

// Avvisi
export const getAvvisi = (params = {}) =>
  http.get('/avvisi/', { params }).then(r => r.data);
export const getAvviso = (id) =>
  http.get(`/avvisi/${id}`).then(r => r.data);
export const createAvviso = (data) =>
  http.post('/avvisi/', data).then(r => r.data);
export const updateAvviso = (id, data) =>
  http.put(`/avvisi/${id}`, data).then(r => r.data);
export const deleteAvviso = (id) =>
  http.delete(`/avvisi/${id}`).then(r => r.data);

// Agents
export const getAgentsCatalog = () =>
  http.get('/agents/').then(r => r.data);
export const getAgentInfo = (agentType) =>
  http.get(`/agents/${agentType}/info`).then(r => r.data);
export const getAgentLlmHealth = () =>
  http.get('/agents/llm/health').then(r => r.data);
export const runAgent = (data) =>
  http.post('/agents/run', data, { timeout: 180000 }).then(r => r.data);
export const runAgentByType = (agentType) =>
  http.post(`/agents/${agentType}/run`).then(r => r.data);
export const getAgentRuns = (params = {}) =>
  http.get('/agents/runs/', { params }).then(r => r.data);
export const getAgentRunDetail = (runId) =>
  http.get(`/agents/runs/${runId}`).then(r => r.data);
export const getAgentSuggestions = (params = {}) =>
  http.get('/agents/suggestions/', { params }).then(r => r.data);
export const getPendingAgentSuggestions = () =>
  http.get('/agents/suggestions/pending').then(r => r.data);
export const getAgentSuggestionDetail = (suggestionId) =>
  http.get(`/agents/suggestions/${suggestionId}`).then(r => r.data);
export const reviewAgentSuggestion = (suggestionId, data) =>
  http.post(`/agents/suggestions/${suggestionId}/review`, data).then(r => r.data);
export const applyAgentSuggestionFix = (suggestionId) =>
  http.post(`/agents/suggestions/${suggestionId}/apply-fix`).then(r => r.data);
export const bulkReviewAgentSuggestions = (data) =>
  http.post('/agents/suggestions/bulk-review', data).then(r => r.data);
export const acceptAgentSuggestion = (suggestionId, data) =>
  http.post(`/agents/suggestions/${suggestionId}/accept`, data).then(r => r.data);
export const rejectAgentSuggestion = (suggestionId, data) =>
  http.post(`/agents/suggestions/${suggestionId}/reject`, data).then(r => r.data);
export const workflowAgentSuggestion = (suggestionId, data) =>
  http.post(`/agents/suggestions/${suggestionId}/workflow`, data).then(r => r.data);
export const getAgentCommunications = (params = {}) =>
  http.get('/agents/communications', { params }).then(r => r.data);
export const createAgentCommunication = (data) =>
  http.post('/agents/communications', data).then(r => r.data);
export const updateAgentCommunicationStatus = (draftId, data) =>
  http.post(`/agents/communications/${draftId}/status`, data).then(r => r.data);
export const getEmailInboxItems = (params = {}) =>
  http.get('/email-inbox/items', { params }).then(r => r.data);
export const assignEmailInboxItem = (itemId, data) =>
  http.post(`/email-inbox/items/${itemId}/assign`, data).then(r => r.data);
export const downloadEmailInboxAttachment = (itemId) =>
  http.get(`/email-inbox/items/${itemId}/attachment`, { responseType: 'blob' });

// Reporting
export const getTimesheetReport = (filters) => apiService.getTimesheetReport(filters);
export const startTimesheetExport = (filters) => apiService.startTimesheetExport(filters);
export const getTimesheetExport = (exportId) => apiService.getTimesheetExport(exportId);
export const getSummaryReport = (filters) => apiService.getSummaryReport(filters);
export const getCollaboratorStats = (collaboratorId, filters) => apiService.getCollaboratorStats(collaboratorId, filters);
export const getProjectStats = (projectId, filters) => apiService.getProjectStats(projectId, filters);

// ── Blocco 2: Smart Collaborators Search ─────
export const getCollaboratorsPaginated = (params = {}) =>
  http.get('/collaborators/search', { params }).then(r => r.data);

// ── Blocco 1: Agenzie ────────────────────────
export const getAgenzie = (params = {}) =>
  http.get('/agenzie/', { params }).then(r => r.data);
export const getAgenzia = (id) =>
  http.get(`/agenzie/${id}`).then(r => r.data);
export const createAgenzia = (data) =>
  http.post('/agenzie/', data).then(r => r.data);
export const updateAgenzia = (id, data) =>
  http.put(`/agenzie/${id}`, data).then(r => r.data);
export const deleteAgenzia = (id) =>
  http.delete(`/agenzie/${id}`).then(r => r.data);

// ── Blocco 1: Consulenti ─────────────────────
export const getConsulenti = (params = {}) =>
  http.get('/consulenti/', {
    params: {
      ...params,
      limit: params.limit ? Math.min(Number(params.limit) || 0, 100) || undefined : params.limit,
    },
  }).then(r => r.data);
export const getConsulente = (id) =>
  http.get(`/consulenti/${id}`).then(r => r.data);
export const getAziendeConsulente = (id) =>
  http.get(`/consulenti/${id}/aziende`).then(r => r.data);
export const createConsulente = (data) =>
  http.post('/consulenti/', data).then(r => r.data);
export const updateConsulente = (id, data) =>
  http.put(`/consulenti/${id}`, data).then(r => r.data);
export const deleteConsulente = (id) =>
  http.delete(`/consulenti/${id}`).then(r => r.data);

// ── Blocco 1: Aziende Clienti ────────────────
export const getAziendeClienti = (params = {}) =>
  http.get('/aziende-clienti/', {
    params: {
      ...params,
      limit: params.limit ? Math.min(Number(params.limit) || 0, 100) || undefined : params.limit,
    },
  }).then(r => r.data);
export const getAziendaCliente = (id) =>
  http.get(`/aziende-clienti/${id}`).then(r => r.data);
export const searchAziendeClienti = (q, limit = 10) =>
  http.get('/aziende-clienti/search', { params: { q, limit } }).then(r => r.data);
export const createAziendaCliente = (data) =>
  http.post('/aziende-clienti/', data).then(r => r.data);
export const updateAziendaCliente = (id, data) =>
  http.put(`/aziende-clienti/${id}`, data).then(r => r.data);
export const deleteAziendaCliente = (id) =>
  http.delete(`/aziende-clienti/${id}`).then(r => r.data);

export const getAllievi = (params = {}) =>
  http.get('/allievi/', {
    params: {
      ...params,
      limit: params.limit ? Math.min(Number(params.limit) || 0, 100) || undefined : params.limit,
    },
  }).then(r => r.data);
export const getAllievo = (id) =>
  http.get(`/allievi/${id}`).then(r => r.data);
export const createAllievo = (data) =>
  http.post('/allievi/', data).then(r => r.data);
export const updateAllievo = (id, data) =>
  http.put(`/allievi/${id}`, data).then(r => r.data);
export const deleteAllievo = (id) =>
  http.delete(`/allievi/${id}`).then(r => r.data);

// ── Blocco 3: Catalogo ───────────────────────
export const getProdotti = (params = {}) =>
  http.get('/catalogo/', {
    params: {
      ...params,
      limit: params.limit ? Math.min(Number(params.limit) || 0, 200) || undefined : params.limit,
    },
  }).then(r => r.data);
export const getProdotto = (id) =>
  http.get(`/catalogo/${id}`).then(r => r.data);
export const getTipiProdotto = () =>
  http.get('/catalogo/tipi').then(r => r.data);
export const createProdotto = (data) =>
  http.post('/catalogo/', data).then(r => r.data);
export const updateProdotto = (id, data) =>
  http.put(`/catalogo/${id}`, data).then(r => r.data);
export const deleteProdotto = (id) =>
  http.delete(`/catalogo/${id}`).then(r => r.data);

// ── Blocco 3: Listini ────────────────────────
export const getListini = (params = {}) =>
  http.get('/listini/', { params }).then(r => r.data);
export const getListino = (id) =>
  http.get(`/listini/${id}`).then(r => r.data);
export const getTipiCliente = () =>
  http.get('/listini/tipi-cliente').then(r => r.data);
export const createListino = (data) =>
  http.post('/listini/', data).then(r => r.data);
export const updateListino = (id, data) =>
  http.put(`/listini/${id}`, data).then(r => r.data);
export const deleteListino = (id) =>
  http.delete(`/listini/${id}`).then(r => r.data);
export const getVociListino = (listinoId) =>
  http.get(`/listini/${listinoId}/voci`).then(r => r.data);
export const addVoceListino = (listinoId, data) =>
  http.post(`/listini/${listinoId}/voci`, data).then(r => r.data);
export const updateVoceListino = (listinoId, voceId, data) =>
  http.put(`/listini/${listinoId}/voci/${voceId}`, data).then(r => r.data);
export const deleteVoceListino = (listinoId, voceId) =>
  http.delete(`/listini/${listinoId}/voci/${voceId}`).then(r => r.data);
export const getPrezzoInListino = (listinoId, prodottoId) =>
  http.get(`/listini/${listinoId}/prezzo/${prodottoId}`).then(r => r.data);

// ── Piano Finanziario ───────────────────────
export const getPianiFinanziari = (params = {}) =>
  http.get('/piani-finanziari/', { params }).then(r => r.data);
export const getTemplatePianiFinanziari = (params = {}) =>
  http.get('/piani-finanziari/templates/', { params }).then(r => r.data);
export const getAvvisiPianoFinanziario = (params = {}) =>
  http.get('/piani-finanziari/avvisi/', { params }).then(r => r.data);
export const getPianoFinanziario = (id) =>
  http.get(`/piani-finanziari/${id}`).then(r => r.data);
export const createPianoFinanziario = (data) =>
  http.post('/piani-finanziari/', data).then(r => r.data);
export const updatePianoFinanziario = (id, data) =>
  http.put(`/piani-finanziari/${id}`, data).then(r => r.data);
export const deletePianoFinanziario = (id, softDelete = true) =>
  http.delete(`/piani-finanziari/${id}`, { params: { soft_delete: softDelete } }).then(r => r.data);
export const getVociPianoFinanziario = (pianoId) =>
  http.get(`/piani-finanziari/${pianoId}/voci`).then(r => r.data);
export const addVocePianoFinanziario = (pianoId, data) =>
  http.post(`/piani-finanziari/${pianoId}/voci`, data).then(r => r.data);
export const updateVocePianoFinanziario = (pianoId, voceId, data) =>
  http.put(`/piani-finanziari/${pianoId}/voci/${voceId}`, data).then(r => r.data);
export const deleteVocePianoFinanziario = (pianoId, voceId) =>
  http.delete(`/piani-finanziari/${pianoId}/voci/${voceId}`).then(r => r.data);
export const updateVociPianoFinanziario = (pianoId, data) =>
  http.put(`/piani-finanziari/${pianoId}/voci`, data).then(r => r.data);
export const getRiepilogoPianoFinanziario = (pianoId) =>
  http.get(`/piani-finanziari/${pianoId}/riepilogo`).then(r => r.data);
export const exportPianoFinanziarioExcel = (pianoId) =>
  http.get(`/piani-finanziari/${pianoId}/export-excel`, { responseType: 'blob' });

// ── Piano Fondimpresa ───────────────────────
export const getPianiFondimpresa = (params = {}) =>
  http.get('/piani-fondimpresa/', { params }).then(r => r.data);
export const getPianoFondimpresa = (id) =>
  http.get(`/piani-fondimpresa/${id}`).then(r => r.data);
export const createPianoFondimpresa = (data) =>
  http.post('/piani-fondimpresa/', data).then(r => r.data);
export const updateVociPianoFondimpresa = (pianoId, data) =>
  http.put(`/piani-fondimpresa/${pianoId}/voci`, data).then(r => r.data);
export const updateDocumentiPianoFondimpresa = (pianoId, data) =>
  http.put(`/piani-fondimpresa/${pianoId}/documenti`, data).then(r => r.data);
export const updateDettaglioBudgetFondimpresa = (pianoId, data) =>
  http.put(`/piani-fondimpresa/${pianoId}/dettaglio-budget`, data).then(r => r.data);
export const getRiepilogoPianoFondimpresa = (pianoId) =>
  http.get(`/piani-fondimpresa/${pianoId}/riepilogo`).then(r => r.data);
export const exportPianoFondimpresaExcel = (pianoId) =>
  http.get(`/piani-fondimpresa/${pianoId}/export-excel`, { responseType: 'blob' });

// ── Blocco 4: Preventivi ─────────────────────
export const getPreventivi = (params = {}) =>
  http.get('/preventivi/', { params }).then(r => r.data);
export const getPreventivo = (id) =>
  http.get(`/preventivi/${id}`).then(r => r.data);
export const createPreventivo = (data) =>
  http.post('/preventivi/', data).then(r => r.data);
export const updatePreventivo = (id, data) =>
  http.put(`/preventivi/${id}`, data).then(r => r.data);
export const deletePreventivo = (id) =>
  http.delete(`/preventivi/${id}`).then(r => r.data);
export const inviaPreventivo = (id) =>
  http.put(`/preventivi/${id}/invia`).then(r => r.data);
export const accettaPreventivo = (id) =>
  http.put(`/preventivi/${id}/accetta`).then(r => r.data);
export const rifiutaPreventivo = (id) =>
  http.put(`/preventivi/${id}/rifiuta`).then(r => r.data);
export const convertiInOrdine = (id) =>
  http.post(`/preventivi/${id}/converti-ordine`).then(r => r.data);
export const downloadPreventivoPDF = (id) =>
  http.get(`/preventivi/${id}/pdf`, { responseType: 'blob' }).then(r => r.data);
export const addRigaPreventivo = (prevId, data) =>
  http.post(`/preventivi/${prevId}/righe`, data).then(r => r.data);
export const updateRigaPreventivo = (prevId, rigaId, data) =>
  http.put(`/preventivi/${prevId}/righe/${rigaId}`, data).then(r => r.data);
export const deleteRigaPreventivo = (prevId, rigaId) =>
  http.delete(`/preventivi/${prevId}/righe/${rigaId}`).then(r => r.data);

// ── Blocco 4: Ordini ─────────────────────────
export const getOrdini = (params = {}) =>
  http.get('/ordini/', { params }).then(r => r.data);
export const getOrdine = (id) =>
  http.get(`/ordini/${id}`).then(r => r.data);
export const updateOrdine = (id, data) =>
  http.put(`/ordini/${id}`, data).then(r => r.data);
export const deleteOrdine = (id) =>
  http.delete(`/ordini/${id}`).then(r => r.data);
export const hardDeleteOrdine = (id) =>
  http.delete(`/ordini/${id}/hard`).then(r => r.data);

export { apiService };
export default apiService;
