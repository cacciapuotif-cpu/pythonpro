import React, { useEffect, useMemo, useState } from 'react';

import { getRoleLabel } from '../auth/permissions';
import { formatApiError } from '../lib/errors';
import apiService from '../services/apiService';
import useDismissibleLayerHistory from '../hooks/useDismissibleLayerHistory';

const EMPTY_PASSWORDS = {
  current_password: '',
  new_password: '',
  confirm_password: '',
};

const nameParts = (user = {}) => {
  if (user.first_name || user.last_name) {
    return {
      first_name: user.first_name || '',
      last_name: user.last_name || '',
    };
  }
  const [firstName = '', ...lastNameParts] = String(user.full_name || '').trim().split(/\s+/);
  return {
    first_name: firstName,
    last_name: lastNameParts.join(' '),
  };
};

const AreaPersonale = ({ currentUser, onUserUpdated, onPasswordChanged }) => {
  const initialNames = nameParts(currentUser);
  const [open, setOpen] = useState(false);
  const [profile, setProfile] = useState({
    ...initialNames,
    email: currentUser?.email || '',
    phone: currentUser?.phone || '',
    current_password: '',
  });
  const [passwords, setPasswords] = useState(EMPTY_PASSWORDS);
  const [profileStatus, setProfileStatus] = useState({ saving: false, error: '', success: '' });
  const [passwordStatus, setPasswordStatus] = useState({ saving: false, error: '' });
  const [avatarStatus, setAvatarStatus] = useState({ saving: false, error: '' });
  const [avatarUrl, setAvatarUrl] = useState('');
  const [avatarRevision, setAvatarRevision] = useState(0);
  const closePersonalArea = useDismissibleLayerHistory({
    id: 'personal-area',
    open,
    onDismiss: () => setOpen(false),
  });

  const initials = useMemo(() => {
    const names = nameParts(currentUser);
    return `${names.first_name.charAt(0)}${names.last_name.charAt(0)}`.toUpperCase()
      || String(currentUser?.username || '?').charAt(0).toUpperCase();
  }, [currentUser]);

  useEffect(() => {
    const names = nameParts(currentUser);
    setProfile({
      ...names,
      email: currentUser?.email || '',
      phone: currentUser?.phone || '',
      current_password: '',
    });
  }, [currentUser]);

  useEffect(() => {
    let active = true;
    let objectUrl = '';
    if (!currentUser?.has_avatar) {
      setAvatarUrl('');
      return () => {};
    }
    apiService.getCurrentUserAvatar()
      .then((blob) => {
        if (!active || typeof URL.createObjectURL !== 'function') return;
        objectUrl = URL.createObjectURL(blob);
        setAvatarUrl(objectUrl);
      })
      .catch(() => {
        if (active) setAvatarUrl('');
      });
    return () => {
      active = false;
      if (objectUrl && typeof URL.revokeObjectURL === 'function') {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [currentUser?.has_avatar, avatarRevision]);

  const updateProfileField = (event) => {
    const { name, value } = event.target;
    setProfile((previous) => ({ ...previous, [name]: value }));
    setProfileStatus((previous) => ({ ...previous, error: '', success: '' }));
  };

  const updatePasswordField = (event) => {
    const { name, value } = event.target;
    setPasswords((previous) => ({ ...previous, [name]: value }));
    setPasswordStatus((previous) => ({ ...previous, error: '' }));
  };

  const saveProfile = async (event) => {
    event.preventDefault();
    setProfileStatus({ saving: true, error: '', success: '' });
    try {
      const updated = await apiService.updateCurrentUser({
        first_name: profile.first_name.trim(),
        last_name: profile.last_name.trim(),
        email: profile.email.trim(),
        phone: profile.phone.trim() || null,
        ...(profile.current_password ? { current_password: profile.current_password } : {}),
      });
      setProfileStatus({ saving: false, error: '', success: 'Informazioni aggiornate.' });
      setProfile((previous) => ({ ...previous, current_password: '' }));
      onUserUpdated?.(updated);
    } catch (error) {
      setProfileStatus({ saving: false, error: formatApiError(error), success: '' });
    }
  };

  const savePassword = async (event) => {
    event.preventDefault();
    if (passwords.new_password !== passwords.confirm_password) {
      setPasswordStatus({ saving: false, error: 'La conferma non coincide con la nuova password.' });
      return;
    }
    setPasswordStatus({ saving: true, error: '' });
    try {
      const response = await apiService.changePassword(passwords);
      setPasswords(EMPTY_PASSWORDS);
      onPasswordChanged?.(response.message);
    } catch (error) {
      setPasswordStatus({ saving: false, error: formatApiError(error) });
    }
  };

  const uploadAvatar = async (event) => {
    const [file] = event.target.files || [];
    event.target.value = '';
    if (!file) return;
    if (file.size > 2 * 1024 * 1024) {
      setAvatarStatus({ saving: false, error: 'La foto non può superare 2 MB.' });
      return;
    }
    setAvatarStatus({ saving: true, error: '' });
    try {
      const updated = await apiService.uploadCurrentUserAvatar(file);
      onUserUpdated?.(updated);
      setAvatarRevision((value) => value + 1);
      setAvatarStatus({ saving: false, error: '' });
    } catch (error) {
      setAvatarStatus({ saving: false, error: formatApiError(error) });
    }
  };

  const deleteAvatar = async () => {
    setAvatarStatus({ saving: true, error: '' });
    try {
      await apiService.deleteCurrentUserAvatar();
      setAvatarUrl('');
      onUserUpdated?.({ ...currentUser, has_avatar: false });
      setAvatarStatus({ saving: false, error: '' });
    } catch (error) {
      setAvatarStatus({ saving: false, error: formatApiError(error) });
    }
  };

  const avatar = (
    <span className="profile-avatar" aria-hidden="true">
      {avatarUrl ? <img src={avatarUrl} alt="" /> : initials}
    </span>
  );

  return (
    <div className="header-personal-area">
      <button
        type="button"
        className="header-profile-button"
        aria-expanded={open}
        onClick={() => setOpen(true)}
      >
        {avatar}
        <span>
          <strong>Area personale</strong>
          <small>{currentUser?.full_name || currentUser?.username}</small>
        </span>
      </button>

      {open && (
        <div className="personal-area-overlay" onMouseDown={closePersonalArea}>
          <section
            className="personal-area"
            role="dialog"
            aria-modal="true"
            aria-labelledby="personal-area-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="personal-area-titlebar">
              <div className="personal-area-identity">
                {avatar}
                <div>
                  <span className="personal-area-kicker">Account</span>
                  <h2 id="personal-area-title">Area personale</h2>
                  <p>{currentUser?.username} · {getRoleLabel(currentUser?.role)}</p>
                </div>
              </div>
              <button
                type="button"
                className="personal-area-close"
                onClick={closePersonalArea}
                aria-label="Chiudi area personale"
              >
                ✕
              </button>
            </div>

            <div className="personal-area-content">
              <form className="personal-area-form" onSubmit={saveProfile}>
                <div className="personal-area-heading">
                  <h3>Informazioni personali</h3>
                  <p>Puoi completare e aggiornare in autonomia il tuo profilo.</p>
                </div>

                <div className="personal-area-photo">
                  {avatar}
                  <label className="personal-area-file-button">
                    <span>{avatarStatus.saving ? 'Caricamento...' : 'Carica foto'}</span>
                    <input
                      type="file"
                      accept="image/jpeg,image/png,image/webp"
                      onChange={uploadAvatar}
                      disabled={avatarStatus.saving}
                    />
                  </label>
                  {currentUser?.has_avatar && (
                    <button type="button" className="btn-sm btn-secondary" onClick={deleteAvatar}>
                      Rimuovi
                    </button>
                  )}
                </div>
                <small>JPG, PNG o WebP; massimo 2 MB.</small>
                {avatarStatus.error && <p className="personal-area-error" role="alert">{avatarStatus.error}</p>}

                <label>
                  <span>Username</span>
                  <input value={currentUser?.username || ''} disabled />
                  <small>Assegnato automaticamente dal sistema.</small>
                </label>

                <label>
                  <span>Nome</span>
                  <input
                    name="first_name"
                    value={profile.first_name}
                    onChange={updateProfileField}
                    autoComplete="given-name"
                    maxLength={50}
                    required
                  />
                </label>

                <label>
                  <span>Cognome</span>
                  <input
                    name="last_name"
                    value={profile.last_name}
                    onChange={updateProfileField}
                    autoComplete="family-name"
                    maxLength={50}
                    required
                  />
                </label>

                <label>
                  <span>Email</span>
                  <input
                    type="email"
                    name="email"
                    value={profile.email}
                    onChange={updateProfileField}
                    autoComplete="email"
                    maxLength={100}
                    required
                  />
                </label>

                <label>
                  <span>Telefono</span>
                  <input
                    type="tel"
                    name="phone"
                    value={profile.phone}
                    onChange={updateProfileField}
                    autoComplete="tel"
                    maxLength={30}
                    placeholder="+39 333 123 4567"
                  />
                </label>

                <label>
                  <span>Password attuale per cambiare email</span>
                  <input
                    type="password"
                    name="current_password"
                    value={profile.current_password}
                    onChange={updateProfileField}
                    autoComplete="current-password"
                    maxLength={128}
                  />
                  <small>Lasciala vuota se non stai modificando l’email.</small>
                </label>

                {profileStatus.error && <p className="personal-area-error" role="alert">{profileStatus.error}</p>}
                {profileStatus.success && <p className="personal-area-success" role="status">{profileStatus.success}</p>}

                <button type="submit" disabled={profileStatus.saving}>
                  {profileStatus.saving ? 'Salvataggio...' : 'Salva informazioni'}
                </button>
              </form>

              <form className="personal-area-form personal-area-password" onSubmit={savePassword}>
                <div className="personal-area-heading">
                  <h3>Password di accesso</h3>
                  <p>Al termine dovrai accedere di nuovo su tutti i dispositivi.</p>
                </div>

                <label>
                  <span>Password attuale</span>
                  <input
                    type="password"
                    name="current_password"
                    value={passwords.current_password}
                    onChange={updatePasswordField}
                    autoComplete="current-password"
                    required
                  />
                </label>

                <label>
                  <span>Nuova password</span>
                  <input
                    type="password"
                    name="new_password"
                    value={passwords.new_password}
                    onChange={updatePasswordField}
                    autoComplete="new-password"
                    minLength={12}
                    required
                    aria-describedby="password-rules"
                  />
                  <small id="password-rules">
                    Almeno 12 caratteri, con maiuscola, minuscola, numero e simbolo.
                  </small>
                </label>

                <label>
                  <span>Conferma nuova password</span>
                  <input
                    type="password"
                    name="confirm_password"
                    value={passwords.confirm_password}
                    onChange={updatePasswordField}
                    autoComplete="new-password"
                    minLength={12}
                    required
                  />
                </label>

                {passwordStatus.error && <p className="personal-area-error" role="alert">{passwordStatus.error}</p>}

                <button type="submit" disabled={passwordStatus.saving}>
                  {passwordStatus.saving ? 'Aggiornamento...' : 'Cambia password'}
                </button>
              </form>
            </div>
          </section>
        </div>
      )}
    </div>
  );
};

export default AreaPersonale;
