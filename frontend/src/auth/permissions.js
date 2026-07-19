/**
 * Fonte unica frontend per ruoli e autorizzazioni.
 *
 * La normalizzazione e la matrice HTTP rispecchiano backend/auth.py. I componenti
 * non devono confrontare direttamente stringhe di ruolo: menu, route e azioni
 * passano da questo modulo.
 */

export const ROLES = Object.freeze({
  ADMIN: 'admin',
  OPERATOR: 'operatore',
  CONSULTATION: 'consultazione',
});

const LEGACY_ROLE_MAP = Object.freeze({
  manager: ROLES.OPERATOR,
  user: ROLES.OPERATOR,
  readonly: ROLES.CONSULTATION,
  dpo: ROLES.ADMIN,
});

export const normalizeRole = (role) => {
  const value = typeof role === 'object' ? role?.role : role;
  if (!value) return ROLES.CONSULTATION;
  const normalized = LEGACY_ROLE_MAP[value] || value;
  return Object.values(ROLES).includes(normalized) ? normalized : ROLES.CONSULTATION;
};

export const isAdminRole = (role) => normalizeRole(role) === ROLES.ADMIN;
export const isOperatorRole = (role) => normalizeRole(role) === ROLES.OPERATOR;
export const isConsultationRole = (role) => normalizeRole(role) === ROLES.CONSULTATION;

export const ROLE_EXPERIENCE = Object.freeze({
  [ROLES.ADMIN]: { label: 'Amministratore', homeSection: 'dashboard' },
  [ROLES.OPERATOR]: { label: 'Operatore', homeSection: 'collaborators' },
  [ROLES.CONSULTATION]: { label: 'Consultazione', homeSection: 'home' },
});

export const getRoleExperience = (role) => ROLE_EXPERIENCE[normalizeRole(role)];
export const getRoleLabel = (role) => getRoleExperience(role).label;

export const ACCESS_PROFILES = Object.freeze({
  admin: {
    id: 'admin',
    label: 'Amministratore',
    description: 'Gestione completa del gestionale, configurazioni e controllo operativo.',
    role: ROLES.ADMIN,
  },
  operator: {
    id: 'operator',
    label: 'Operatore',
    description: 'Accesso operativo alle funzioni quotidiane del gestionale.',
    role: ROLES.OPERATOR,
  },
  consultation: {
    id: 'consultation',
    label: 'Consultazione',
    description: 'Lettura dei dati senza possibilità di modificarli.',
    role: ROLES.CONSULTATION,
  },
});

export const profileAcceptsRole = (profile, role) => (
  Boolean(profile) && profile.role === normalizeRole(role)
);

const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS']);
const ADMIN_ONLY_PREFIXES = ['/api/v1/admin', '/api/v1/gdpr'];
const AGENT_PLATFORM_PREFIXES = ['/api/v1/agents', '/api/v1/agent-suggestions', '/api/v1/email-inbox'];
const AGENT_ADMIN_ONLY_PATHS = ['/api/v1/email-inbox/trigger-poll', '/api/v1/email-inbox/imap/test'];
const OPERATIONAL_PREFIXES = [
  '/api/v1/collaborators', '/api/v1/projects', '/api/v1/attendances',
  '/api/v1/assignments', '/api/v1/entities', '/api/v1/project-assignments',
  '/api/v1/contracts', '/api/v1/reporting', '/api/v1/agenzie',
  '/api/v1/consulenti', '/api/v1/aziende-clienti', '/api/v1/allievi',
  '/api/v1/catalogo', '/api/v1/listini', '/api/v1/preventivi',
  '/api/v1/ordini', '/api/v1/piani-finanziari', '/api/v1/documenti-richiesti',
  '/api/v1/avvisi', '/api/v1/attivita', '/api/v1/cockpit',
];
const OPERATIONAL_EXACT_PREFIXES = ['/collaborators-with-projects', '/collaborators/'];
const ADMIN_ONLY_PATTERNS = ['/download-documento', '/download-curriculum', '/api/v1/reporting/timesheet/export'];
const OPERATOR_SENSITIVE_GET_PATHS = ['/api/v1/reporting/timesheet'];
const OPERATOR_SENSITIVE_GET_SUFFIXES = ['/export-excel'];

