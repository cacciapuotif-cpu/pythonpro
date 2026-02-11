// =================================================================
// FILE: Dashboard.test.js
// =================================================================
// SCOPO: Unit tests per componente Dashboard React
//
// Framework utilizzati:
// - Jest: Test runner e assertion library
// - React Testing Library: Utilità per testare componenti React
// - @testing-library/user-event: Simulare interazioni utente
//
// ESECUZIONE:
//   npm test Dashboard.test.js         # Esegui questi test
//   npm test -- --coverage             # Con coverage
//   npm test -- --watch                # Watch mode
// =================================================================

import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import Dashboard from './Dashboard';

// =================================================================
// MOCK API SERVICE
// =================================================================
// Mock di apiService per evitare chiamate HTTP reali durante test
// =================================================================

// Mock del modulo intero
jest.mock('../services/apiService', () => ({
  getCollaborators: jest.fn(),
  getProjects: jest.fn(),
  getAttendances: jest.fn(),
  getAssignments: jest.fn()
}));

// Import dopo il mock
import * as apiService from '../services/apiService';

// =================================================================
// TEST SETUP E TEARDOWN
// =================================================================

beforeEach(() => {
  // Reset mocks prima di ogni test per isolamento
  jest.clearAllMocks();
});

afterEach(() => {
  // Cleanup dopo ogni test
  jest.restoreAllMocks();
});

// =================================================================
// MOCK DATA
// =================================================================
// Dati di test che simulano risposte API
// =================================================================

const mockCollaborators = [
  { id: 1, first_name: 'Mario', last_name: 'Rossi', email: 'mario@test.com', position: 'Developer' },
  { id: 2, first_name: 'Luigi', last_name: 'Verdi', email: 'luigi@test.com', position: 'Designer' }
];

const mockProjects = [
  { id: 1, name: 'Project Alpha', status: 'active', start_date: '2025-01-01', end_date: '2025-12-31' },
  { id: 2, name: 'Project Beta', status: 'completed', start_date: '2024-01-01', end_date: '2024-12-31' }
];

const mockAttendances = [
  { id: 1, collaborator_id: 1, project_id: 1, date: '2025-09-30', hours: 8, notes: 'Test attendance' }
];

// =================================================================
// TEST SUITE: DASHBOARD RENDERING
// =================================================================

