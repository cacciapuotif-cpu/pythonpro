export const MAX_RENDERABLE_EVENTS = 400;

export const DEFAULT_CALENDAR_FILTERS = {
  projectIds: [],
  collaboratorIds: [],
  includeClosedProjects: false,
  onlyMine: false,
  view: 'month',
  date: new Date().toISOString(),
};

const CSV_FIELDS = ['projectIds', 'collaboratorIds'];
const BOOL_FIELDS = ['includeClosedProjects', 'onlyMine'];
const FIELD_TO_PARAM = {
  projectIds: 'project_ids',
  collaboratorIds: 'collaborator_ids',
  includeClosedProjects: 'include_closed_projects',
  onlyMine: 'only_mine',
  view: 'view',
  date: 'date',
};

export const filtersToParams = (filters) => {
  const params = new URLSearchParams();
  Object.entries(FIELD_TO_PARAM).forEach(([field, param]) => {
    const value = filters[field];
    if (CSV_FIELDS.includes(field)) {
      if (value && value.length) params.set(param, value.join(','));
      return;
    }
    if (BOOL_FIELDS.includes(field)) {
      if (value) params.set(param, 'true');
      return;
    }
    if (value !== undefined && value !== null && value !== '') {
      params.set(param, String(value));
    }
  });
  return params;
};

export const filtersFromURL = () => {
  const params = new URLSearchParams(window.location.search);
  const filters = { ...DEFAULT_CALENDAR_FILTERS };
  if (params.has('project_ids')) {
    filters.projectIds = params.get('project_ids').split(',').filter(Boolean).map(Number);
  }
  if (params.has('collaborator_ids')) {
    filters.collaboratorIds = params.get('collaborator_ids').split(',').filter(Boolean).map(Number);
  }
  if (params.has('include_closed_projects')) {
    filters.includeClosedProjects = params.get('include_closed_projects') === 'true';
  }
  if (params.has('only_mine')) {
    filters.onlyMine = params.get('only_mine') === 'true';
  }
  if (params.has('view')) filters.view = params.get('view');
  if (params.has('date')) filters.date = params.get('date');
  return filters;
};

const storageKey = (username) => `pythonpro:calendarFilters:${username}`;

export const loadPersistedFilters = (username) => {
  if (!username) return null;
  try {
    const raw = localStorage.getItem(storageKey(username));
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
};

export const savePersistedFilters = (username, filters) => {
  if (!username) return;
  try {
    localStorage.setItem(storageKey(username), JSON.stringify(filters));
  } catch {
    // storage non disponibile (quota, modalità privata): non bloccare l'utente
  }
};
