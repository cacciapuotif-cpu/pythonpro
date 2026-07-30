import SECTION_CONFIG from './sections.json';

const SECTION_BY_ID = new Map(SECTION_CONFIG.map((section) => [section.id, section]));
const SECTION_BY_PATH = [...SECTION_CONFIG]
  .sort((left, right) => right.path.length - left.path.length);

export const FILTER_QUERY_KEYS = Object.freeze({
  status: 'status',
  runStatus: 'run_status',
  suggestionId: 'suggestion_id',
  documentId: 'document_id',
  collaboratorId: 'collaborator_id',
  projectId: 'project_id',
  focus: 'focus',
  avvisoId: 'avviso_id',
});

export const getPathForSection = (sectionId) => SECTION_BY_ID.get(sectionId)?.path || '/home';

const queryFilters = (search = '') => {
  const params = new URLSearchParams(search);
  return Object.entries(FILTER_QUERY_KEYS).reduce((filters, [filterKey, queryKey]) => {
    const value = params.get(queryKey);
    if (value) filters[filterKey] = value;
    return filters;
  }, {});
};

export const resolveAppLocation = ({ pathname = '/', search = '' } = {}) => {
  const filters = queryFilters(search);

  if (pathname === '/presenze' || pathname.startsWith('/presenze/')) {
    return {
      section: 'calendar',
      filters: { ...filters, focus: filters.focus || 'attendance' },
      canonicalPath: '/presenze',
      mode: 'attendance',
    };
  }

  const collaboratorDocuments = pathname.match(
    /^\/(?:collaborators\/(\d+)\/documents|collaboratori\/(\d+)\/documenti)\/?$/,
  );
  if (collaboratorDocuments) {
    return {
      section: 'collaborators',
      filters: {
        ...filters,
        collaboratorId: collaboratorDocuments[1] || collaboratorDocuments[2],
        focus: 'documents',
      },
      canonicalPath: `/collaborators/${collaboratorDocuments[1] || collaboratorDocuments[2]}/documents`,
    };
  }

  const collaboratorDetail = pathname.match(/^\/collaborators\/(\d+)\/?$/);
  if (collaboratorDetail) {
    return {
      section: 'collaborators',
      filters: { ...filters, collaboratorId: collaboratorDetail[1], focus: filters.focus || 'detail' },
      canonicalPath: `/collaborators/${collaboratorDetail[1]}`,
    };
  }

  const matched = SECTION_BY_PATH.find(
    (section) => pathname === section.path || pathname.startsWith(`${section.path}/`),
  );
  return matched
    ? { section: matched.id, filters, canonicalPath: matched.path }
    : { section: null, filters, canonicalPath: null };
};

export const getPathWithFilters = (sectionId, filters = {}, options = {}) => {
  let path = options.mode === 'attendance' ? '/presenze' : getPathForSection(sectionId);
  if (sectionId === 'collaborators' && filters.collaboratorId) {
    path = filters.focus === 'documents'
      ? `/collaborators/${filters.collaboratorId}/documents`
      : `/collaborators/${filters.collaboratorId}`;
  }

  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (
      value !== undefined
      && value !== null
      && value !== ''
      && !(sectionId === 'collaborators' && ['collaboratorId', 'focus'].includes(key))
      && !(options.mode === 'attendance' && key === 'focus')
    ) {
      params.set(FILTER_QUERY_KEYS[key] || key, String(value));
    }
  });
  const query = params.toString();
  return `${path}${query ? `?${query}` : ''}`;
};
