import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import TimesheetReport from './TimesheetReport';
import apiService from '../services/apiService';

jest.mock('../hooks/useEntity', () => ({
  useCollaborators: () => ({ data: [], loading: false }),
  useProjects: () => ({ data: [], loading: false }),
}));

jest.mock('../services/apiService', () => ({
  __esModule: true,
  default: {
    getTimesheetReport: jest.fn(),
    startTimesheetExport: jest.fn(),
    getTimesheetExport: jest.fn(),
  },
}));

beforeEach(() => {
  apiService.getTimesheetReport.mockResolvedValue({
    items: [], total: 0,
    totali: { ore_totali: 0, numero_presenze: 0, per_collaboratore: [], per_progetto: [] },
  });
});

test.each([
  ['admin', true],
  ['operatore', false],
  ['consultazione', false],
])('export timesheet visibile per %s: %s', async (role, expected) => {
  render(<TimesheetReport currentUser={{ role }} />);
  await screen.findByRole('heading', { name: /timesheet report/i });
  const exportButton = screen.queryByRole('button', { name: /export csv/i });
  expect(Boolean(exportButton)).toBe(expected);
});

