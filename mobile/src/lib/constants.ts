/**
 * App Constants
 */

// Environment
export const API_BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL || 'http://192.168.1.40:8001';
export const USE_MOCK = process.env.EXPO_PUBLIC_USE_MOCK === 'true';
export const IS_DEV = process.env.EXPO_PUBLIC_ENABLE_DEBUG === 'true';

// Storage keys
export const STORAGE_KEYS = {
  ACCESS_TOKEN: '@pythonpro/access_token',
  REFRESH_TOKEN: '@pythonpro/refresh_token',
  USER: '@pythonpro/user',
} as const;

// API endpoints
export const API_ENDPOINTS = {
  LOGIN: '/api/v1/auth/login',
  REFRESH: '/api/v1/auth/refresh',
  ME: '/api/v1/auth/me',
  ITEMS: '/api/v1/items',
  ITEM_DETAIL: (id: number) => `/api/v1/items/${id}`,
  // Gestionale endpoints
  COLLABORATORI: '/api/v1/collaborators/',
  COLLABORATORE_DETAIL: (id: number) => `/api/v1/collaborators/${id}`,
  ENTI: '/api/v1/entities/',
  ENTE_DETAIL: (id: number) => `/api/v1/entities/${id}`,
  PROGETTI: '/api/v1/projects/',
  PROGETTO_DETAIL: (id: number) => `/api/v1/projects/${id}`,
  CALENDARIO: '/api/v1/attendances/',
  EVENTO_DETAIL: (id: number) => `/api/v1/attendances/${id}`,
} as const;

// Query keys for react-query
export const QUERY_KEYS = {
  USER: ['user'],
  ITEMS: ['items'],
  ITEM: (id: number) => ['item', id],
  // Gestionale query keys
  COLLABORATORI: ['collaboratori'],
  COLLABORATORE: (id: number) => ['collaboratore', id],
  ENTI: ['enti'],
  ENTE: (id: number) => ['ente', id],
  PROGETTI: ['progetti'],
  PROGETTO: (id: number) => ['progetto', id],
  CALENDARIO: ['calendario'],
  EVENTO: (id: number) => ['evento', id],
} as const;

// UI Constants
export const UI = {
  DEBOUNCE_MS: 300,
  STALE_TIME: 5 * 60 * 1000, // 5 minutes
  CACHE_TIME: 10 * 60 * 1000, // 10 minutes
} as const;

// Error messages
export const ERROR_MESSAGES = {
  NETWORK: 'Errore di connessione. Verifica la tua connessione internet.',
  UNAUTHORIZED: 'Sessione scaduta. Effettua nuovamente il login.',
  FORBIDDEN: 'Non hai i permessi per questa operazione.',
  NOT_FOUND: 'Risorsa non trovata.',
  SERVER_ERROR: 'Errore del server. Riprova più tardi.',
  VALIDATION: 'Dati non validi. Controlla i campi e riprova.',
  UNKNOWN: 'Si è verificato un errore imprevisto.',
} as const;
