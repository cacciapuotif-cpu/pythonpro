import React, { useState, useMemo } from 'react';
import CollaboratorProjectsRow from './CollaboratorProjectsRow';

/**
 * Tabella collaboratori con filtraggio, ordinamento e paginazione
 * Gestisce la visualizzazione dei collaboratori con dettagli espandibili
 */
const CollaboratorsTable = ({
  collaborators,
  projects,
  assignments,
  onEdit,
  onDelete,
  onOpenAssignmentModal,
  onAssignProject,
  onRemoveProject,
  onEditAssignment,
  onDownloadContract
}) => {
  // Stati per filtri, ricerca e paginazione
  const [searchTerm, setSearchTerm] = useState('');
  const [filterPosition, setFilterPosition] = useState('');
  const [sortField, setSortField] = useState('first_name');
  const [sortDirection, setSortDirection] = useState('asc');
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(10);

  // Stato per espansione righe collaboratori
  const [expandedRows, setExpandedRows] = useState(new Set());

  /**
   * FILTRA E ORDINA I COLLABORATORI
   */
  const getFilteredCollaborators = () => {
    let filtered = [...collaborators];

    // Filtro per termine di ricerca
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      filtered = filtered.filter(collaborator =>
        collaborator.first_name.toLowerCase().includes(term) ||
        collaborator.last_name.toLowerCase().includes(term) ||
        collaborator.email.toLowerCase().includes(term) ||
        (collaborator.fiscal_code && collaborator.fiscal_code.toLowerCase().includes(term)) ||
        (collaborator.position && collaborator.position.toLowerCase().includes(term))
      );
    }

    // Filtro per posizione
    if (filterPosition) {
      filtered = filtered.filter(collaborator =>
        collaborator.position && collaborator.position.toLowerCase().includes(filterPosition.toLowerCase())
      );
    }

    // Ordinamento
    filtered.sort((a, b) => {
      let aValue = a[sortField] || '';
      let bValue = b[sortField] || '';

      if (typeof aValue === 'string') {
        aValue = aValue.toLowerCase();
        bValue = bValue.toLowerCase();
      }

      if (aValue < bValue) return sortDirection === 'asc' ? -1 : 1;
      if (aValue > bValue) return sortDirection === 'asc' ? 1 : -1;
      return 0;
    });

    return filtered;
  };

  /**
   * OTTIENI COLLABORATORI PAGINATI
   */
  const getPaginatedCollaborators = () => {
    const filtered = getFilteredCollaborators();
    const startIndex = (currentPage - 1) * itemsPerPage;
    const endIndex = startIndex + itemsPerPage;
    return {
      items: filtered.slice(startIndex, endIndex),
      totalItems: filtered.length,
      totalPages: Math.ceil(filtered.length / itemsPerPage)
    };
  };

  /**
   * OTTIENI POSIZIONI UNICHE PER IL FILTRO
   */
  const getUniquePositions = () => {
    const positions = collaborators
      .map(c => c.position)
      .filter(p => p && p.trim())
      .map(p => p.trim());
    return [...new Set(positions)].sort();
  };

  /**
   * TOGGLE ESPANSIONE RIGA COLLABORATORE
   */
  const toggleRowExpansion = (collaboratorId) => {
    const newExpanded = new Set(expandedRows);
    if (newExpanded.has(collaboratorId)) {
      newExpanded.delete(collaboratorId);
    } else {
      newExpanded.add(collaboratorId);
    }
    setExpandedRows(newExpanded);
  };

  // Calcola dati paginati
  const { items, totalItems, totalPages } = getPaginatedCollaborators();

  return (
    <div className="collaborators-list">
      <div className="list-header">
        <h2>📋 Collaboratori Registrati ({collaborators.length})</h2>

        {/* CONTROLLI DI FILTRAGGIO E VISTA */}
        <div className="list-controls">
          <div className="search-filters">
            <input
              type="text"
              placeholder="🔍 Cerca per nome, cognome, email o posizione..."
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value);
                setCurrentPage(1);
              }}
              className="search-input"
            />

            <select
              value={filterPosition}
              onChange={(e) => {
                setFilterPosition(e.target.value);
                setCurrentPage(1);
              }}
              className="filter-select"
            >
              <option value="">Tutte le posizioni</option>
              {getUniquePositions().map(position => (
                <option key={position} value={position}>{position}</option>
              ))}
            </select>

            <select
              value={sortField}
              onChange={(e) => setSortField(e.target.value)}
              className="sort-select"
            >
              <option value="last_name">Ordina per Cognome</option>
              <option value="first_name">Ordina per Nome</option>
              <option value="email">Ordina per Email</option>
              <option value="position">Ordina per Posizione</option>
            </select>

            <button
              onClick={() => setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc')}
              className="sort-direction-btn"
              title={`Ordinamento ${sortDirection === 'asc' ? 'crescente' : 'decrescente'}`}
            >
              {sortDirection === 'asc' ? '⬆️' : '⬇️'}
            </button>
          </div>

          <div className="view-controls">
            <label>Mostra per pagina:</label>
            <select
              value={itemsPerPage}
              onChange={(e) => {
                setItemsPerPage(parseInt(e.target.value));
                setCurrentPage(1);
              }}
              className="items-per-page-select"
            >
              <option value={10}>10</option>
              <option value={25}>25</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
            </select>
          </div>
        </div>
      </div>

      {/* EMPTY STATE */}
      {totalItems === 0 ? (
        <div className="empty-state">
          {collaborators.length === 0 ? (
            <>
              <p>👥 Nessun collaboratore registrato</p>
              <p>Usa il pulsante "Nuovo Collaboratore" per aggiungerne uno!</p>
            </>
          ) : (
            <>
              <p>🔍 Nessun collaboratore trovato con i filtri attuali</p>
              <p>Prova a modificare i criteri di ricerca</p>
            </>
          )}
        </div>
      ) : (
        <>
          {/* INFORMAZIONI PAGINAZIONE */}
          <div className="pagination-info">
            <span>
              Mostrando {((currentPage - 1) * itemsPerPage) + 1}-{Math.min(currentPage * itemsPerPage, totalItems)} di {totalItems} collaboratori
            </span>
          </div>

          {/* TABELLA COLLABORATORI */}
          <div className="collaborators-table">
            <table className="compact-table">
              <thead>
                <tr>
                  <th>Nome Completo</th>
                  <th>Codice Fiscale</th>
                  <th>Progetti</th>
                  <th className="actions-column">Azioni</th>
                </tr>
              </thead>
              <tbody>
                {items.map(collaborator => {
                  const isExpanded = expandedRows.has(collaborator.id);
                  const hasProjects = collaborator.projects && collaborator.projects.length > 0;

                  // Calcola progetti disponibili per questo collaboratore
                  const assignedProjectIds = collaborator.projects ? collaborator.projects.map(p => p.id) : [];
                  const availableProjects = projects.filter(
                    project => !assignedProjectIds.includes(project.id)
                  );

                  return (
                    <React.Fragment key={collaborator.id}>
                      {/* RIGA PRINCIPALE */}
                      <tr className="collaborator-row">
                        <td className="name-cell">
                          <strong>{collaborator.first_name} {collaborator.last_name}</strong>
                          {collaborator.position && (
                            <small className="position-tag">{collaborator.position}</small>
                          )}
                        </td>
                        <td className="fiscal-code-cell">{collaborator.fiscal_code || 'N/A'}</td>
                        <td className="projects-cell">
                          <div style={{display: 'flex', alignItems: 'center', gap: '8px'}}>
                            {hasProjects ? (
                              <>
                                <div className="projects-summary-compact">
                                  <span className="project-count">
                                    📁 {collaborator.projects.length} {collaborator.projects.length === 1 ? 'progetto' : 'progetti'}
                                  </span>
                                  <span className="project-status-compact">
                                    (🟢 {collaborator.projects.filter(p => p.status === 'active').length} attivi)
                                  </span>
                                </div>
                                <button
                                  onClick={() => toggleRowExpansion(collaborator.id)}
                                  className="expand-btn"
                                  title={isExpanded ? 'Nascondi dettagli' : 'Mostra dettagli progetti'}
                                >
                                  {isExpanded ? '👁️ Nascondi' : '👁️ Visualizza'}
                                </button>
                              </>
                            ) : (
                              <span className="no-projects-text">Nessun progetto</span>
                            )}
                          </div>
                        </td>
                        <td className="actions-cell">
                          <button
                            onClick={() => onEdit(collaborator)}
                            className="action-btn edit-btn"
                            title="Modifica tutti i dettagli"
                          >
                            ✏️ Modifica
                          </button>
                          <button
                            onClick={() => onOpenAssignmentModal(collaborator)}
                            className="action-btn assign-btn"
                            title="Assegna a progetto"
                          >
                            ➕ Assegna
                          </button>
                          <button
                            onClick={() => onDelete(collaborator.id)}
                            className="action-btn delete-btn"
                            title="Elimina collaboratore"
                          >
                            🗑️
                          </button>
                        </td>
                      </tr>

                      {/* RIGA ESPANSA CON DETTAGLI PROGETTI */}
                      {isExpanded && (
                        <CollaboratorProjectsRow
                          collaborator={collaborator}
                          projects={projects}
                          assignments={assignments}
                          availableProjects={availableProjects}
                          onAssignProject={onAssignProject}
                          onRemoveProject={onRemoveProject}
                          onOpenAssignmentModal={onOpenAssignmentModal}
                          onEditAssignment={onEditAssignment}
                          onDownloadContract={onDownloadContract}
                        />
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* CONTROLLI PAGINAZIONE */}
          {totalPages > 1 && (
            <div className="pagination-controls">
              <button
                onClick={() => setCurrentPage(1)}
                disabled={currentPage === 1}
                className="pagination-btn"
              >
                ⏮️ Prima
              </button>

              <button
                onClick={() => setCurrentPage(currentPage - 1)}
                disabled={currentPage === 1}
                className="pagination-btn"
              >
                ⬅️ Precedente
              </button>

              <span className="pagination-current">
                Pagina {currentPage} di {totalPages}
              </span>

              <button
                onClick={() => setCurrentPage(currentPage + 1)}
                disabled={currentPage === totalPages}
                className="pagination-btn"
              >
                Successiva ➡️
              </button>

              <button
                onClick={() => setCurrentPage(totalPages)}
                disabled={currentPage === totalPages}
                className="pagination-btn"
              >
                Ultima ⏭️
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default CollaboratorsTable;
