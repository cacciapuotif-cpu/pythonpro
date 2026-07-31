import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';

import Calendar from './Calendar';
import apiService from '../services/apiService';
import { useAppContext } from '../context/AppContext';

jest.mock('../services/apiService', () => ({
  __esModule: true,
  default: {
    getCalendarAttendances: jest.fn(),
    getProjects: jest.fn(),
    getCollaborators: jest.fn(),
  },
}));

jest.mock('../context/AppContext', () => ({
  useAppContext: jest.fn(),
}));

jest.mock('./AttendanceModal', () => () => <div>Attendance modal</div>);

const CURRENT_USER = { id: 1, username: 'mario.rossi', role: 'admin', collaborator_id: 10 };

const PROJECTS_RESPONSE = [{ id: 1, name: 'Progetto Alfa', is_active: true }];
const CLOSED_PROJECTS_RESPONSE = [];
const COLLABORATORS_RESPONSE = [
  { id: 10, first_name: 'Mario', last_name: 'Rossi' },
  { id: 11, first_name: 'Giulia', last_name: 'Bianchi' },
];

const APP_CONTEXT_VALUE = {
  state: { ui: { modals: {} }, system: { isOnline: true } },
  createEntity: jest.fn(),
  updateEntity: jest.fn(),
  deleteEntity: jest.fn(),
  openModal: jest.fn(),
  closeModal: jest.fn(),
  addNotification: jest.fn(),
};

beforeEach(() => {
  jest.clearAllMocks();
  window.history.replaceState({}, '', '/');
  localStorage.clear();
  useAppContext.mockReturnValue(APP_CONTEXT_VALUE);
  apiService.getProjects.mockImplementation((filters = {}) => (
    Promise.resolve(filters.isActive === false ? CLOSED_PROJECTS_RESPONSE : PROJECTS_RESPONSE)
  ));
  apiService.getCollaborators.mockResolvedValue(COLLABORATORS_RESPONSE);
  apiService.getCalendarAttendances.mockResolvedValue({ items: [], total: 0 });
});

test('al primo caricamento chiama getCalendarAttendances con i filtri di default', async () => {
  render(<Calendar currentUser={CURRENT_USER} />);

  await waitFor(() => expect(apiService.getCalendarAttendances).toHaveBeenCalled());
  const callArgs = apiService.getCalendarAttendances.mock.calls[0][0];
  expect(callArgs.collaboratorIds).toEqual([]);
  expect(callArgs.projectIds).toEqual([]);
  expect(callArgs.includeClosedProjects).toBe(false);
});

test('selezionare un collaboratore rifà la fetch con il filtro e aggiorna la URL', async () => {
  render(<Calendar currentUser={CURRENT_USER} />);
  await screen.findByLabelText(/rossi mario/i);

  fireEvent.click(screen.getByLabelText(/rossi mario/i));

  await waitFor(() => {
    const lastCall = apiService.getCalendarAttendances.mock.calls.at(-1)[0];
    expect(lastCall.collaboratorIds).toEqual([10]);
  });
  expect(window.location.search).toContain('collaborator_ids=10');
});

test('i filtri vengono letti dalla URL al montaggio', async () => {
  window.history.replaceState({}, '', '/?project_ids=1');
  render(<Calendar currentUser={CURRENT_USER} />);

  await waitFor(() => {
    const callArgs = apiService.getCalendarAttendances.mock.calls[0][0];
    expect(callArgs.projectIds).toEqual([1]);
  });
});

test('senza parametri URL, ripristina i filtri salvati in localStorage per l\'utente corrente', async () => {
  localStorage.setItem(
    'pythonpro:calendarFilters:mario.rossi',
    JSON.stringify({
      projectIds: [1], collaboratorIds: [], includeClosedProjects: false, onlyMine: false,
      view: 'month', date: new Date().toISOString(),
    }),
  );
  render(<Calendar currentUser={CURRENT_USER} />);

  await waitFor(() => {
    const callArgs = apiService.getCalendarAttendances.mock.calls[0][0];
    expect(callArgs.projectIds).toEqual([1]);
  });
});

test('oltre la soglia mostra l\'avviso invece del calendario', async () => {
  apiService.getCalendarAttendances.mockResolvedValue({ items: [], total: 500 });
  render(<Calendar currentUser={CURRENT_USER} />);

  expect(await screen.findByText(/restringi i filtri/i)).toBeInTheDocument();
});

test('azzera filtri riporta ai valori di default e pulisce la URL', async () => {
  window.history.replaceState({}, '', '/?project_ids=1');
  render(<Calendar currentUser={CURRENT_USER} />);
  await screen.findByLabelText(/rossi mario/i);

  fireEvent.click(screen.getByRole('button', { name: /azzera filtri/i }));

  await waitFor(() => expect(window.location.search).toBe(''));
});

test('con più collaboratori selezionati e un solo progetto, la legenda mostra i collaboratori', async () => {
  window.history.replaceState({}, '', '/?collaborator_ids=10,11');
  apiService.getCalendarAttendances.mockResolvedValue({
    items: [
      { id: 1, collaborator_id: 10, project_id: 1, date: '2026-07-01T09:00:00', start_time: '2026-07-01T09:00:00', end_time: '2026-07-01T10:00:00', hours: 1 },
    ],
    total: 1,
  });
  render(<Calendar currentUser={CURRENT_USER} />);

  expect(await screen.findByText(/legenda: collaboratori/i)).toBeInTheDocument();
});

test('con più progetti selezionati la legenda mostra i progetti (default)', async () => {
  window.history.replaceState({}, '', '/?project_ids=1,2');
  render(<Calendar currentUser={CURRENT_USER} />);

  expect(await screen.findByText(/legenda: progetti/i)).toBeInTheDocument();
});