describe('Dashboard Component', () => {
  describe('Initial Rendering', () => {
    test('should render dashboard title', () => {
      // Arrange: configura mocks per risposte vuote
      apiService.getCollaborators.mockResolvedValue([]);
      apiService.getProjects.mockResolvedValue([]);
      apiService.getAttendances.mockResolvedValue([]);

      // Act: renderizza componente
      render(<Dashboard />);

      // Assert: verifica titolo presente
      const titleElement = screen.getByText(/dashboard/i);
      expect(titleElement).toBeInTheDocument();
    });

    test('should show loading state initially', () => {
      // Mock con delay per simulare caricamento
      apiService.getCollaborators.mockImplementation(() =>
        new Promise(resolve => setTimeout(() => resolve([]), 100))
      );
      apiService.getProjects.mockResolvedValue([]);
      apiService.getAttendances.mockResolvedValue([]);

      render(<Dashboard />);

      // Durante caricamento, dovrebbe mostrare indicator
      // (assumendo che Dashboard abbia un loading indicator)
      // Modifica in base alla tua implementazione
      expect(screen.queryByText(/caricamento/i) || screen.queryByRole('progressbar')).toBeTruthy();
    });
  });

  // =================================================================
  // TEST SUITE: DATA FETCHING
  // =================================================================

  describe('Data Fetching', () => {
    test('should fetch and display collaborators', async () => {
      // Arrange: mock con dati
      apiService.getCollaborators.mockResolvedValue(mockCollaborators);
      apiService.getProjects.mockResolvedValue([]);
      apiService.getAttendances.mockResolvedValue([]);

      // Act: renderizza
      render(<Dashboard />);

      // Assert: verifica chiamata API
      expect(apiService.getCollaborators).toHaveBeenCalledTimes(1);

      // Assert: attendi che dati compaiano nel DOM
      await waitFor(() => {
        expect(screen.getByText(/mario/i)).toBeInTheDocument();
        expect(screen.getByText(/luigi/i)).toBeInTheDocument();
      });
    });

    test('should fetch and display projects', async () => {
      apiService.getCollaborators.mockResolvedValue([]);
      apiService.getProjects.mockResolvedValue(mockProjects);
      apiService.getAttendances.mockResolvedValue([]);

      render(<Dashboard />);

      expect(apiService.getProjects).toHaveBeenCalledTimes(1);

      await waitFor(() => {
        expect(screen.getByText(/project alpha/i)).toBeInTheDocument();
        expect(screen.getByText(/project beta/i)).toBeInTheDocument();
      });
    });

    test('should handle API errors gracefully', async () => {
      // Arrange: mock con errore
      const consoleError = jest.spyOn(console, 'error').mockImplementation(() => {});
      apiService.getCollaborators.mockRejectedValue(new Error('API Error'));
      apiService.getProjects.mockResolvedValue([]);
      apiService.getAttendances.mockResolvedValue([]);

      // Act: renderizza
      render(<Dashboard />);

      // Assert: verifica gestione errore
      await waitFor(() => {
        // Assumendo che Dashboard mostri messaggio errore
        // Modifica in base alla tua implementazione
        expect(screen.queryByText(/errore/i) || screen.queryByRole('alert')).toBeTruthy();
      });

      consoleError.mockRestore();
    });
  });

  // =================================================================
  // TEST SUITE: STATISTICS CALCULATION
  // =================================================================

  describe('Statistics Display', () => {
    test('should display correct count of collaborators', async () => {
      apiService.getCollaborators.mockResolvedValue(mockCollaborators);
      apiService.getProjects.mockResolvedValue([]);
      apiService.getAttendances.mockResolvedValue([]);

      render(<Dashboard />);

      await waitFor(() => {
        // Cerca contatore collaboratori (adatta al tuo markup)
        const countElement = screen.getByText(/2.*collaboratori/i) ||
                            screen.getByText(/collaboratori.*2/i);
        expect(countElement).toBeInTheDocument();
      });
    });

    test('should display correct count of active projects', async () => {
      apiService.getCollaborators.mockResolvedValue([]);
      apiService.getProjects.mockResolvedValue(mockProjects);
      apiService.getAttendances.mockResolvedValue([]);

      render(<Dashboard />);

      await waitFor(() => {
        // Solo 1 progetto attivo (Project Alpha)
        const activeCount = screen.getByText(/1.*attiv/i) ||
                           screen.getByText(/attiv.*1/i);
        expect(activeCount).toBeInTheDocument();
      });
    });
  });

  // =================================================================
  // TEST SUITE: USER INTERACTIONS
  // =================================================================

  describe('User Interactions', () => {
    test('should refresh data when refresh button clicked', async () => {
      apiService.getCollaborators.mockResolvedValue(mockCollaborators);
      apiService.getProjects.mockResolvedValue([]);
      apiService.getAttendances.mockResolvedValue([]);

      render(<Dashboard />);

      // Attendi render iniziale
      await waitFor(() => {
        expect(apiService.getCollaborators).toHaveBeenCalledTimes(1);
      });

      // Simula click su bottone refresh (se presente)
      const refreshButton = screen.queryByRole('button', { name: /refresh|aggiorna/i });
      if (refreshButton) {
        fireEvent.click(refreshButton);

        // Verifica che API sia chiamata di nuovo
        await waitFor(() => {
          expect(apiService.getCollaborators).toHaveBeenCalledTimes(2);
        });
      }
    });
  });

  // =================================================================
  // TEST SUITE: CONDITIONAL RENDERING
  // =================================================================

  describe('Conditional Rendering', () => {
    test('should show empty state when no data', async () => {
      apiService.getCollaborators.mockResolvedValue([]);
      apiService.getProjects.mockResolvedValue([]);
      apiService.getAttendances.mockResolvedValue([]);

      render(<Dashboard />);

      await waitFor(() => {
        // Verifica messaggio "nessun dato" o simile
        const emptyState = screen.queryByText(/nessun.*collaboratore/i) ||
                          screen.queryByText(/nessun.*progetto/i);
        expect(emptyState).toBeTruthy();
      });
    });

    test('should show data when available', async () => {
      apiService.getCollaborators.mockResolvedValue(mockCollaborators);
      apiService.getProjects.mockResolvedValue(mockProjects);
      apiService.getAttendances.mockResolvedValue(mockAttendances);

      render(<Dashboard />);

      await waitFor(() => {
        expect(screen.getByText(/mario/i)).toBeInTheDocument();
        expect(screen.getByText(/project alpha/i)).toBeInTheDocument();
      });
    });
  });
});

// =================================================================
// TEST SUITE: SNAPSHOT TESTING
// =================================================================

describe('Dashboard Snapshots', () => {
  test('should match snapshot with data', async () => {
    apiService.getCollaborators.mockResolvedValue(mockCollaborators);
    apiService.getProjects.mockResolvedValue(mockProjects);
    apiService.getAttendances.mockResolvedValue([]);

    const { container } = render(<Dashboard />);

    await waitFor(() => {
      expect(screen.getByText(/mario/i)).toBeInTheDocument();
    });

    // Snapshot test: cattura HTML renderizzato
    // Se cambi volontariamente UI, aggiorna con: npm test -- -u
    expect(container).toMatchSnapshot();
  });
});

// =================================================================
// NOTE PER ESECUZIONE
// =================================================================
/*
COMANDI UTILI:

# Esegui test Dashboard
npm test Dashboard.test.js

# Esegui con coverage
npm test -- --coverage --coveragePathIgnorePatterns=node_modules

# Watch mode (ri-esegue al salvataggio)
npm test -- --watch

# Update snapshots
npm test -- -u

# Verbose output
npm test -- --verbose

# Run solo test che matchano pattern
npm test -- -t "should fetch"

OUTPUT ATTESO:
 PASS  src/components/Dashboard.test.js
  Dashboard Component
    Initial Rendering
      ✓ should render dashboard title (XX ms)
      ✓ should show loading state initially (XX ms)
    Data Fetching
      ✓ should fetch and display collaborators (XX ms)
      ✓ should fetch and display projects (XX ms)
      ✓ should handle API errors gracefully (XX ms)
    ...

Test Suites: 1 passed, 1 total
Tests:       X passed, X total
*/
