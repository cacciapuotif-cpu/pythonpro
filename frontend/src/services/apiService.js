/**
 * Servizio API avanzato con autenticazione, retry logic e caching
 * Updated to use shared http client from lib/http.js
 */

import { http } from '../lib/http';

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
    // Health endpoint is on root, not under /api/v1
    // Use fetch directly for this special endpoint
    const baseUrl = (process.env.REACT_APP_API_URL || 'http://localhost:8001').replace(/\/+$/, '');
    const response = await fetch(`${baseUrl}/health`);
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
    const response = await http.post('/contracts/generate', data);
    return response.data;
  }

  // Reporting
  async getTimesheetReport(filters = {}) {
    const response = await http.get('/reporting/timesheet', { params: filters });
    return response.data;
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

  // Batch operations
  async batchUpdateAssignments(updates) {
    const response = await http.post('/assignments/batch-update', { updates });
    return response.data;
  }

  // File operations - Document upload for collaborators
  async uploadDocumentoIdentita(collaboratorId, file) {
    const formData = new FormData();
    formData.append('file', file);

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
export const getCollaborator = (id) => apiService.getCollaborator(id);

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
export const generateContractPdf = (assignmentId) => http.get(`/assignments/${assignmentId}/generate-contract`, { responseType: 'blob' }).then(r => r.data);

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

// Reporting
export const getTimesheetReport = (filters) => apiService.getTimesheetReport(filters);
export const getSummaryReport = (filters) => apiService.getSummaryReport(filters);
export const getCollaboratorStats = (collaboratorId, filters) => apiService.getCollaboratorStats(collaboratorId, filters);
export const getProjectStats = (projectId, filters) => apiService.getProjectStats(projectId, filters);

export { apiService };
export default apiService;
