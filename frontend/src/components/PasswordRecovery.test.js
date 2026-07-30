import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

import ResetPasswordPage, { ForgotPasswordForm } from './PasswordRecovery';
import apiService from '../services/apiService';

jest.mock('../services/apiService', () => ({
  __esModule: true,
  default: {
    requestPasswordReset: jest.fn(),
    resetPassword: jest.fn(),
  },
}));

beforeEach(() => {
  jest.clearAllMocks();
  window.history.replaceState({}, '', '/');
});

test('richiede il link mostrando sempre il messaggio generico del backend', async () => {
  apiService.requestPasswordReset.mockResolvedValue({
    status: 'accepted',
    message: 'Se l’indirizzo è associato a un account attivo, riceverai un link.',
  });
  render(<ForgotPasswordForm onBack={jest.fn()} />);

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

test('estrae il token dal fragment, lo rimuove dalla URL e reimposta la password', async () => {
  const onComplete = jest.fn();
  window.history.replaceState({}, '', '/reset-password#token=reset-token-value');
  apiService.resetPassword.mockResolvedValue({
    status: 'password_reset',
    message: 'Password reimpostata. Ora puoi accedere.',
  });

  render(<ResetPasswordPage onComplete={onComplete} onBack={jest.fn()} />);

  await waitFor(() => expect(window.location.hash).toBe(''));
  fireEvent.change(screen.getByLabelText(/^nuova password/i), {
    target: { value: 'RecoveredPassword789!' },
  });
  fireEvent.change(screen.getByLabelText(/conferma nuova password/i), {
    target: { value: 'RecoveredPassword789!' },
  });
  fireEvent.click(screen.getByRole('button', { name: /^reimposta password$/i }));

  await waitFor(() => expect(apiService.resetPassword).toHaveBeenCalledWith({
    token: 'reset-token-value',
    new_password: 'RecoveredPassword789!',
    confirm_password: 'RecoveredPassword789!',
  }));
  await waitFor(() => expect(onComplete).toHaveBeenCalledWith(
    'Password reimpostata. Ora puoi accedere.',
  ));
});

test('blocca localmente conferme diverse senza consumare il token', async () => {
  window.history.replaceState({}, '', '/reset-password#token=reset-token-value');
  render(<ResetPasswordPage onComplete={jest.fn()} onBack={jest.fn()} />);

  fireEvent.change(screen.getByLabelText(/^nuova password/i), {
    target: { value: 'RecoveredPassword789!' },
  });
  fireEvent.change(screen.getByLabelText(/conferma nuova password/i), {
    target: { value: 'DifferentPassword789!' },
  });
  fireEvent.click(screen.getByRole('button', { name: /^reimposta password$/i }));

  expect(await screen.findByRole('alert')).toHaveTextContent('La conferma non coincide');
  expect(apiService.resetPassword).not.toHaveBeenCalled();
});

test('senza token non permette di inviare il reset', () => {
  window.history.replaceState({}, '', '/reset-password');
  render(<ResetPasswordPage onComplete={jest.fn()} onBack={jest.fn()} />);

  expect(screen.getByRole('button', { name: /^reimposta password$/i })).toBeDisabled();
  expect(apiService.resetPassword).not.toHaveBeenCalled();
});

test('mostra un link scaduto restituito dal backend senza perdere il form', async () => {
  window.history.replaceState({}, '', '/reset-password#token=expired-token-value');
  apiService.resetPassword.mockRejectedValue({
    response: {
      status: 400,
      data: { detail: 'Il link non è valido, è scaduto o è già stato utilizzato' },
    },
  });
  render(<ResetPasswordPage onComplete={jest.fn()} onBack={jest.fn()} />);

  fireEvent.change(screen.getByLabelText(/^nuova password/i), {
    target: { value: 'RecoveredPassword789!' },
  });
  fireEvent.change(screen.getByLabelText(/conferma nuova password/i), {
    target: { value: 'RecoveredPassword789!' },
  });
  fireEvent.click(screen.getByRole('button', { name: /^reimposta password$/i }));

  expect(await screen.findByRole('alert')).toHaveTextContent('Il link non è valido');
  expect(screen.getByLabelText(/^nuova password/i)).toHaveValue('RecoveredPassword789!');
});
