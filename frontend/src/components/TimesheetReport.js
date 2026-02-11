/**
 * COMPONENTE TIMESHEET REPORT
 *
 * Visualizza un report completo delle ore lavorate:
 * - Tutte le presenze in formato tabellare
 * - Filtri per collaboratore, progetto, periodo
 * - Totali ore per collaboratore e progetto
 * - Statistiche aggregate
 */

import React, { useState } from 'react';
import { useAttendances, useCollaborators, useProjects } from '../hooks/useEntity';
import './TimesheetReport.css';

const TimesheetReport = () => {
  // ==========================================
  // CONTEXT E HOOKS
  // ==========================================

  // Carica dati dal Context con caching automatico
  const { data: attendances, loading: loadingAttendances, error: errorAttendances } = useAttendances();
  const { data: collaborators, loading: loadingCollaborators } = useCollaborators();
  const { data: projects, loading: loadingProjects } = useProjects();

  // Stati UI - filtri locali per la vista
  const [filters, setFilters] = useState({
    collaborator_id: '',
    project_id: '',
    start_date: '',
    end_date: '',
  });

  // Combina gli stati di loading
  const loading = loadingAttendances || loadingCollaborators || loadingProjects;
  const error = errorAttendances;

  // ==========================================
  // FILTRI E CALCOLI
  // ==========================================

  // Filtra le presenze in base ai filtri selezionati
  const filteredAttendances = attendances.filter(att => {
    // Filtro collaboratore
    if (filters.collaborator_id && att.collaborator_id !== parseInt(filters.collaborator_id)) {
      return false;
    }

    // Filtro progetto
    if (filters.project_id && att.project_id !== parseInt(filters.project_id)) {
      return false;
    }

    // Filtro data inizio
    if (filters.start_date) {
      const attDate = new Date(att.date);
      const startDate = new Date(filters.start_date);
      if (attDate < startDate) return false;
    }

    // Filtro data fine
    if (filters.end_date) {
      const attDate = new Date(att.date);
      const endDate = new Date(filters.end_date);
      if (attDate > endDate) return false;
    }

    return true;
  });

  // Calcola totale ore
  const totalHours = filteredAttendances.reduce((sum, att) => sum + (att.hours || 0), 0);

  // Raggruppa per collaboratore
  const hoursByCollaborator = filteredAttendances.reduce((acc, att) => {
    const id = att.collaborator_id;
    if (!acc[id]) {
      acc[id] = {
        collaborator: collaborators.find(c => c.id === id),
        hours: 0,
        count: 0
      };
    }
    acc[id].hours += att.hours || 0;
    acc[id].count += 1;
    return acc;
  }, {});

  // Raggruppa per progetto
  const hoursByProject = filteredAttendances.reduce((acc, att) => {
    const id = att.project_id;
    if (!acc[id]) {
      acc[id] = {
        project: projects.find(p => p.id === id),
        hours: 0,
        count: 0
      };
    }
    acc[id].hours += att.hours || 0;
    acc[id].count += 1;
    return acc;
  }, {});

  // ==========================================
  // GESTIONE FILTRI
  // ==========================================

  const handleFilterChange = (field, value) => {
    setFilters(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const resetFilters = () => {
    setFilters({
      collaborator_id: '',
      project_id: '',
      start_date: '',
      end_date: '',
    });
  };

  // ==========================================
  // HELPER FUNCTIONS
  // ==========================================

  const formatDate = (dateString) => {
    if (!dateString) return 'N/D';
    const date = new Date(dateString);
    return date.toLocaleDateString('it-IT', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric'
    });
  };

  const formatTime = (timeString) => {
    if (!timeString) return 'N/D';
    const date = new Date(timeString);
    return date.toLocaleTimeString('it-IT', {
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getCollaboratorName = (id) => {
    const collab = collaborators.find(c => c.id === id);
    return collab ? `${collab.first_name} ${collab.last_name}` : 'N/D';
  };

  const getProjectName = (id) => {
    const project = projects.find(p => p.id === id);
    return project ? project.name : 'N/D';
  };

  // ==========================================
  // RENDER
  // ==========================================

  if (loading) {
    return (
      <div className="timesheet-report">
        <div className="loading-spinner">
          <div className="spinner"></div>
          <p>Caricamento timesheet...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="timesheet-report">
      {/* HEADER */}
      <div className="timesheet-header">
        <div className="header-title">
          <h2>⏱️ Timesheet Report</h2>
          <p>Report completo delle ore lavorate</p>
        </div>
      </div>

      {/* MESSAGGI ERRORE */}
      {error && (
        <div className="alert alert-error">
          <span className="alert-icon">⚠️</span>
          {error.message || 'Errore nel caricamento dei dati'}
        </div>
      )}

      {/* FILTRI */}
      <div className="timesheet-filters">
        <div className="filters-grid">
          <div className="filter-group">
            <label>👤 Collaboratore</label>
            <select
              value={filters.collaborator_id}
              onChange={(e) => handleFilterChange('collaborator_id', e.target.value)}
            >
              <option value="">Tutti i collaboratori</option>
              {collaborators.map(collab => (
                <option key={collab.id} value={collab.id}>
                  {collab.first_name} {collab.last_name}
                </option>
              ))}
            </select>
          </div>

          <div className="filter-group">
            <label>📁 Progetto</label>
            <select
              value={filters.project_id}
              onChange={(e) => handleFilterChange('project_id', e.target.value)}
            >
              <option value="">Tutti i progetti</option>
              {projects.map(project => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </select>
          </div>

          <div className="filter-group">
            <label>📅 Da Data</label>
            <input
              type="date"
              value={filters.start_date}
              onChange={(e) => handleFilterChange('start_date', e.target.value)}
            />
          </div>

          <div className="filter-group">
            <label>📅 A Data</label>
            <input
              type="date"
              value={filters.end_date}
              onChange={(e) => handleFilterChange('end_date', e.target.value)}
            />
          </div>
        </div>

        <div className="filter-actions">
          <button className="btn-secondary" onClick={resetFilters}>
            🔄 Resetta Filtri
          </button>
        </div>
      </div>

      {/* STATISTICHE RIEPILOGATIVE */}
      <div className="timesheet-stats">
        <div className="stat-card">
          <div className="stat-icon">⏱️</div>
          <div className="stat-content">
            <div className="stat-value">{totalHours.toFixed(1)}</div>
            <div className="stat-label">Ore Totali</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">📋</div>
          <div className="stat-content">
            <div className="stat-value">{filteredAttendances.length}</div>
            <div className="stat-label">Presenze</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">👥</div>
          <div className="stat-content">
            <div className="stat-value">{Object.keys(hoursByCollaborator).length}</div>
            <div className="stat-label">Collaboratori</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">📁</div>
          <div className="stat-content">
            <div className="stat-value">{Object.keys(hoursByProject).length}</div>
            <div className="stat-label">Progetti</div>
          </div>
        </div>
      </div>

      {/* TABELLA PRESENZE */}
      <div className="timesheet-section">
        <h3>📋 Dettaglio Presenze</h3>

        {filteredAttendances.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">📋</div>
            <h4>Nessuna presenza trovata</h4>
            <p>Prova a modificare i filtri o aggiungi nuove presenze dal calendario</p>
          </div>
        ) : (
          <div className="table-container">
            <table className="timesheet-table">
              <thead>
                <tr>
                  <th>Data</th>
                  <th>Collaboratore</th>
                  <th>Progetto</th>
                  <th>Ora Inizio</th>
                  <th>Ora Fine</th>
                  <th>Ore</th>
                  <th>Note</th>
                </tr>
              </thead>
              <tbody>
                {filteredAttendances.map(att => (
                  <tr key={att.id}>
                    <td>{formatDate(att.date)}</td>
                    <td>{getCollaboratorName(att.collaborator_id)}</td>
                    <td>{getProjectName(att.project_id)}</td>
                    <td>{formatTime(att.start_time)}</td>
                    <td>{formatTime(att.end_time)}</td>
                    <td className="hours-cell">
                      <span className="hours-badge">{att.hours?.toFixed(1)}h</span>
                    </td>
                    <td className="notes-cell">{att.notes || '-'}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <td colSpan="5" className="total-label">Totale Ore</td>
                  <td className="hours-cell">
                    <span className="hours-badge total">{totalHours.toFixed(1)}h</span>
                  </td>
                  <td></td>
                </tr>
              </tfoot>
            </table>
          </div>
        )}
      </div>

      {/* RIEPILOGO PER COLLABORATORE */}
      {Object.keys(hoursByCollaborator).length > 0 && (
        <div className="timesheet-section">
          <h3>👥 Riepilogo per Collaboratore</h3>
          <div className="summary-grid">
            {Object.values(hoursByCollaborator).map((item, index) => (
              <div key={index} className="summary-card">
                <div className="summary-header">
                  <span className="summary-name">
                    {item.collaborator
                      ? `${item.collaborator.first_name} ${item.collaborator.last_name}`
                      : 'N/D'}
                  </span>
                </div>
                <div className="summary-stats">
                  <div className="summary-stat">
                    <span className="summary-label">Ore Totali</span>
                    <span className="summary-value">{item.hours.toFixed(1)}h</span>
                  </div>
                  <div className="summary-stat">
                    <span className="summary-label">Presenze</span>
                    <span className="summary-value">{item.count}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* RIEPILOGO PER PROGETTO */}
      {Object.keys(hoursByProject).length > 0 && (
        <div className="timesheet-section">
          <h3>📁 Riepilogo per Progetto</h3>
          <div className="summary-grid">
            {Object.values(hoursByProject).map((item, index) => (
              <div key={index} className="summary-card">
                <div className="summary-header">
                  <span className="summary-name">
                    {item.project ? item.project.name : 'N/D'}
                  </span>
                </div>
                <div className="summary-stats">
                  <div className="summary-stat">
                    <span className="summary-label">Ore Totali</span>
                    <span className="summary-value">{item.hours.toFixed(1)}h</span>
                  </div>
                  <div className="summary-stat">
                    <span className="summary-label">Presenze</span>
                    <span className="summary-value">{item.count}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default TimesheetReport;
