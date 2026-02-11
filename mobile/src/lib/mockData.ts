/**
 * Mock Data for Offline Development/Demo
 */

import type { Item, User, TokenResponse } from '../types/api';

export const MOCK_USER: User = {
  id: 1,
  email: 'demo@pythonpro.com',
  nome: 'Demo',
  cognome: 'User',
  ruolo: 'admin',
};

export const MOCK_TOKEN: TokenResponse = {
  access_token: 'mock_access_token_' + Date.now(),
  refresh_token: 'mock_refresh_token_' + Date.now(),
  token_type: 'bearer',
  expires_in: 3600,
};

export const MOCK_ITEMS: Item[] = [
  {
    id: 1,
    nome: 'Progetto Alpha',
    descrizione: 'Sistema di gestione clienti enterprise',
    stato: 'attivo',
    data_creazione: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
    data_modifica: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(),
  },
  {
    id: 2,
    nome: 'Collaboratore Beta',
    descrizione: 'Sviluppatore Full-Stack con 5 anni di esperienza',
    stato: 'disponibile',
    data_creazione: new Date(Date.now() - 14 * 24 * 60 * 60 * 1000).toISOString(),
    data_modifica: new Date(Date.now() - 5 * 24 * 60 * 60 * 1000).toISOString(),
  },
  {
    id: 3,
    nome: 'Task Gamma',
    descrizione: 'Implementazione API REST per modulo fatturazione',
    stato: 'in_corso',
    data_creazione: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString(),
    data_modifica: new Date(Date.now() - 1 * 24 * 60 * 60 * 1000).toISOString(),
  },
  {
    id: 4,
    nome: 'Cliente Delta',
    descrizione: null,
    stato: 'attivo',
    data_creazione: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString(),
    data_modifica: new Date(Date.now() - 10 * 24 * 60 * 60 * 1000).toISOString(),
  },
  {
    id: 5,
    nome: 'Report Epsilon',
    descrizione: 'Report mensile performance Q1 2024',
    stato: 'completato',
    data_creazione: new Date(Date.now() - 60 * 24 * 60 * 60 * 1000).toISOString(),
    data_modifica: new Date(Date.now() - 45 * 24 * 60 * 60 * 1000).toISOString(),
  },
];

/**
 * Simulate network delay
 */
export const delay = (ms: number = 500) =>
  new Promise((resolve) => setTimeout(resolve, ms));
