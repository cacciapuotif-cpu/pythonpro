import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom';

import UserManagement from './UserManagement';
import apiService from '../services/apiService';

jest.mock('../services/apiService', () => ({
  __esModule: true,
  default: {
    listUsers: jest.fn(),
    createUser: jest.fn(),
    updateUser: jest.fn(),
    deleteUser: jest.fn(),
    resendUserInvite: jest.fn(),
  },
}));

const ADMIN_ROW = {
  id: 1,
  username: 'admin',
  email: 'admin@example.test',
  full_name: 'Amministratore Sistema',
  role: 'admin',
  is_active: true,
  created_at: '2026-01-01T10:00:00Z',
};

const OPERATOR_ROW = {
  id: 2,
  username: 'mario_rossi',
  email: 'mario@example.test',
  full_name: 'Mario Rossi',
  first_name: 'Mario',
  last_name: 'Rossi',
  role: 'operatore',
  is_active: true,
  created_at: '2026-01-02T10:00:00Z',
};

const CURRENT_ADMIN = { id: 1, username: 'admin', role: 'admin' };

const openCreateForm = () => {
  fireEvent.click(screen.getByRole('button', { name: /nuovo utente/i }));
};

beforeEach(() => {
  jest.clearAllMocks();
  apiService.listUsers.mockResolvedValue({ users: [ADMIN_ROW, OPERATOR_ROW] });
});

test('carica ed elenca gli utenti esistenti ordinati per nome', async () => {
  render(<UserManagement currentUser={CURRENT_ADMIN} />);

  expect(await screen.findByText('admin')).toBeInTheDocument();
  expect(screen.getByText('mario_rossi')).toBeInTheDocument();
  expect(screen.getByText('admin@example.test')).toBeInTheDocument();
});

test('crea un nuovo utente con il ruolo scelto e mostra conferma invito', async () => {
  apiService.createUser.mockResolvedValue({
    id: 3,
    username: 'nuovo.operatore',
    email: 'nuovo@example.test',
    full_name: 'Nuovo Operatore',
    first_name: 'Nuovo',
    last_name: 'Operatore',
    role: 'operatore',
    is_active: true,
    invite_queued: true,
  });

  render(<UserManagement currentUser={CURRENT_ADMIN} />);
  await screen.findByText('admin');
  openCreateForm();

  fireEvent.change(screen.getByLabelText(/^email$/i), { target: { value: 'nuovo@example.test' } });
  fireEvent.change(screen.getByLabelText(/^nome$/i), { target: { value: 'Nuovo' } });
  fireEvent.change(screen.getByLabelText(/^cognome$/i), { target: { value: 'Operatore' } });
  fireEvent.change(screen.getByLabelText(/ruolo/i), { target: { value: 'operatore' } });
  fireEvent.click(screen.getByRole('button', { name: /^crea utente$/i }));

  await waitFor(() => {
    expect(apiService.createUser).toHaveBeenCalledWith({
      email: 'nuovo@example.test',
      first_name: 'Nuovo',
      last_name: 'Operatore',
      role: 'operatore',
    });
  });

  expect(await screen.findByRole('status')).toHaveTextContent(/invio del link.*predisposto/i);
});

test('mostra l\'errore del backend senza cancellare i campi già compilati', async () => {
  apiService.createUser.mockRejectedValue({
    response: { data: { detail: 'Username o email già in uso' } },
  });

  render(<UserManagement currentUser={CURRENT_ADMIN} />);
  await screen.findByText('admin');
  openCreateForm();

  fireEvent.change(screen.getByLabelText(/^email$/i), { target: { value: 'admin@example.test' } });
  fireEvent.change(screen.getByLabelText(/^nome$/i), { target: { value: 'Nome' } });
  fireEvent.change(screen.getByLabelText(/^cognome$/i), { target: { value: 'Duplicato' } });
  fireEvent.click(screen.getByRole('button', { name: /^crea utente$/i }));

  expect(await screen.findByRole('alert')).toHaveTextContent(/già in uso/i);
  expect(screen.getByLabelText(/^nome$/i)).toHaveValue('Nome');
});

