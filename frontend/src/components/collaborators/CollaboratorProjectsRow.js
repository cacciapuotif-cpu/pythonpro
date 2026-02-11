import React from 'react';

/**
 * Riga espansa che mostra i progetti e le assegnazioni di un collaboratore
 * Gestisce visualizzazione dettagli, modifica e rimozione
 */
const CollaboratorProjectsRow = ({
  collaborator,
  projects,
  assignments,
  availableProjects,
  onAssignProject,
  onRemoveProject,
  onOpenAssignmentModal,
  onEditAssignment,
  onDownloadContract
}) => {
  // Ottieni assegnazioni per un collaboratore e progetto specifici
  const getAssignmentsForCollaboratorProject = (collaboratorId, projectId) => {
    return assignments.filter(
      assignment =>
        assignment.collaborator_id === collaboratorId &&
        assignment.project_id === projectId
    );
  };

  const hasProjects = collaborator.projects && collaborator.projects.length > 0;

  if (!hasProjects) {
    return null;
  }

  // Calcola progetti disponibili da assegnare
  const assignedProjectIds = collaborator.projects.map(p => p.id);
  const unassignedProjects = availableProjects.filter(
    project => !assignedProjectIds.includes(project.id)
  );

  return (
    <tr className="expanded-row">
      <td colSpan="4">
        <div className="projects-details-panel">
          <h4>📁 Progetti Assegnati</h4>
          <div className="projects-grid-expanded">
            {collaborator.projects.map(project => {
              const projectAssignments = getAssignmentsForCollaboratorProject(
                collaborator.id,
                project.id
              );

              return (
                <div key={project.id} className="project-detail-card">
                  <div className="project-detail-header">
                    <div>
                      <strong className="project-name-detail">
                        🎯 {project.name}
                      </strong>
                      <span className={`status-badge status-${project.status}`}>
                        {project.status === 'active' ? '🟢 Attivo' :
                         project.status === 'completed' ? '✅ Completato' :
                         project.status === 'paused' ? '⏸️ In Pausa' :
                         '❌ Annullato'}
                      </span>
                    </div>
                    <div className="project-detail-actions">
                      <button
                        className="small-action-btn"
                        onClick={() => onOpenAssignmentModal(collaborator, project)}
                        title="Aggiungi nuova mansione"
                      >
                        ➕ Aggiungi Mansione
                      </button>
                      <button
                        className="small-action-btn remove-btn"
                        onClick={() => onRemoveProject(collaborator.id, project.id)}
                        title="Rimuovi progetto"
                      >
                        ❌ Rimuovi
                      </button>
                    </div>
                  </div>

                  {/* Elenco Mansioni/Assegnazioni */}
                  {projectAssignments.length > 0 ? (
                    <div className="assignments-list">
                      <h5>📋 Mansioni assegnate ({projectAssignments.length}):</h5>
                      {projectAssignments.map((assignment, index) => (
                        <div key={assignment.id} className="assignment-details-expanded">
                          <div className="assignment-header">
                            <strong>Mansione {index + 1}</strong>
                            <div className="assignment-actions">
                              <button
                                className="small-action-btn edit-assignment-btn"
                                onClick={() => onEditAssignment(assignment)}
                                title="Modifica questa mansione"
                              >
                                ✏️ Modifica
                              </button>
                              <button
                                className="small-action-btn download-contract-btn"
                                onClick={() => onDownloadContract(assignment)}
                                title="Scarica contratto PDF"
                              >
                                📄 Contratto
                              </button>
                            </div>
                          </div>

                          <div className="detail-item">
                            <span className="detail-label">👔 Mansione:</span>
                            <span>{assignment.role}</span>
                          </div>

                          {assignment.contract_type && (
                            <div className="detail-item">
                              <span className="detail-label">📝 Tipo Contratto:</span>
                              <span>
                                {assignment.contract_type === 'professionale' && '💼 Professionale'}
                                {assignment.contract_type === 'occasionale' && '📝 Occasionale'}
                                {assignment.contract_type === 'ordine_servizio' && '📋 Ordine di servizio'}
                                {assignment.contract_type === 'contratto_progetto' && '📄 Contratto a progetto'}
                              </span>
                            </div>
                          )}

                          <div className="detail-item">
                            <span className="detail-label">⏰ Ore Assegnate:</span>
                            <span>{assignment.assigned_hours}h</span>
                          </div>

                          <div className="detail-item">
                            <span className="detail-label">💰 Tariffa Oraria:</span>
                            <span>€{assignment.hourly_rate}/h</span>
                          </div>

                          <div className="detail-item">
                            <span className="detail-label">💶 Totale:</span>
                            <span>
                              <strong>
                                €{(assignment.assigned_hours * assignment.hourly_rate).toFixed(2)}
                              </strong>
                            </span>
                          </div>

                          <div className="detail-item full-width">
                            <span className="detail-label">📅 Periodo:</span>
                            <span>
                              {new Date(assignment.start_date).toLocaleDateString('it-IT')} → {new Date(assignment.end_date).toLocaleDateString('it-IT')}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="no-assignments-message">
                      <p>📝 Nessuna mansione specificata per questo progetto</p>
                      <button
                        className="small-action-btn"
                        onClick={() => onOpenAssignmentModal(collaborator, project)}
                      >
                        ➕ Aggiungi Dettagli Mansione
                      </button>
                    </div>
                  )}

                  {/* Dettagli Progetto */}
                  {(project.cup || project.ente_erogatore || project.description) && (
                    <div className="project-extra-info">
                      {project.cup && (
                        <div><small>🏷️ CUP: {project.cup}</small></div>
                      )}
                      {project.ente_erogatore && (
                        <div><small>🏛️ Ente: {project.ente_erogatore}</small></div>
                      )}
                      {project.description && (
                        <div><small>📝 {project.description}</small></div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Dropdown per assegnare nuovi progetti */}
          <div className="assign-new-project-section">
            {unassignedProjects.length > 0 ? (
              <select
                onChange={(e) => {
                  if (e.target.value) {
                    onAssignProject(collaborator.id, parseInt(e.target.value));
                    e.target.value = '';
                  }
                }}
                className="assign-project-select"
              >
                <option value="">➕ Assegna nuovo progetto...</option>
                {unassignedProjects.map(project => (
                  <option key={project.id} value={project.id}>
                    {project.name}
                  </option>
                ))}
              </select>
            ) : (
              <p className="all-assigned-message">
                ✅ Tutti i progetti disponibili sono già assegnati
              </p>
            )}
          </div>
        </div>
      </td>
    </tr>
  );
};

export default CollaboratorProjectsRow;
