import React, { useMemo, useState } from 'react';
import './CalendarFilterBar.css';

const CalendarFilterBar = ({ filters, projects, collaborators, eventCount, onChange, onReset }) => {
  const [collaboratorSearch, setCollaboratorSearch] = useState('');

  const visibleProjects = useMemo(
    () => projects.filter((p) => filters.includeClosedProjects || p.is_active),
    [projects, filters.includeClosedProjects],
  );

  const visibleCollaborators = useMemo(() => {
    const term = collaboratorSearch.trim().toLowerCase();
    if (!term) return collaborators;
    return collaborators.filter((c) => (
      `${c.first_name} ${c.last_name}`.toLowerCase().includes(term)
    ));
  }, [collaborators, collaboratorSearch]);

  const toggleCollaborator = (id) => {
    const current = filters.collaboratorIds;
    const next = current.includes(id)
      ? current.filter((existing) => existing !== id)
      : [...current, id];
    onChange({ collaboratorIds: next });
  };

  const toggleProject = (id) => {
    const current = filters.projectIds;
    const next = current.includes(id)
      ? current.filter((existing) => existing !== id)
      : [...current, id];
    onChange({ projectIds: next });
  };

  return (
    <div className="calendar-filter-bar">
      <div className="calendar-filter-group">
        <span className="calendar-filter-label">Progetto</span>
        <div className="calendar-filter-checklist">
          {visibleProjects.map((project) => (
            <label key={project.id}>
              <input
                type="checkbox"
                checked={filters.projectIds.includes(project.id)}
                onChange={() => toggleProject(project.id)}
              />
              {project.name}
            </label>
          ))}
        </div>
        <label className="calendar-filter-inline-toggle">
          <input
            type="checkbox"
            checked={filters.includeClosedProjects}
            onChange={(event) => onChange({ includeClosedProjects: event.target.checked })}
          />
          Includi progetti chiusi
        </label>
      </div>

      <div className="calendar-filter-group">
        <span className="calendar-filter-label">Collaboratore</span>
        <input
          type="search"
          placeholder="Cerca collaboratore..."
          value={collaboratorSearch}
          onChange={(event) => setCollaboratorSearch(event.target.value)}
        />
        <div className="calendar-filter-checklist">
          {visibleCollaborators.map((collaborator) => (
            <label key={collaborator.id}>
              <input
                type="checkbox"
                checked={filters.collaboratorIds.includes(collaborator.id)}
                onChange={() => toggleCollaborator(collaborator.id)}
              />
              {collaborator.first_name} {collaborator.last_name}
            </label>
          ))}
        </div>
      </div>

      <div className="calendar-filter-group">
        <label>
          <input
            type="checkbox"
            checked={filters.onlyMine}
            onChange={(event) => onChange({ onlyMine: event.target.checked })}
          />
          Solo i miei impegni
        </label>
      </div>

      <div className="calendar-filter-actions">
        <button type="button" className="cancel-button" onClick={onReset}>
          Azzera filtri
        </button>
        <span className="calendar-filter-count">{eventCount} eventi mostrati</span>
      </div>
    </div>
  );
};

export default CalendarFilterBar;
