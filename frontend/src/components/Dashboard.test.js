import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import Dashboard from './Dashboard';
import apiService from '../services/apiService';

jest.mock('../services/apiService', () => ({
  __esModule: true,
  default: {
    getSummaryReport: jest.fn(),
    getTimesheetReport: jest.fn(),
    getCollaborators: jest.fn(),
    getProjects: jest.fn(),
    getAssignments: jest.fn(),
    getContractTemplates: jest.fn(),
    getSystemMetrics: jest.fn(),
  },
}));

const baseSummary = {
  periodo: { from: null, to: null },
  kpi_generali: {
    totale_collaboratori: 2,
    totale_progetti: 2,
    totale_enti_attuatori: 1,
    totale_ore_lavorate: 64,
    totale_presenze: 8,
  },
  top_5_progetti: [{ id: 1, nome: 'Progetto Alpha', ore_totali: 40 }],
  top_5_collaboratori: [{ id: 1, nome: 'Mario Rossi', ore_totali: 32 }],
  distribuzione_contratti: [{ tipo: 'professionale', numero: 1 }],
};

const baseCollaborators = [
  {
    id: 1,
    first_name: 'Mario',
    last_name: 'Rossi',
    documento_identita_filename: null,
    documento_identita_scadenza: null,
  },
  {
    id: 2,
    first_name: 'Luigi',
    last_name: 'Verdi',
    documento_identita_filename: 'carta.pdf',
    documento_identita_scadenza: '2099-12-31T00:00:00Z',
  },
];

const baseProjects = [
  { id: 1, name: 'Progetto Alpha', status: 'active', end_date: '2099-12-31T00:00:00Z' },
  { id: 2, name: 'Progetto Beta', status: 'draft', end_date: null },
];

const baseAssignments = [
  {
    id: 11,
    collaborator_id: 1,
    project_id: 1,
    contract_type: null,
    assigned_hours: 24,
    hourly_rate: 25,
    start_date: '2026-03-01T00:00:00Z',
    end_date: '2026-03-20T00:00:00Z',
    is_active: true,
  },
];

beforeEach(() => {
  jest.clearAllMocks();
  apiService.getSummaryReport.mockResolvedValue(baseSummary);
  apiService.getTimesheetReport.mockResolvedValue({
    totali: {
      ore_totali: 64,
      numero_presenze: 8,
    },
  });
  apiService.getCollaborators.mockResolvedValue(baseCollaborators);
  apiService.getProjects.mockResolvedValue(baseProjects);
  apiService.getAssignments.mockResolvedValue(baseAssignments);
  apiService.getContractTemplates.mockResolvedValue([
    { id: 8, tipo_contratto: 'professionale', is_default: true, is_active: true },
  ]);
  apiService.getSystemMetrics.mockResolvedValue({
    dashboard_metrics: {
      total_requests: 10,
    },
  });
});

describe('Dashboard', () => {
  test('renderizza il cockpit operativo con KPI e ranking', async () => {
    render(<Dashboard currentUser={{ role: 'admin' }} />);

    await waitFor(() => {
      expect(screen.getByText(/dashboard e compliance center/i)).toBeInTheDocument();
      expect(screen.getByText('Collaboratori')).toBeInTheDocument();
      expect(screen.getByText('Progetto Alpha')).toBeInTheDocument();
      expect(screen.getByText('Mario Rossi')).toBeInTheDocument();
    });

    expect(apiService.getSystemMetrics).toHaveBeenCalledTimes(1);
  });

  test('mostra alert documentali e di assegnazione', async () => {
    render(<Dashboard currentUser={{ role: 'operator' }} />);

    await waitFor(() => {
      expect(screen.getByText(/documento identita assente/i)).toBeInTheDocument();
      expect(screen.getByText(/assegnazione senza tipo contratto/i)).toBeInTheDocument();
      expect(screen.getByText(/vista operativa del team/i)).toBeInTheDocument();
    });

    expect(apiService.getSystemMetrics).not.toHaveBeenCalled();
  });

  test('segnala template contrattuali mancanti per i tipi usati', async () => {
    apiService.getAssignments.mockResolvedValue([
      {
        id: 12,
        collaborator_id: 1,
        project_id: 1,
        contract_type: 'contratto_progetto',
        assigned_hours: 24,
        hourly_rate: 25,
        start_date: '2026-03-01T00:00:00Z',
        end_date: '2026-03-20T00:00:00Z',
        is_active: true,
      },
    ]);
    apiService.getContractTemplates.mockResolvedValue([
      { id: 8, tipo_contratto: 'professionale', is_default: true, is_active: true },
    ]);

    render(<Dashboard currentUser={{ role: 'admin' }} />);

    await waitFor(() => {
      expect(screen.getByText(/template default mancante/i)).toBeInTheDocument();
      expect(screen.getAllByText(/contratto_progetto/i).length).toBeGreaterThan(0);
    });
  });

  test('mostra il focus di governo per admin', async () => {
    render(<Dashboard currentUser={{ role: 'admin' }} />);

    await waitFor(() => {
      expect(screen.getByText(/vista di governo del sistema/i)).toBeInTheDocument();
      expect(screen.getByText(/metriche backend/i)).toBeInTheDocument();
    });
  });

  test('consente refresh manuale del cockpit', async () => {
    render(<Dashboard currentUser={{ role: 'admin' }} />);

    await waitFor(() => {
      expect(apiService.getSummaryReport).toHaveBeenCalledTimes(1);
      expect(screen.getByRole('button', { name: /aggiorna cockpit/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /aggiorna cockpit/i }));

    await waitFor(() => {
      expect(apiService.getSummaryReport).toHaveBeenCalledTimes(2);
    });
  });
});
