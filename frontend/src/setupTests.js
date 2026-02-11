// =================================================================
// FILE: setupTests.js
// =================================================================
// SCOPO: Configurazione globale per Jest e React Testing Library
//
// Questo file viene eseguito automaticamente PRIMA di tutti i test.
// Configura environment, mocks globali, e utilità condivise.
// =================================================================

// Import jest-dom per matchers custom (toBeInTheDocument, etc.)
import '@testing-library/jest-dom';

// =================================================================
// GLOBAL MOCKS
// =================================================================

// Mock window.matchMedia (usato da molti componenti responsive)
global.matchMedia = global.matchMedia || function (query) {
  return {
    matches: false,
    media: query,
    onchange: null,
    addListener: jest.fn(), // Deprecated
    removeListener: jest.fn(), // Deprecated
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
    dispatchEvent: jest.fn(),
  };
};

// Mock IntersectionObserver (usato per lazy loading)
global.IntersectionObserver = class IntersectionObserver {
  constructor() {}
  disconnect() {}
  observe() {}
  takeRecords() {
    return [];
  }
  unobserve() {}
};

// Mock console methods per test più puliti (opzionale)
// Decommentare se si vuole silenziare console durante test
/*
global.console = {
  ...console,
  error: jest.fn(),
  warn: jest.fn(),
  log: jest.fn(),
};
*/

// =================================================================
// ENVIRONMENT VARIABLES per TEST
// =================================================================

// Imposta variabili ambiente per test
process.env.REACT_APP_API_URL = 'http://localhost:8000';
process.env.NODE_ENV = 'test';

// =================================================================
// CUSTOM MATCHERS (opzionale)
// =================================================================

// Esempio: aggiungere matcher personalizzato
// expect.extend({
//   toBeValidEmail(received) {
//     const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
//     const pass = regex.test(received);
//     return {
//       pass,
//       message: () => `expected ${received} to be a valid email`
//     };
//   }
// });

// =================================================================
// GLOBAL TEST UTILITIES
// =================================================================

// Funzione helper per attendere tutte le promises pendenti
// Utile per test asincroni
export const flushPromises = () => new Promise(resolve => setImmediate(resolve));

// Helper per creare mock API responses
export const createMockResponse = (data, status = 200) => {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => data,
    text: async () => JSON.stringify(data)
  };
};

// =================================================================
// CLEANUP
// =================================================================

// Cleanup automatico dopo ogni test (React Testing Library lo fa già)
// Ma aggiungiamo cleanup custom se necessario
afterEach(() => {
  // Reset localStorage
  localStorage.clear();

  // Reset sessionStorage
  sessionStorage.clear();

  // Clear all timers
  jest.clearAllTimers();
});
