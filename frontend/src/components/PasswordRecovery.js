import React, { useEffect, useState } from 'react';

import { formatApiError } from '../lib/errors';
import apiService from '../services/apiService';

const EMPTY_RESET = {
  new_password: '',
  confirm_password: '',
};

export const ForgotPasswordForm = ({ onBack }) => {
  const [email, setEmail] = useState('');
  const [status, setStatus] = useState({ sending: false, error: '', success: '' });

  const submit = async (event) => {
    event.preventDefault();
    setStatus({ sending: true, error: '', success: '' });
    try {
      const response = await apiService.requestPasswordReset(email.trim());
      setStatus({ sending: false, error: '', success: response.message });
    } catch (error) {
      setStatus({ sending: false, error: formatApiError(error), success: '' });
    }
  };

  return (
    <form className="login-form password-recovery-form" onSubmit={submit}>
      <div className="login-panel-header">
        <span className="login-panel-eyebrow">Recupero account</span>
        <h2>Password dimenticata</h2>
        <p>Inserisci l’email associata all’account. Riceverai un link valido per 30 minuti.</p>
      </div>

      <label className="login-field">
        <span>Email</span>
        <input
          type="email"
          value={email}
          onChange={(event) => {
            setEmail(event.target.value);
            setStatus((previous) => ({ ...previous, error: '', success: '' }));
          }}
          autoComplete="email"
          maxLength={100}
          required
        />
      </label>

      {status.error && <div className="login-error" role="alert">{status.error}</div>}
      {status.success && <div className="login-notice" role="status">{status.success}</div>}

      <button type="submit" className="login-submit" disabled={status.sending}>
        {status.sending ? 'Invio in corso...' : 'Invia link di recupero'}
      </button>
      <button type="button" className="login-link-button" onClick={onBack}>
        Torna all’accesso
      </button>
    </form>
  );
};

const ResetPasswordPage = ({ onComplete, onBack }) => {
  const [token] = useState(() => (
    new URLSearchParams(window.location.hash.replace(/^#/, '')).get('token') || ''
  ));
  const [passwords, setPasswords] = useState(EMPTY_RESET);
  const [status, setStatus] = useState({ saving: false, error: '' });

  useEffect(() => {
    if (window.location.hash) {
      window.history.replaceState(window.history.state, '', '/reset-password');
    }
  }, []);

  const updateField = (event) => {
    const { name, value } = event.target;
    setPasswords((previous) => ({ ...previous, [name]: value }));
    setStatus((previous) => ({ ...previous, error: '' }));
  };

  const submit = async (event) => {
    event.preventDefault();
    if (!token) {
      setStatus({ saving: false, error: 'Il link di recupero non contiene un token valido.' });
      return;
    }
    if (passwords.new_password !== passwords.confirm_password) {
      setStatus({ saving: false, error: 'La conferma non coincide con la nuova password.' });
      return;
    }
    setStatus({ saving: true, error: '' });
    try {
      const response = await apiService.resetPassword({ token, ...passwords });
      setPasswords(EMPTY_RESET);
      onComplete?.(response.message);
    } catch (error) {
      setStatus({ saving: false, error: formatApiError(error) });
    }
  };

  return (
    <div className="login-shell password-reset-shell">
      <section className="login-hero">
        <div className="login-hero-badge">Gestionale Collaboratori</div>
        <h1>Reimposta la password</h1>
        <p>Il link è personale, scade dopo 30 minuti e può essere usato una sola volta.</p>
      </section>

      <section className="login-panel">
        <form className="login-form" onSubmit={submit}>
          <div className="login-panel-header">
            <span className="login-panel-eyebrow">Recupero account</span>
            <h2>Nuova password</h2>
            <p>Scegli una password diversa e robusta.</p>
          </div>

          <label className="login-field">
            <span>Nuova password</span>
            <input
              type="password"
              name="new_password"
              value={passwords.new_password}
              onChange={updateField}
              autoComplete="new-password"
              minLength={12}
              required
              aria-describedby="reset-password-rules"
            />
            <small id="reset-password-rules">
              Almeno 12 caratteri, con maiuscola, minuscola, numero e simbolo.
            </small>
          </label>

          <label className="login-field">
            <span>Conferma nuova password</span>
            <input
              type="password"
              name="confirm_password"
              value={passwords.confirm_password}
              onChange={updateField}
              autoComplete="new-password"
              minLength={12}
              required
            />
          </label>

          {status.error && <div className="login-error" role="alert">{status.error}</div>}

          <button type="submit" className="login-submit" disabled={status.saving || !token}>
            {status.saving ? 'Reimpostazione...' : 'Reimposta password'}
          </button>
          <button type="button" className="login-link-button" onClick={onBack}>
            Torna all’accesso
          </button>
        </form>
      </section>
    </div>
  );
};

export default ResetPasswordPage;
