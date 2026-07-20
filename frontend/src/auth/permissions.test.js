import {
  canAccessSection,
  canPerform,
  canRequest,
  getAccessibleSectionIds,
  normalizeRole,
  UI_ACTIONS,
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

test.each([
  ['admin', true, true, true],
  ['operatore', false, false, true],
  ['consultazione', false, false, false],
])(
  'azioni sensibili per %s: export=%s documenti=%s collegamenti=%s',
  (role, exportAllowed, documentAllowed, linksAllowed) => {
    expect(canPerform(role, 'EXPORT_TIMESHEET')).toBe(exportAllowed);
    expect(canPerform(role, 'DOWNLOAD_COLLABORATOR_SENSITIVE')).toBe(documentAllowed);
    expect(canPerform(role, 'MANAGE_PROJECT_LINKS')).toBe(linksAllowed);
  },
);

test('matrice completa delle azioni nominate per i tre ruoli', () => {
  const actions = Object.keys(UI_ACTIONS);
  const operatorDenied = new Set([
    'DOWNLOAD_COLLABORATOR_SENSITIVE',
    'EXPORT_TIMESHEET',
    'RUN_AGENTS',
    'PERMANENT_DELETE_AVVISO',
  ]);

  actions.forEach((action) => {
    expect(canPerform('admin', action)).toBe(true);
    expect(canPerform('operatore', action)).toBe(!operatorDenied.has(action));
    expect(canPerform('consultazione', action)).toBe(false);
  });
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

test('il download del contratto (NEW-022) segue la matrice backend', () => {
  expect(canRequest('consultazione', 'GET', '/api/v1/assignments/1/contract')).toBe(false);
  expect(canRequest('operatore', 'GET', '/api/v1/assignments/1/contract')).toBe(true);
  expect(canRequest('admin', 'GET', '/api/v1/assignments/1/contract')).toBe(true);
});
