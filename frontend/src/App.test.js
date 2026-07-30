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
    requestPasswordReset: jest.fn(),
    resetPassword: jest.fn(),
  },
  healthCheck: jest.fn(),
}));

jest.mock('./lib/http', () => ({
  http: {},
  ensureValidAccessToken: jest.fn(),
}));

jest.mock('./components/Dashboard', () => () => <div>Dashboard test</div>);
jest.mock('./components/HomeCockpit', () => ({ onNavigate }) => (
  <div>
    Home test
    <button type="button" onClick={() => onNavigate({ section: 'projects', filters: { status: 'active' } })}>
      Vai ai progetti attivi
    </button>
  </div>
));
jest.mock('./components/AreaPersonale', () => ({ currentUser, onPasswordChanged }) => (
  <div>
    <button type="button">Area personale</button>
    <span>{currentUser?.full_name}</span>
    <button type="button" onClick={() => onPasswordChanged('Password aggiornata. Effettua di nuovo l’accesso.')}>
      Simula cambio password
    </button>
  </div>
));
jest.mock('./components/Calendar', () => () => <div>Calendario test</div>);
jest.mock('./components/PortaleAllievi', () => () => <div>Portale pubblico test</div>);
jest.mock('./components/CollaboratorManager', () => () => <div>Collaboratori test</div>);
jest.mock('./components/ProjectManager', () => ({ initialFilters }) => (
  <div>Progetti test filtro {initialFilters.status || 'all'}</div>
));
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

const CANONICAL_OPERATOR = {
  id: 3,
  username: 'ui_operatore',
  full_name: 'UI Operatore',
  role: 'operatore',
};

const CONSULTATION_USER = {
  id: 4,
  username: 'ui_consultazione',
  full_name: 'UI Consultazione',
  role: 'consultazione',
};

const navigationLabels = () => screen
  .queryAllByRole('navigation')[0]
  ?.querySelectorAll('.nav-button')
  ? Array.from(screen.getByRole('navigation').querySelectorAll('.nav-button'))
    .map((button) => button.textContent.replace(/^\S+\s*/, '').trim())
  : [];

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

test('dal login apre il recupero password e invia la richiesta email', async () => {
  apiService.requestPasswordReset.mockResolvedValue({
    status: 'accepted',
    message: 'Se l’indirizzo è associato a un account attivo, riceverai un link.',
  });
  render(<App />);

  fireEvent.click(await screen.findByRole('button', { name: /password dimenticata/i }));
  fireEvent.change(screen.getByLabelText(/^email$/i), {
    target: { value: 'mario@example.com' },
  });
  fireEvent.click(screen.getByRole('button', { name: /invia link/i }));

  await waitFor(() => expect(apiService.requestPasswordReset).toHaveBeenCalledWith(
    'mario@example.com',
  ));
  expect(await screen.findByRole('status')).toHaveTextContent(
    'Se l’indirizzo è associato',
  );
});

test('la rotta reset password precede il login e rimuove subito il token dalla URL', async () => {
  window.history.replaceState({}, '', '/reset-password#token=reset-token-value');

  render(<App />);

  expect(await screen.findByRole('heading', { name: /reimposta la password/i })).toBeInTheDocument();
  await waitFor(() => expect(window.location.hash).toBe(''));
  expect(screen.queryByRole('heading', { name: /accesso al gestionale/i })).not.toBeInTheDocument();
});

test('reset riuscito cancella i token locali e torna al login con conferma', async () => {
  window.history.replaceState({}, '', '/reset-password#token=reset-token-value');
  localStorage.setItem('access_token', 'old-access');
  localStorage.setItem('refresh_token', 'old-refresh');
  apiService.resetPassword.mockResolvedValue({
    status: 'password_reset',
    message: 'Password reimpostata. Ora puoi accedere con la nuova password.',
  });

  render(<App />);
  fireEvent.change(await screen.findByLabelText(/^nuova password/i), {
    target: { value: 'RecoveredPassword789!' },
  });
  fireEvent.change(screen.getByLabelText(/conferma nuova password/i), {
    target: { value: 'RecoveredPassword789!' },
  });
  fireEvent.click(screen.getByRole('button', { name: /^reimposta password$/i }));

  expect(await screen.findByRole('heading', { name: /accesso al gestionale/i })).toBeInTheDocument();
  expect(screen.getByRole('status')).toHaveTextContent('Password reimpostata');
  expect(localStorage.getItem('access_token')).toBeNull();
  expect(localStorage.getItem('refresh_token')).toBeNull();
  expect(window.location.pathname).toBe('/');
});

test('il portale magic-token precede sempre il login ERP', async () => {
  window.history.replaceState({}, '', '/portale-allievi?token=magic-valido');

  render(<App />);

  expect(await screen.findByText('Portale pubblico test')).toBeInTheDocument();
  expect(screen.queryByRole('heading', { name: /accesso al gestionale/i })).not.toBeInTheDocument();
});

