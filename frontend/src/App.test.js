import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import App from './App';
import apiService, { healthCheck } from './services/apiService';
import { ensureValidAccessToken } from './lib/http';

jest.mock('./services/apiService', () => ({
  __esModule: true,
  default: {
    getCurrentUser: jest.fn(),
  },
  healthCheck: jest.fn(),
}));

jest.mock('./lib/http', () => ({
  http: {},
  ensureValidAccessToken: jest.fn(),
}));

jest.mock('./components/Dashboard', () => () => <div>Dashboard test</div>);
jest.mock('./components/Calendar', () => () => <div>Calendario test</div>);
jest.mock('./components/CollaboratorManager', () => () => <div>Collaboratori test</div>);
jest.mock('./components/TimesheetReport', () => () => <div>Report Ore test</div>);
jest.mock('./components/TimesheetPDF', () => () => <div>PDF Timesheet test</div>);

const ADMIN = {
  id: 1,
  username: 'ui_admin',
  full_name: 'UI Admin',
  role: 'admin',
};

const LEGACY_OPERATOR = {
  id: 2,
  username: 'ui_user',
  full_name: 'UI User',
  role: 'user',
};

beforeEach(() => {
  jest.clearAllMocks();
  window.history.replaceState({}, '', '/');
  healthCheck.mockResolvedValue({ status: 'ok' });
  ensureValidAccessToken.mockResolvedValue(false);
});

test('senza sessione mostra i profili di accesso correnti', async () => {
  render(<App />);

  expect(await screen.findByRole('heading', { name: /accesso al gestionale/i })).toBeInTheDocument();
  expect(screen.getByText('Amministratore', { selector: '.profile-title' })).toBeInTheDocument();
  expect(screen.getByText('Operatore', { selector: '.profile-title' })).toBeInTheDocument();
});

test('admin autenticato vede la navigazione amministrativa', async () => {
  ensureValidAccessToken.mockResolvedValue(true);
  apiService.getCurrentUser.mockResolvedValue(ADMIN);

  render(<App />);

  expect(await screen.findByRole('button', { name: /enti attuatori/i })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /timesheet/i })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /agenti$/i })).toBeInTheDocument();
});

test('click su Timesheet cambia sezione senza cambiare applicazione', async () => {
  ensureValidAccessToken.mockResolvedValue(true);
  apiService.getCurrentUser.mockResolvedValue(ADMIN);

  render(<App />);
  const button = await screen.findByRole('button', { name: /timesheet/i });
  fireEvent.click(button);

  expect(await screen.findByText('Report Ore test')).toBeInTheDocument();
  expect(button).toHaveClass('active');
});

test('il ruolo user legacy vede le sezioni operative ma non quelle admin', async () => {
  ensureValidAccessToken.mockResolvedValue(true);
  apiService.getCurrentUser.mockResolvedValue(LEGACY_OPERATOR);

  render(<App />);

  await waitFor(() => {
    expect(screen.getByRole('button', { name: /collaboratori/i })).toBeInTheDocument();
  });
  expect(screen.queryByRole('button', { name: /enti attuatori/i })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /agenti$/i })).not.toBeInTheDocument();
});
