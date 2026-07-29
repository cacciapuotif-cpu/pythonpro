import {
  DEFAULT_CALENDAR_FILTERS,
  filtersToParams,
  filtersFromURL,
  loadPersistedFilters,
  savePersistedFilters,
  MAX_RENDERABLE_EVENTS,
} from './calendarFilters';

beforeEach(() => {
  window.history.replaceState({}, '', '/');
  localStorage.clear();
});

test('filtersToParams serializza multi-selezione come CSV', () => {
  const params = filtersToParams({
    ...DEFAULT_CALENDAR_FILTERS,
    projectIds: [3, 7],
    collaboratorIds: [1],
    includeClosedProjects: true,
  });
  expect(params.get('project_ids')).toBe('3,7');
  expect(params.get('collaborator_ids')).toBe('1');
  expect(params.get('include_closed_projects')).toBe('true');
});

test('filtersFromURL ricostruisce array numerici dalla query string', () => {
  window.history.replaceState({}, '', '/?project_ids=3,7&collaborator_ids=1,2&only_mine=true');
  const filters = filtersFromURL();
  expect(filters.projectIds).toEqual([3, 7]);
  expect(filters.collaboratorIds).toEqual([1, 2]);
  expect(filters.onlyMine).toBe(true);
});

test('savePersistedFilters e loadPersistedFilters sono simmetrici per utente', () => {
  const filters = { ...DEFAULT_CALENDAR_FILTERS, projectIds: [5] };
  savePersistedFilters('mario.rossi', filters);
  expect(loadPersistedFilters('mario.rossi')).toEqual(filters);
  expect(loadPersistedFilters('altro.utente')).toBeNull();
});

test('MAX_RENDERABLE_EVENTS è una soglia numerica positiva', () => {
  expect(MAX_RENDERABLE_EVENTS).toBeGreaterThan(0);
});