test('modifica un utente esistente: username bloccato, resto modificabile', async () => {
  apiService.updateUser.mockResolvedValue({ ...OPERATOR_ROW, full_name: 'Mario Rossi Bis', role: 'consultazione' });

  render(<UserManagement currentUser={CURRENT_ADMIN} />);
  await screen.findByText('mario_rossi');

  const card = screen.getByText('mario_rossi').closest('.user-card');
  fireEvent.click(within(card).getByTitle('Modifica'));

  expect(screen.getByLabelText(/username/i)).toBeDisabled();
  expect(screen.getByLabelText(/username/i)).toHaveValue('mario_rossi');

  fireEvent.change(screen.getByLabelText(/^cognome$/i), { target: { value: 'Rossi Bis' } });
  fireEvent.change(screen.getByLabelText(/ruolo/i), { target: { value: 'consultazione' } });
  fireEvent.click(screen.getByRole('button', { name: /salva modifiche/i }));

  await waitFor(() => {
    expect(apiService.updateUser).toHaveBeenCalledWith(2, {
      full_name: 'Mario Rossi Bis',
      email: 'mario@example.test',
      role: 'consultazione',
    });
  });
});

test('per il proprio account disabilita email e non la invia al router admin', async () => {
  apiService.updateUser.mockResolvedValue(ADMIN_ROW);

  render(<UserManagement currentUser={CURRENT_ADMIN} />);
  await screen.findByText('admin');

  const selfCard = screen.getByText('admin').closest('.user-card');
  fireEvent.click(within(selfCard).getByTitle('Modifica'));
  expect(screen.getByLabelText(/^email/i)).toBeDisabled();
  expect(screen.getByText(/usa l’area personale/i)).toBeInTheDocument();

  fireEvent.click(screen.getByRole('button', { name: /salva modifiche/i }));
  await waitFor(() => {
    expect(apiService.updateUser).toHaveBeenCalledWith(1, {
      full_name: 'Amministratore Sistema',
      role: 'admin',
    });
  });
});

test('disattiva un utente cliccando il bottone di stato', async () => {
  apiService.updateUser.mockResolvedValue({ ...OPERATOR_ROW, is_active: false });

  render(<UserManagement currentUser={CURRENT_ADMIN} />);
  await screen.findByText('mario_rossi');

  const card = screen.getByText('mario_rossi').closest('.user-card');
  fireEvent.click(within(card).getByTitle('Disattiva'));

  await waitFor(() => {
    expect(apiService.updateUser).toHaveBeenCalledWith(2, { is_active: false });
  });
});

test('elimina un utente dopo conferma nel modal', async () => {
  apiService.deleteUser.mockResolvedValue(undefined);

  render(<UserManagement currentUser={CURRENT_ADMIN} />);
  await screen.findByText('mario_rossi');

  const card = screen.getByText('mario_rossi').closest('.user-card');
  fireEvent.click(within(card).getByTitle('Elimina'));

  expect(screen.getByText(/conferma eliminazione/i)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /^🗑️ elimina$/i }));

  await waitFor(() => {
    expect(apiService.deleteUser).toHaveBeenCalledWith(2);
  });
});

test('reinvia le credenziali a un utente attivo', async () => {
  apiService.resendUserInvite.mockResolvedValue({ status: 'invite_queued', email: OPERATOR_ROW.email });

  render(<UserManagement currentUser={CURRENT_ADMIN} />);
  await screen.findByText('mario_rossi');

  const card = screen.getByText('mario_rossi').closest('.user-card');
  fireEvent.click(within(card).getByTitle('Reinvia credenziali'));

  await waitFor(() => {
    expect(apiService.resendUserInvite).toHaveBeenCalledWith(2);
  });
  expect(await screen.findByRole('status')).toHaveTextContent(/invio del link.*predisposto.*mario@example.test/i);
});

test('non permette di disattivare o eliminare il proprio account', async () => {
  render(<UserManagement currentUser={CURRENT_ADMIN} />);
  await screen.findByText('admin');

  const selfCard = screen.getByText('admin').closest('.user-card');
  expect(within(selfCard).getByTitle('Non puoi disattivare te stesso')).toBeDisabled();
  expect(within(selfCard).getByTitle('Non puoi eliminare te stesso')).toBeDisabled();
});

test('filtra la lista in base al testo cercato', async () => {
  render(<UserManagement currentUser={CURRENT_ADMIN} />);
  await screen.findByText('mario_rossi');

  fireEvent.change(screen.getByPlaceholderText(/cerca per username/i), { target: { value: 'mario' } });

  expect(screen.queryByText('admin')).not.toBeInTheDocument();
  expect(screen.getByText('mario_rossi')).toBeInTheDocument();
});