const pathMatches = (path, prefixes) => prefixes.some(
  (prefix) => path === prefix || path.startsWith(`${prefix}/`),
);
const pathStartsWith = (path, prefixes) => prefixes.some((prefix) => path.startsWith(prefix));

export const allowedRolesForRequest = (method, path) => {
  const normalizedMethod = method.toUpperCase();
  if (pathMatches(path, ADMIN_ONLY_PREFIXES)) return [ROLES.ADMIN];
  if (pathMatches(path, AGENT_PLATFORM_PREFIXES)) {
    if (SAFE_METHODS.has(normalizedMethod)) return Object.values(ROLES);
    const isAgentRun = path === '/api/v1/agents/run'
      || (path.startsWith('/api/v1/agents/') && path.endsWith('/run'));
    if (isAgentRun || AGENT_ADMIN_ONLY_PATHS.includes(path)) return [ROLES.ADMIN];
    return [ROLES.ADMIN, ROLES.OPERATOR];
  }
  if (SAFE_METHODS.has(normalizedMethod) && (
    OPERATOR_SENSITIVE_GET_PATHS.includes(path)
    || OPERATOR_SENSITIVE_GET_SUFFIXES.some((suffix) => path.endsWith(suffix))
  )) return [ROLES.ADMIN, ROLES.OPERATOR];
  if (ADMIN_ONLY_PATTERNS.some((pattern) => path.includes(pattern))) return [ROLES.ADMIN];
  if (pathMatches(path, OPERATIONAL_PREFIXES) || pathStartsWith(path, OPERATIONAL_EXACT_PREFIXES)) {
    return SAFE_METHODS.has(normalizedMethod)
      ? Object.values(ROLES)
      : [ROLES.ADMIN, ROLES.OPERATOR];
  }
  return [ROLES.ADMIN];
};

export const canRequest = (role, method, path) => (
  allowedRolesForRequest(method, path).includes(normalizeRole(role))
);

export const SECTION_ACCESS = Object.freeze({
  home: ['GET', '/api/v1/cockpit'],
  dashboard: ['GET', '/api/v1/cockpit'],
  calendar: ['GET', '/api/v1/attendances'],
  timesheet: ['GET', '/api/v1/reporting/timesheet'],
  'documenti-mancanti': ['GET', '/api/v1/documenti-richiesti'],
  collaborators: ['GET', '/api/v1/collaborators'],
  allievi: ['GET', '/api/v1/allievi'],
  projects: ['GET', '/api/v1/projects'],
  'aziende-clienti': ['GET', '/api/v1/aziende-clienti'],
  catalogo: ['GET', '/api/v1/catalogo'],
  listini: ['GET', '/api/v1/listini'],
  preventivi: ['GET', '/api/v1/preventivi'],
  ordini: ['GET', '/api/v1/ordini'],
  resources: ['GET', '/api/v1/avvisi'],
  entities: ['GET', '/api/v1/entities'],
  'agents-dashboard': ['GET', '/api/v1/agents'],
  agents: ['GET', '/api/v1/agents'],
  'agents-review': ['GET', '/api/v1/agent-suggestions'],
  templates: ['GET', '/api/v1/contract-templates'],
});

export const canAccessSection = (role, sectionId) => {
  const request = SECTION_ACCESS[sectionId];
  return Boolean(request) && canRequest(role, request[0], request[1]);
};

export const getAccessibleSectionIds = (role) => Object.keys(SECTION_ACCESS)
  .filter((sectionId) => canAccessSection(role, sectionId));