test('admin autenticato vede la navigazione amministrativa', async () => {
  ensureValidAccessToken.mockResolvedValue(true);
  apiService.getCurrentUser.mockResolvedValue(ADMIN);

  render(<App />);

  expect(await screen.findByRole('button', { name: /enti attuatori/i })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /timesheet/i })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /agenti$/i })).toBeInTheDocument();
});

test('la documentazione tecnica non è esposta nel gestionale operativo', async () => {
  ensureValidAccessToken.mockResolvedValue(true);
  apiService.getCurrentUser.mockResolvedValue(ADMIN);

  const { unmount } = render(<App />);
  await screen.findByText(ADMIN.full_name);
  expect(screen.queryByRole('link', { name: /documentazione api/i })).not.toBeInTheDocument();
  unmount();

  apiService.getCurrentUser.mockResolvedValue(CANONICAL_OPERATOR);
  render(<App />);
  await screen.findByText(CANONICAL_OPERATOR.full_name);
  expect(screen.queryByRole('link', { name: /documentazione api/i })).not.toBeInTheDocument();
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

test('il Cockpit passa pagina e filtro fino alla sezione di destinazione', async () => {
  ensureValidAccessToken.mockResolvedValue(true);
  apiService.getCurrentUser.mockResolvedValue(ADMIN);

  render(<App />);
  fireEvent.click(await screen.findByRole('button', { name: /^🏠 Home$/i }));
  fireEvent.click(await screen.findByRole('button', { name: /vai ai progetti attivi/i }));

  expect(await screen.findByText('Progetti test filtro active')).toBeInTheDocument();
  expect(window.location.pathname).toBe('/projects');
  expect(window.location.search).toBe('?status=active');
});

test('dopo il cambio password cancella la sessione e torna al login', async () => {
  ensureValidAccessToken.mockResolvedValue(true);
  apiService.getCurrentUser.mockResolvedValue(ADMIN);
  localStorage.setItem('access_token', 'old-access');
  localStorage.setItem('refresh_token', 'old-refresh');

  render(<App />);
  fireEvent.click(await screen.findByRole('button', { name: /^🏠 Home$/i }));
  fireEvent.click(screen.getByRole('button', { name: /simula cambio password/i }));

  expect(await screen.findByRole('heading', { name: /accesso al gestionale/i })).toBeInTheDocument();
  expect(screen.getByRole('status')).toHaveTextContent('Password aggiornata');
  expect(localStorage.getItem('access_token')).toBeNull();
  expect(localStorage.getItem('refresh_token')).toBeNull();
});

test('il ruolo user legacy viene normalizzato a operatore', async () => {
  ensureValidAccessToken.mockResolvedValue(true);
  apiService.getCurrentUser.mockResolvedValue(LEGACY_OPERATOR);

  render(<App />);

  await waitFor(() => {
    expect(screen.getByRole('button', { name: /collaboratori/i })).toBeInTheDocument();
  });
  expect(screen.getByRole('button', { name: /enti attuatori/i })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /agenti$/i })).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /template/i })).not.toBeInTheDocument();
});

test.each([
  [ADMIN, [
    'Home', 'Dashboard', 'Calendario', 'Timesheet', 'Documenti', 'Collaboratori',
    'Allievi', 'Progetti', 'Aziende', 'Catalogo', 'Listini', 'Preventivi', 'Ordini',
    'Archivio Risorse', 'Chiedi all’archivio', 'Enti Attuatori', 'Utenti', 'Agents Dashboard', 'Agenti', 'Template',
  ]],
  [CANONICAL_OPERATOR, [
    'Home', 'Dashboard', 'Calendario', 'Timesheet', 'Documenti', 'Collaboratori',
    'Allievi', 'Progetti', 'Aziende', 'Catalogo', 'Listini', 'Preventivi', 'Ordini',
    'Archivio Risorse', 'Chiedi all’archivio', 'Enti Attuatori', 'Agents Dashboard', 'Agenti',
  ]],
  [CONSULTATION_USER, [
    'Home', 'Dashboard', 'Calendario', 'Documenti', 'Collaboratori', 'Allievi',
    'Progetti', 'Aziende', 'Catalogo', 'Listini', 'Preventivi', 'Ordini',
    'Archivio Risorse', 'Chiedi all’archivio', 'Enti Attuatori', 'Agents Dashboard', 'Agenti',
  ]],
])('la navigazione del ruolo canonico %s rispetta la matrice backend', async (user, expected) => {
  ensureValidAccessToken.mockResolvedValue(true);
  apiService.getCurrentUser.mockResolvedValue(user);

  render(<App />);

  await screen.findByText(user.full_name);
  expect(navigationLabels()).toEqual(expected);
});
