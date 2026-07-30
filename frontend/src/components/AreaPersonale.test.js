import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

import AreaPersonale from './AreaPersonale';
import apiService from '../services/apiService';

jest.mock('../services/apiService', () => ({
  __esModule: true,
  default: {
    updateCurrentUser: jest.fn(),
    changePassword: jest.fn(),
    getCurrentUserAvatar: jest.fn(),
    uploadCurrentUserAvatar: jest.fn(),
    deleteCurrentUserAvatar: jest.fn(),
  },
}));

const USER = {
  id: 7,
  username: 'mario.rossi',
  full_name: 'Mario Rossi',
  first_name: 'Mario',
  last_name: 'Rossi',
  email: 'mario@example.test',
  phone: '',
  has_avatar: false,
  role: 'operatore',
};

const openArea = () => {
  fireEvent.click(screen.getByRole('button', { name: /area personale/i }));
};

beforeEach(() => {
  jest.clearAllMocks();
});

test('mostra username non modificabile e dati personali editabili', () => {
  render(<AreaPersonale currentUser={USER} />);
  openArea();

  expect(screen.getByDisplayValue('mario.rossi')).toBeDisabled();
  expect(screen.getByLabelText(/^nome$/i)).toHaveValue('Mario');
  expect(screen.getByLabelText(/^cognome$/i)).toHaveValue('Rossi');
  expect(screen.getByLabelText(/^email$/i)).toHaveValue('mario@example.test');
  expect(screen.getByLabelText(/^telefono$/i)).toHaveValue('');
});

test('salva nome cognome telefono ed email e propaga il profilo aggiornato', async () => {
  const onUserUpdated = jest.fn();
  const updated = {
    ...USER,
    full_name: 'Mario Bianchi',
    last_name: 'Bianchi',
    phone: '+39 333 123 4567',
    email: 'nuova@example.test',
  };
  apiService.updateCurrentUser.mockResolvedValue(updated);

  render(<AreaPersonale currentUser={USER} onUserUpdated={onUserUpdated} />);
  openArea();
  fireEvent.change(screen.getByLabelText(/^cognome$/i), { target: { value: ' Bianchi ' } });
  fireEvent.change(screen.getByLabelText(/^telefono$/i), { target: { value: ' +39 333 123 4567 ' } });
  fireEvent.change(screen.getByLabelText(/^email$/i), { target: { value: 'nuova@example.test' } });
  fireEvent.change(screen.getByLabelText(/password attuale per cambiare email/i), {
    target: { value: 'CurrentPass123!' },
  });
  fireEvent.click(screen.getByRole('button', { name: /salva informazioni/i }));

  await waitFor(() => expect(apiService.updateCurrentUser).toHaveBeenCalledWith({
    first_name: 'Mario',
    last_name: 'Bianchi',
    email: 'nuova@example.test',
    phone: '+39 333 123 4567',
    current_password: 'CurrentPass123!',
  }));
  await waitFor(() => expect(onUserUpdated).toHaveBeenCalledWith(updated));
  expect(await screen.findByRole('status')).toHaveTextContent('Informazioni aggiornate');
  expect(screen.getByLabelText(/password attuale per cambiare email/i)).toHaveValue('');
});

test('il solo cambio nome non invia una password vuota', async () => {
  apiService.updateCurrentUser.mockResolvedValue({ ...USER, first_name: 'Marco', full_name: 'Marco Rossi' });
  render(<AreaPersonale currentUser={USER} />);
  openArea();
  fireEvent.change(screen.getByLabelText(/^nome$/i), {
    target: { value: 'Marco' },
  });
  fireEvent.click(screen.getByRole('button', { name: /salva informazioni/i }));

  await waitFor(() => expect(apiService.updateCurrentUser).toHaveBeenCalledWith({
    first_name: 'Marco',
    last_name: 'Rossi',
    email: 'mario@example.test',
    phone: null,
  }));
});

test('carica la foto profilo e aggiorna l’utente corrente', async () => {
  const onUserUpdated = jest.fn();
  const updated = { ...USER, has_avatar: true };
  apiService.uploadCurrentUserAvatar.mockResolvedValue(updated);
  render(<AreaPersonale currentUser={USER} onUserUpdated={onUserUpdated} />);
  openArea();

  const file = new File(['avatar'], 'avatar.png', { type: 'image/png' });
  fireEvent.change(document.querySelector('input[type="file"]'), {
    target: { files: [file] },
  });

  await waitFor(() => expect(apiService.uploadCurrentUserAvatar).toHaveBeenCalledWith(file));
  await waitFor(() => expect(onUserUpdated).toHaveBeenCalledWith(updated));
});

test('blocca localmente una conferma password diversa', async () => {
  render(<AreaPersonale currentUser={USER} />);
  openArea();
  fireEvent.change(screen.getByLabelText(/^password attuale$/i), { target: { value: 'CurrentPass123!' } });
  fireEvent.change(document.querySelector('input[name="new_password"]'), { target: { value: 'NewPassword456!' } });
  fireEvent.change(screen.getByLabelText(/conferma nuova password/i), { target: { value: 'DifferentPass456!' } });
  fireEvent.click(screen.getByRole('button', { name: /cambia password/i }));

  expect(await screen.findByRole('alert')).toHaveTextContent('La conferma non coincide');
  expect(apiService.changePassword).not.toHaveBeenCalled();
});

test('dopo il cambio password richiede la chiusura della sessione', async () => {
  const onPasswordChanged = jest.fn();
  apiService.changePassword.mockResolvedValue({
    status: 'password_changed',
    message: 'Password aggiornata. Effettua di nuovo l’accesso.',
  });

  render(<AreaPersonale currentUser={USER} onPasswordChanged={onPasswordChanged} />);
  openArea();
  fireEvent.change(screen.getByLabelText(/^password attuale$/i), { target: { value: 'CurrentPass123!' } });
  fireEvent.change(document.querySelector('input[name="new_password"]'), { target: { value: 'NewPassword456!' } });
  fireEvent.change(screen.getByLabelText(/conferma nuova password/i), { target: { value: 'NewPassword456!' } });
  fireEvent.click(screen.getByRole('button', { name: /cambia password/i }));

  await waitFor(() => expect(apiService.changePassword).toHaveBeenCalledWith({
    current_password: 'CurrentPass123!',
    new_password: 'NewPassword456!',
    confirm_password: 'NewPassword456!',
  }));
  await waitFor(() => expect(onPasswordChanged).toHaveBeenCalledWith(
    'Password aggiornata. Effettua di nuovo l’accesso.'
  ));
});

test('rende leggibile un errore restituito dal backend', async () => {
  apiService.updateCurrentUser.mockRejectedValue({
    response: { status: 409, data: { detail: 'Questa email è già associata a un altro account' } },
  });

  render(<AreaPersonale currentUser={USER} />);
  openArea();
  fireEvent.click(screen.getByRole('button', { name: /salva informazioni/i }));

  expect(await screen.findByRole('alert')).toHaveTextContent('email è già associata');
});
