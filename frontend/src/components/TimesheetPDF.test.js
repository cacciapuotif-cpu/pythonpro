import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import TimesheetPDF from './TimesheetPDF';
import { http } from '../lib/http';

// B5.1: separazione comando/interrogazione sul timesheet.
// - Generazione (side-effect) -> POST /assignments/{id}/timesheet
// - Download snapshot bloccato (read-only) -> GET /assignments/{id}/timesheet

jest.mock('../lib/http', () => ({
  http: { get: jest.fn(), post: jest.fn() },
}));

const listResponse = (assignments) => ({
  data: { project_id: 1, project_name: 'Progetto X', assignments },
});

const baseAssignment = (overrides = {}) => ({
  assignment_id: 7,
  collaboratore: 'Ada Lovelace',
  ruolo: 'Docente',
  ore_assegnate: 20,
  ore_effettive: 3,
  presenze_count: 1,
  timesheet_generato: false,
  timesheet_bloccato: false,
  ...overrides,
});

beforeEach(() => {
  jest.clearAllMocks();
  global.URL.createObjectURL = jest.fn(() => 'blob:mock');
  global.URL.revokeObjectURL = jest.fn();
});

test('timesheet non generato: il bottone PDF genera via POST', async () => {
  http.get.mockImplementation((url) => {
    if (url.startsWith('/projects/')) {
      return Promise.resolve(listResponse([baseAssignment()]));
    }
    return Promise.reject(new Error('GET inatteso su ' + url));
  });
  http.post.mockResolvedValue({
    data: new Blob(['%PDF'], { type: 'application/pdf' }),
  });

  render(<TimesheetPDF projectId={1} />);
  const btn = await screen.findByRole('button', { name: /^PDF$/ });
  fireEvent.click(btn);

  await waitFor(() =>
    expect(http.post).toHaveBeenCalledWith(
      '/assignments/7/timesheet',
      null,
      expect.objectContaining({ responseType: 'blob' }),
    ),
  );
  // La GET (read-only) non deve essere usata per generare.
  const downloadGets = http.get.mock.calls.filter(([u]) =>
    u.startsWith('/assignments/'),
  );
  expect(downloadGets).toHaveLength(0);
});

test('timesheet generato e bloccato: il bottone PDF scarica via GET read-only', async () => {
  http.get.mockImplementation((url) => {
    if (url.startsWith('/projects/')) {
      return Promise.resolve(
        listResponse([
          baseAssignment({ timesheet_generato: true, timesheet_bloccato: true }),
        ]),
      );
    }
    // download snapshot esistente
    return Promise.resolve({
      data: new Blob(['%PDF'], { type: 'application/pdf' }),
    });
  });

  render(<TimesheetPDF projectId={1} />);
  const btn = await screen.findByRole('button', { name: /^PDF$/ });
  fireEvent.click(btn);

  await waitFor(() =>
    expect(http.get).toHaveBeenCalledWith(
      '/assignments/7/timesheet',
      expect.objectContaining({ responseType: 'blob' }),
    ),
  );
  // Nessuna generazione/rigenerazione: la POST non viene chiamata.
  expect(http.post).not.toHaveBeenCalled();
});

test('timesheet sbloccato: il bottone PDF rigenera via POST', async () => {
  http.get.mockImplementation((url) => {
    if (url.startsWith('/projects/')) {
      return Promise.resolve(
        listResponse([
          baseAssignment({ timesheet_generato: true, timesheet_bloccato: false }),
        ]),
      );
    }
    return Promise.reject(new Error('GET inatteso su ' + url));
  });
  http.post.mockResolvedValue({
    data: new Blob(['%PDF'], { type: 'application/pdf' }),
  });

  render(<TimesheetPDF projectId={1} />);
  const btn = await screen.findByRole('button', { name: /^PDF$/ });
  fireEvent.click(btn);

  await waitFor(() =>
    expect(http.post).toHaveBeenCalledWith(
      '/assignments/7/timesheet',
      null,
      expect.objectContaining({ responseType: 'blob' }),
    ),
  );
});
