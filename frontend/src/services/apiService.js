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

  async updateCurrentUser(profile) {
    const response = await http.patch('/auth/me', profile);
    return response.data;
  }

  async getCurrentUserAvatar() {
    const response = await http.get('/auth/me/avatar', { responseType: 'blob' });
    return response.data;
  }

  async uploadCurrentUserAvatar(file) {
    const formData = new FormData();
    formData.append('file', file);
    const response = await http.post('/auth/me/avatar', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  }

  async deleteCurrentUserAvatar() {
    await http.delete('/auth/me/avatar');
  }

  async changePassword(passwords) {
    const response = await http.post('/auth/change-password', passwords);
    return response.data;
  }

  async requestPasswordReset(email) {
    const response = await http.post('/auth/forgot-password', { email });
    return response.data;
  }

  async resetPassword(payload) {
    const response = await http.post('/auth/reset-password', payload);
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

  // Amministrazione utenti
  async listUsers() {
    const response = await http.get('/admin/users');
    return response.data;
  }

  async createUser(payload) {
    const response = await http.post('/admin/users', payload);
    return response.data;
  }

  async updateUser(userId, payload) {
    const response = await http.patch(`/admin/users/${userId}`, payload);
    return response.data;
  }

  async deleteUser(userId) {
    await http.delete(`/admin/users/${userId}`);
  }

  async resendUserInvite(userId) {
    const response = await http.post(`/admin/users/${userId}/resend-invite`);
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
      http.get('/collaborators/', { params })
    );

    return response.data;
  }

  async getCollaborator(id) {
    const response = await http.get(`/collaborators/${id}`);
    return response.data;
  }

  async createCollaborator(data) {
    const response = await http.post('/collaborators/', data);
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
    if (filters.isActive !== undefined) params.is_active = filters.isActive;

    const response = await retryRequest(() =>
      http.get('/projects/', { params })
    );

    return response.data;
  }

  async getProject(id) {
    const response = await http.get(`/projects/${id}`);
    return response.data;
  }

  async getProjectModuliFormativi(id) {
    const response = await http.get(`/projects/${id}/moduli-formativi`);
    return response.data;
  }

  async getProjectModuloVocePiano(projectId, moduloId) {
    const response = await http.get(`/projects/${projectId}/moduli-formativi/${moduloId}/voce-piano`);
    return response.data;
  }

  async createProject(data) {
    const response = await http.post('/projects/', data);
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

  async getCalendarAttendances(filters = {}) {
    const params = {
      start_date: filters.startDate,
      end_date: filters.endDate,
    };
    if (filters.collaboratorIds && filters.collaboratorIds.length) {
      params.collaborator_ids = filters.collaboratorIds.join(',');
    }
    if (filters.projectIds && filters.projectIds.length) {
      params.project_ids = filters.projectIds.join(',');
    }
    if (filters.includeClosedProjects) params.include_closed_projects = true;
    if (filters.onlyMine) params.only_mine = true;

    const response = await http.get('/attendances/calendar', { params });
    return response.data;
  }

  async getAttendance(id) {
    const response = await http.get(`/attendances/${id}`);
    return response.data;
  }

  async createAttendance(data) {
    const response = await http.post('/attendances/', data);
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
      http.get('/assignments/', { params })
    );

    return response.data;
  }

  async getAssignment(id) {
    const response = await http.get(`/assignments/${id}`);
    return response.data;
  }

  async createAssignment(data) {
    const response = await http.post('/assignments/', data);
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
    try {
      // La health del backend è esposta su `/health` (fuori dal prefisso
      // /api/v1). L'istanza axios `http` ha baseURL = apiBaseUrl (…/api/v1),
      // quindi un URL relativo verrebbe prefissato con /api/v1 → 404 in
      // same-origin. Forziamo baseURL = apiRootUrl per questa richiesta:
      // - same-origin: apiRootUrl='' → hit su origin '/health'
      // - LAN: apiRootUrl='http://IP:8001' → hit su 'http://IP:8001/health'
      const response = await http.get('/health', { baseURL: apiRootUrl });
      return response.data;
    } catch (err) {
      throw new Error(`Health check failed: ${err.response?.status || err.message}`);
    }
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
    const response = await http.post('/entities/', data);
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
    const response = await http.post('/contracts/', data);
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

  async downloadAssignmentContract(assignmentId) {
    const response = await http.get(`/assignments/${assignmentId}/contract`, {
      responseType: 'blob',
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
    const response = await http.post('/piani-finanziari/', data);
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
export const getProjectModuliFormativi = (id) => apiService.getProjectModuliFormativi(id);

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
export const downloadAssignmentContract = (assignmentId) => apiService.downloadAssignmentContract(assignmentId);

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
export const getAvvisoDeletionImpact = (id) =>
  http.get(`/avvisi/${id}/deletion-impact`).then(r => r.data);
export const permanentlyDeleteAvviso = (id, confirmationPhrase) =>
  http.delete(`/avvisi/${id}/permanent`, {
    data: {
      confirmation_phrase: confirmationPhrase,
      linked_records_confirmed: true,
    },
  }).then(r => r.data);
export const getAvvisoRevisioni = (id) =>
  http.get(`/avvisi/${id}/revisioni`).then(r => r.data);
export const retryAvvisoExtraction = (avvisoId, revisionId) =>
  http.post(
    `/avvisi/${avvisoId}/revisioni/${revisionId}/estrazione/riprova`,
    {},
    { timeout: 180000 },
  ).then(r => r.data);
export const ingestAvvisoRevision = (
  id,
  { file, titolo, etichettaRevisione = '', eseguiEstrazione = true },
) => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('titolo', titolo);
  if (etichettaRevisione) formData.append('etichetta_revisione', etichettaRevisione);
  formData.append('esegui_estrazione', String(eseguiEstrazione));
  return http.post(`/avvisi/${id}/revisioni/ingest`, formData, {
    timeout: 180000,
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then(r => r.data);
};

// ── E3.3: Archivio "Chiedi all'archivio" ──────────────────────────────────
// Due rotte di sola lettura semantica (RBAC: aperte ai 3 ruoli, vedi
// auth/permissions.js). La ricerca è una GET; /chiedi è un POST solo perché la
// domanda in linguaggio naturale viaggia nel body.
export const searchArchivio = (q, { avvisoId, tipoFondo, limit } = {}) => {
  const params = { q };
  if (avvisoId) params.avviso_id = avvisoId;
  if (tipoFondo) params.tipo_fondo = tipoFondo;
  if (limit) params.limit = limit;
  return http.get('/archivio/search', { params }).then(r => r.data);
};
export const chiediArchivio = ({ domanda, avvisoId, tipoFondo } = {}) => {
  const body = { domanda };
  if (avvisoId) body.avviso_id = avvisoId;
  if (tipoFondo) body.tipo_fondo = tipoFondo;
  return http.post('/archivio/chiedi', body).then(r => r.data);
};

// Agents
export const getAgentsCatalog = () =>
  http.get('/agents/').then(r => r.data);
export const getAgentInfo = (agentType) =>
  http.get(`/agents/${agentType}/info`).then(r => r.data);
export const getAgentLlmHealth = () =>
  http.get('/agents/llm/health').then(r => r.data);
export const getAgentsSystemHealth = () =>
  http.get('/agents/system-health').then(r => r.data);
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
export const sendAgentSuggestionEmail = (suggestionId, data) =>
  http.post(`/agent-suggestions/${suggestionId}/send-email`, data).then(r => r.data);
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
export const archiveEmailInboxItem = (itemId) =>
  http.post(`/email-inbox/${itemId}/archive`).then(r => r.data);
export const sendEmailInboxFollowup = (itemId, data) =>
  http.post(`/email-inbox/${itemId}/send-followup`, data).then(r => r.data);
export const downloadEmailInboxAttachment = (itemId) =>
  http.get(`/email-inbox/items/${itemId}/attachment`, { responseType: 'blob' });
export const manualUpdateCollaborator = (collaboratorId, data) =>
  http.patch(`/collaborators/${collaboratorId}/manual-update`, data).then(r => r.data);

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

// UX-9: l'albero per azienda ha bisogno di TUTTI gli allievi, non della prima
// pagina. `/allievi/` e' paginato e tetto a 100 per pagina, quindi si seguono
// le pagine; il tetto di sicurezza evita il ciclo infinito su una API che
// dichiarasse `has_next` per sbaglio, e chi chiama sa se l'elenco e' parziale.
export const caricaTuttiGliAllievi = async ({ maxPagine = 20, ...params } = {}) => {
  const items = [];
  let page = 1;

  for (; page <= maxPagine; page += 1) {
    // eslint-disable-next-line no-await-in-loop
    const data = await http.get('/allievi/', { params: { ...params, page, limit: 100 } })
      .then(r => r.data);

    if (Array.isArray(data)) return { items: [...items, ...data], troncato: false };

    items.push(...(data.items || []));
    if (!data.has_next) return { items, troncato: false };
  }

  return { items, troncato: true };
};
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
export const getPianoFinanziario = (id) =>
  http.get(`/piani-finanziari/${id}`).then(r => r.data);
export const getProjectModuloVocePiano = (projectId, moduloId) =>
  http.get(`/projects/${projectId}/moduli-formativi/${moduloId}/voce-piano`).then(r => r.data);
export const createPianoFinanziario = (data) =>
  http.post('/piani-finanziari/', data).then(r => r.data);
export const createPianoFinanziarioFromTemplate = (data) =>
  http.post('/piani-finanziari/from-template', data).then(r => r.data);
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
// ── Piano Templates (E1.5: wizard piano da template) ───────────────────────
export const getPianoTemplates = (params = {}) =>
  http.get('/piano-templates/', { params }).then(r => r.data);
export const getPianoTemplateAnteprima = (templateId, params = {}) =>
  http.get(`/piano-templates/${templateId}/anteprima`, { params }).then(r => r.data);

export const getProjectBeneficiari = (projectId) =>
  http.get(`/projects/${projectId}/beneficiari`).then(r => r.data);
export const updateProjectBeneficiarioRegime = (projectId, aziendaId, data) =>
  http.patch(`/projects/${projectId}/beneficiari/${aziendaId}/regime`, data).then(r => r.data);

// ── UX-8: dissociazione allievi/aziende dal progetto ──────────────────────
// Il corpo e' opzionale: senza `{forza, motivo}` valgono le guardie piene.
export const dissociaAllievoDaProgetto = (projectId, allievoId, payload) =>
  http.delete(`/projects/${projectId}/allievi/${allievoId}`, { data: payload }).then(r => r.data);
export const dissociaAziendaDaProgetto = (projectId, aziendaId, payload) =>
  http.delete(`/projects/${projectId}/aziende/${aziendaId}`, { data: payload }).then(r => r.data);

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

// ── FAPI document upload ──────────────────────────────────────────────────
export const uploadConvenzione = (file) => {
  const fd = new FormData();
  fd.append('file', file);
  return http.post('/projects/upload-convenzione', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then(r => r.data);
};
export const confirmConvenzione = (previewToken, options = {}) =>
  http.post('/projects/confirm-convenzione', {
    preview_token: previewToken,
    ...options,
  }).then(r => r.data);

// UX-6: dentro un progetto il documento si ASSOCIA, non crea un gemello.
export const uploadConvenzioneProgetto = (projectId, file) => {
  const fd = new FormData();
  fd.append('file', file);
  return http.post(`/projects/${projectId}/upload-convenzione`, fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then(r => r.data);
};
export const confirmConvenzioneProgetto = (
  projectId,
  previewToken,
  campiDaApplicare = [],
  modalita,
  tipoDocumento,
) =>
  http.post(`/projects/${projectId}/confirm-convenzione`, {
    preview_token: previewToken,
    campi_da_applicare: campiDaApplicare,
    ...(modalita ? { modalita } : {}),
    ...(tipoDocumento ? { tipo_documento: tipoDocumento } : {}),
  }).then(r => r.data);

export const getDocumentiProgetto = (projectId) =>
  http.get(`/projects/${projectId}/documenti`).then(r => r.data);
export const downloadDocumentoProgetto = (projectId, documentoId) =>
  http.get(`/projects/${projectId}/documenti/${documentoId}/download`, {
    responseType: 'blob',
  }).then(r => r.data);

export const uploadFormulario = (projectId, file) => {
  const fd = new FormData();
  fd.append('file', file);
  return http.post(`/projects/${projectId}/upload-formulario`, fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then(r => r.data);
};
export const confirmFormulario = (projectId, previewToken) =>
  http.post(`/projects/${projectId}/confirm-formulario`, { preview_token: previewToken }).then(r => r.data);

export const uploadPianoFinanziario = (projectId, file) => {
  const fd = new FormData();
  fd.append('file', file);
  return http.post(`/projects/${projectId}/upload-piano-finanziario`, fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then(r => r.data);
};
export const confirmPianoFinanziario = (projectId, previewToken) =>
  http.post(`/projects/${projectId}/confirm-piano-finanziario`, { preview_token: previewToken }).then(r => r.data);

// ── Fondimpresa document upload ───────────────────────────────────────────
export const uploadAmmissioneFondimpresa = (file) => {
  const fd = new FormData();
  fd.append('file', file);
  return http.post('/projects/fondimpresa/upload-ammissione', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then(r => r.data);
};
export const confirmAmmissioneFondimpresa = (previewToken) =>
  http.post('/projects/fondimpresa/confirm-ammissione', { preview_token: previewToken }).then(r => r.data);

// UX-6: dalla scheda di un progetto la lettera si ALLEGA al progetto aperto.
export const uploadAmmissioneFondimpresaProgetto = (projectId, file) => {
  const fd = new FormData();
  fd.append('file', file);
  return http.post(`/projects/${projectId}/fondimpresa/upload-ammissione`, fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then(r => r.data);
};
export const confirmAmmissioneFondimpresaProgetto = (projectId, previewToken, campiDaApplicare = []) =>
  http.post(`/projects/${projectId}/fondimpresa/confirm-ammissione`, {
    preview_token: previewToken,
    campi_da_applicare: campiDaApplicare,
  }).then(r => r.data);

export const uploadRiepilogoFondimpresa = (projectId, file) => {
  const fd = new FormData();
  fd.append('file', file);
  return http.post(`/projects/${projectId}/fondimpresa/upload-riepilogo`, fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then(r => r.data);
};
export const confirmRiepilogoFondimpresa = (projectId, previewToken) =>
  http.post(`/projects/${projectId}/fondimpresa/confirm-riepilogo`, { preview_token: previewToken }).then(r => r.data);

export { apiService };
export default apiService;
