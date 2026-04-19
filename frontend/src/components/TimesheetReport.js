/**
 * COMPONENTE TIMESHEET REPORT
 *
 * Visualizza il report paginato delle ore lavorate:
 * - Filtri per collaboratore, progetto e periodo
 * - Statistiche aggregate lato backend
 * - Tabella presenze paginata
 * - Export asincrono CSV per dataset grandi
 */

import React, { useEffect, useState } from 'react';
import { useCollaborators, useProjects } from '../hooks/useEntity';
import apiService from '../services/apiService';
import './TimesheetReport.css';

const DEFAULT_PAGE_SIZE = 100;
const PAGE_SIZE_OPTIONS = [50, 100, 250, 500, 1000];

const TimesheetReport = () => {
  const { data: collaborators, loading: loadingCollaborators } = useCollaborators();
  const { data: projects, loading: loadingProjects } = useProjects();

  const [filters, setFilters] = useState({
    collaborator_id: '',
    project_id: '',
    start_date: '',
    end_date: '',
  });
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [report, setReport] = useState(null);
  const [loadingReport, setLoadingReport] = useState(true);
  const [error, setError] = useState(null);
  const [exportState, setExportState] = useState({
    loading: false,
    message: '',
  });

  const loading = loadingCollaborators || loadingProjects || loadingReport;

  useEffect(() => {
    let active = true;

    const loadReport = async () => {
      setLoadingReport(true);
      setError(null);
      try {
        const data = await apiService.getTimesheetReport({
          collaborator_id: filters.collaborator_id || undefined,
          project_id: filters.project_id || undefined,
          from: filters.start_date || undefined,
          to: filters.end_date || undefined,
          skip: page * pageSize,
          limit: pageSize,
        });

        if (active) {
          setReport(data);
        }
      } catch (loadError) {
        if (active) {
          setError(loadError);
        }
      } finally {
        if (active) {
          setLoadingReport(false);
        }
      }
    };

    loadReport();

    return () => {
      active = false;
    };
  }, [filters, page, pageSize]);

  const handleFilterChange = (field, value) => {
    setPage(0);
    setFilters(prev => ({
      ...prev,
      [field]: value,
    }));
  };

  const resetFilters = () => {
    setPage(0);
    setFilters({
      collaborator_id: '',
      project_id: '',
      start_date: '',
      end_date: '',
    });
  };

  const handlePageSizeChange = (value) => {
    setPage(0);
    setPageSize(parseInt(value, 10));
  };

  const pollExportUntilReady = async (exportId) => {
    for (let attempt = 0; attempt < 30; attempt += 1) {
      const result = await apiService.getTimesheetExport(exportId);
      if (result?.status === 'ready' && result.blob) {
        const url = window.URL.createObjectURL(result.blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = result.filename;
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(url);
        return true;
      }

      await new Promise(resolve => setTimeout(resolve, 1000));
    }

    return false;
  };

  const handleExport = async () => {
    setExportState({
      loading: true,
      message: 'Export in preparazione...',
    });

    try {
      const result = await apiService.startTimesheetExport({
        collaborator_id: filters.collaborator_id ? parseInt(filters.collaborator_id, 10) : null,
        project_id: filters.project_id ? parseInt(filters.project_id, 10) : null,
        from_date: filters.start_date || null,
        to_date: filters.end_date || null,
      });

      const ready = await pollExportUntilReady(result.export_id);
      setExportState({
        loading: false,
        message: ready
          ? 'Export completato.'
          : 'Export ancora in elaborazione. Riprova tra qualche secondo.',
      });
    } catch (exportError) {
      setExportState({
        loading: false,
        message: exportError?.message || 'Errore durante l\'export.',
      });
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'N/D';
    const date = new Date(dateString);
    return date.toLocaleDateString('it-IT', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    });
  };

  const formatHours = (value) => `${Number(value || 0).toFixed(1)}h`;

  const items = report?.items || [];
  const totals = report?.totali || {
    ore_totali: 0,
    numero_presenze: 0,
    per_collaboratore: [],
    per_progetto: [],
  };
  const total = report?.total || 0;
  const currentPage = total === 0 ? 0 : page + 1;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

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
      <div className="timesheet-header">
        <div className="header-title">
          <h2>⏱️ Timesheet Report</h2>
          <p>Report paginato delle ore lavorate</p>
        </div>
      </div>

      {error && (
        <div className="alert alert-error">
          <span className="alert-icon">⚠️</span>
          {error.message || 'Errore nel caricamento del report'}
        </div>
      )}

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

          <div className="filter-group">
            <label>📄 Righe per pagina</label>
            <select
              value={pageSize}
              onChange={(e) => handlePageSizeChange(e.target.value)}
            >
              {PAGE_SIZE_OPTIONS.map(option => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="filter-actions">
          <button className="btn-secondary" onClick={resetFilters}>
            🔄 Resetta Filtri
          </button>
          <button
            className="btn-secondary"
            onClick={handleExport}
            disabled={exportState.loading}
          >
            {exportState.loading ? '⏳ Export...' : '⬇️ Export CSV'}
          </button>
        </div>

        {exportState.message && (
          <div className="timesheet-export-status">
            {exportState.message}
          </div>
        )}
      </div>

      <div className="timesheet-stats">
        <div className="stat-card">
          <div className="stat-icon">⏱️</div>
          <div className="stat-content">
            <div className="stat-value">{Number(totals.ore_totali || 0).toFixed(1)}</div>
            <div className="stat-label">Ore Totali</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">📋</div>
          <div className="stat-content">
            <div className="stat-value">{total}</div>
            <div className="stat-label">Presenze Totali</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">👥</div>
          <div className="stat-content">
            <div className="stat-value">{totals.per_collaboratore.length}</div>
            <div className="stat-label">Collaboratori in Pagina</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">📁</div>
          <div className="stat-content">
            <div className="stat-value">{totals.per_progetto.length}</div>
            <div className="stat-label">Progetti in Pagina</div>
          </div>
        </div>
      </div>

      <div className="timesheet-section">
        <div className="timesheet-section-header">
          <h3>📋 Dettaglio Presenze</h3>
          <div className="timesheet-pagination-meta">
            Pagina {currentPage} di {totalPages} • {items.length} righe mostrate su {total}
          </div>
        </div>

        {items.length === 0 ? (
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
                  <th>Ore</th>
                  <th>Note</th>
                </tr>
              </thead>
              <tbody>
                {items.map(att => (
                  <tr key={att.id}>
                    <td>{formatDate(att.data)}</td>
                    <td>{att.collaboratore?.nome_completo || 'N/D'}</td>
                    <td>{att.progetto?.nome || 'N/D'}</td>
                    <td className="hours-cell">
                      <span className="hours-badge">{formatHours(att.ore_lavorate)}</span>
                    </td>
                    <td className="notes-cell">{att.note || '-'}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <td colSpan="3" className="total-label">Totale Ore Filtrate</td>
                  <td className="hours-cell">
                    <span className="hours-badge total">{formatHours(totals.ore_totali)}</span>
                  </td>
                  <td></td>
                </tr>
              </tfoot>
            </table>
          </div>
        )}

        <div className="timesheet-pagination">
          <button
            className="btn-secondary"
            onClick={() => setPage(prev => Math.max(0, prev - 1))}
            disabled={page === 0}
          >
            ← Precedente
          </button>
          <button
            className="btn-secondary"
            onClick={() => setPage(prev => prev + 1)}
            disabled={!report?.has_more}
          >
            Successiva →
          </button>
        </div>
      </div>

      {totals.per_collaboratore.length > 0 && (
        <div className="timesheet-section">
          <h3>👥 Riepilogo Collaboratori</h3>
          <div className="summary-grid">
            {totals.per_collaboratore.map((item) => (
              <div key={item.id} className="summary-card">
                <div className="summary-header">
                  <span className="summary-name">{item.nome}</span>
                </div>
                <div className="summary-stats">
                  <div className="summary-stat">
                    <span className="summary-label">Ore in pagina</span>
                    <span className="summary-value">{Number(item.ore_totali || 0).toFixed(1)}h</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {totals.per_progetto.length > 0 && (
        <div className="timesheet-section">
          <h3>📁 Riepilogo Progetti</h3>
          <div className="summary-grid">
            {totals.per_progetto.map((item) => (
              <div key={item.id} className="summary-card">
                <div className="summary-header">
                  <span className="summary-name">{item.nome}</span>
                </div>
                <div className="summary-stats">
                  <div className="summary-stat">
                    <span className="summary-label">Ore in pagina</span>
                    <span className="summary-value">{Number(item.ore_totali || 0).toFixed(1)}h</span>
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
