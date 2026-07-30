import SECTION_CONFIG from './sections.json';
import {
  getPathForSection,
  getPathWithFilters,
  resolveAppLocation,
} from './routes';

test.each(SECTION_CONFIG.map((section) => [section.id, section.path]))(
  'round-trip canonico %s ↔ %s',
  (sectionId, path) => {
    expect(getPathForSection(sectionId)).toBe(path);
    expect(resolveAppLocation({ pathname: path, search: '' })).toMatchObject({
      section: sectionId,
      canonicalPath: path,
    });
  },
);

test('Presenze riusa Calendario in modalità operativa con URL distinto', () => {
  expect(getPathWithFilters('calendar', {}, { mode: 'attendance' })).toBe('/presenze');
  expect(resolveAppLocation({ pathname: '/presenze', search: '' })).toMatchObject({
    section: 'calendar',
    mode: 'attendance',
    filters: { focus: 'attendance' },
  });
});

test.each([
  ['/collaborators/42/documents', '42'],
  ['/collaboratori/42/documenti', '42'],
])('risolve il deep-link documenti collaboratore %s', (pathname, collaboratorId) => {
  expect(resolveAppLocation({ pathname, search: '' })).toMatchObject({
    section: 'collaborators',
    filters: { collaboratorId, focus: 'documents' },
  });
});

test('serializza i filtri senza perdere il path canonico', () => {
  expect(getPathWithFilters('projects', { status: 'active', projectId: 7 }))
    .toBe('/projects?status=active&project_id=7');
});
