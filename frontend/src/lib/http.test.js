/**
 * Test F2-003: client HTTP unico.
 *
 * Il client deve:
 * - allegare il Bearer token a ogni richiesta
 * - su 401 senza refresh token: pulire i token e reindirizzare al login
 * - su 401 degli endpoint di auth (login/refresh): propagare l'errore senza redirect
 *
 * Nota: gira in ambiente node con shim di window/localStorage perche'
 * l'ambiente jsdom e' rotto da una dipendenza hoisted preesistente
 * (@tootallnate/once@3 ESM vs http-proxy-agent@4 che richiede v1).
 *
 * @jest-environment node
 */

const createLocalStorageMock = () => {
  let store = {};
  return {
    getItem: (key) => (key in store ? store[key] : null),
    setItem: (key, value) => { store[key] = String(value); },
    removeItem: (key) => { delete store[key]; },
    clear: () => { store = {}; },
  };
};

global.localStorage = createLocalStorageMock();
global.sessionStorage = createLocalStorageMock();
global.window = { location: { href: '/app', hostname: 'localhost', port: '3001' } };

const { http, clearStoredAuthTokens } = require('./http');

const requestInterceptor = http.interceptors.request.handlers[0];
const responseInterceptor = http.interceptors.response.handlers[0];

const make401Error = (url) => ({
  config: { url, headers: {} },
  response: { status: 401 },
});

describe('http client', () => {
  beforeEach(() => {
    localStorage.clear();
    window.location.href = '/app';
  });

  test('aggiunge il Bearer token alle richieste', () => {
    localStorage.setItem('access_token', 'token-di-test');
    const config = requestInterceptor.fulfilled({ headers: {} });
    expect(config.headers.Authorization).toBe('Bearer token-di-test');
  });

  test('senza token non aggiunge Authorization', () => {
    const config = requestInterceptor.fulfilled({ headers: {} });
    expect(config.headers.Authorization).toBeUndefined();
  });

  test('401 senza refresh token: pulisce i token e reindirizza al login', async () => {
    localStorage.setItem('access_token', 'scaduto');
    const error = make401Error('/cockpit/decisioni');

    await expect(responseInterceptor.rejected(error)).rejects.toBeDefined();

    expect(localStorage.getItem('access_token')).toBeNull();
    expect(localStorage.getItem('refresh_token')).toBeNull();
    expect(window.location.href).toBe('/');
  });

  test('401 su /auth/login: nessun redirect, errore propagato', async () => {
    const error = make401Error('/auth/login');

    await expect(responseInterceptor.rejected(error)).rejects.toBeDefined();

    expect(window.location.href).toBe('/app');
  });

  test('clearStoredAuthTokens rimuove access e refresh token', () => {
    localStorage.setItem('access_token', 'a');
    localStorage.setItem('refresh_token', 'r');
    clearStoredAuthTokens();
    expect(localStorage.getItem('access_token')).toBeNull();
    expect(localStorage.getItem('refresh_token')).toBeNull();
  });
});
