import {
  canAccessSection,
  canRequest,
  getAccessibleSectionIds,
  normalizeRole,
} from './permissions';

test.each([
  ['admin', 'admin'],
  ['operatore', 'operatore'],
  ['user', 'operatore'],
  ['manager', 'operatore'],
  ['consultazione', 'consultazione'],
  ['readonly', 'consultazione'],
  ['sconosciuto', 'consultazione'],
])('normalizza il ruolo %s come il backend', (input, expected) => {
  expect(normalizeRole(input)).toBe(expected);
});

test.each(['admin', 'operatore', 'consultazione'])(
  'snapshot delle route accessibili per %s',
  (role) => {
    expect(getAccessibleSectionIds(role)).toMatchSnapshot();
  },
);

test('la route guard usa la stessa matrice delle richieste backend', () => {
  expect(canAccessSection('consultazione', 'timesheet')).toBe(false);
  expect(canRequest('consultazione', 'GET', '/api/v1/reporting/timesheet')).toBe(false);
  expect(canAccessSection('consultazione', 'entities')).toBe(true);
  expect(canRequest('consultazione', 'GET', '/api/v1/entities')).toBe(true);
  expect(canAccessSection('operatore', 'templates')).toBe(false);
  expect(canRequest('operatore', 'GET', '/api/v1/contract-templates')).toBe(false);
});

