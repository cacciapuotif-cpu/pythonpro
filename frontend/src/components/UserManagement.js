import React, { useCallback, useEffect, useMemo, useState } from 'react';

import { getRoleLabel } from '../auth/permissions';
import { formatApiError } from '../lib/errors';
import apiService from '../services/apiService';
import './UserManagement.css';

const EMPTY_FORM = {
  email: '',
  first_name: '',
  last_name: '',
  role: 'operatore',
};

const ROLE_OPTIONS = [
  { value: 'admin', label: 'Amministratore' },
  { value: 'operatore', label: 'Operatore' },
  { value: 'consultazione', label: 'Consultazione' },
];

const SORT_OPTIONS = [
  { value: 'full_name', label: 'Nome' },
  { value: 'username', label: 'Username' },
  { value: 'role', label: 'Ruolo' },
];

const formatDate = (value) => {
  if (!value) return '—';
  try {
    return new Date(value).toLocaleString('it-IT');
  } catch {
    return value;
  }
};

const splitName = (user = {}) => {
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

const UserManagement = ({ currentUser }) => {
  const [users, setUsers] = useState([]);
  const [loadingUsers, setLoadingUsers] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const [showForm, setShowForm] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

  const [searchTerm, setSearchTerm] = useState('');
  const [sortBy, setSortBy] = useState('full_name');
  const [sortDir, setSortDir] = useState('asc');

  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [busyUserId, setBusyUserId] = useState(null);

  const loadUsers = useCallback(async () => {
    setLoadingUsers(true);
    try {
      const response = await apiService.listUsers();
      setUsers(response.users || []);
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setLoadingUsers(false);
    }
  }, []);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  const activeAdminCount = useMemo(
    () => users.filter((user) => user.role === 'admin' && user.is_active).length,
    [users],
  );

  const isLastActiveAdmin = useCallback(
    (user) => user.role === 'admin' && user.is_active && activeAdminCount <= 1,
    [activeAdminCount],
  );

  const filteredSortedUsers = useMemo(() => {
    const term = searchTerm.trim().toLowerCase();
    const filtered = term
      ? users.filter((user) => (
        user.username.toLowerCase().includes(term)
        || user.email.toLowerCase().includes(term)
        || (user.full_name || '').toLowerCase().includes(term)
      ))
      : users;

    const sorted = [...filtered].sort((a, b) => {
      let left;
      let right;
      if (sortBy === 'role') {
        left = getRoleLabel(a.role);
        right = getRoleLabel(b.role);
      } else {
        left = a[sortBy] || '';
        right = b[sortBy] || '';
      }
      return left.localeCompare(right, 'it', { sensitivity: 'base' });
    });

    return sortDir === 'asc' ? sorted : sorted.reverse();
  }, [users, searchTerm, sortBy, sortDir]);

  const closeForm = () => {
    setShowForm(false);
    setEditingUser(null);
    setForm(EMPTY_FORM);
  };

  const openCreateForm = () => {
    if (showForm && !editingUser) {
      closeForm();
      return;
    }
    setEditingUser(null);
    setForm(EMPTY_FORM);
    setShowForm(true);
    setError('');
    setSuccess('');
  };

  const openEditForm = (user) => {
    const names = splitName(user);
    setEditingUser(user);
    setForm({
      email: user.email,
      ...names,
      role: user.role,
    });
    setShowForm(true);
    setError('');
    setSuccess('');
  };

  const updateField = (event) => {
    const { name, value } = event.target;
    setForm((previous) => ({ ...previous, [name]: value }));
  };

  const submitForm = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError('');
    setSuccess('');
    try {
      if (editingUser) {
        const updatePayload = {
          full_name: `${form.first_name.trim()} ${form.last_name.trim()}`.trim(),
          role: form.role,
        };
        if (Number(editingUser.id) !== Number(currentUser?.id)) {
          updatePayload.email = form.email.trim();
        }
        await apiService.updateUser(editingUser.id, updatePayload);
        setSuccess(`Utente "${editingUser.username}" aggiornato.`);
      } else {
        const created = await apiService.createUser({
          email: form.email.trim(),
          first_name: form.first_name.trim(),
          last_name: form.last_name.trim(),
          role: form.role,
        });
        setSuccess(
          created.invite_queued
            ? `Utente "${created.username}" creato. Invio del link di impostazione password predisposto per ${created.email}; la consegna dipende dal servizio email.`
            : `Utente "${created.username}" creato, ma non è stato possibile predisporre il link. Riprova con "Password dimenticata?" dalla pagina di login.`,
        );
      }
      closeForm();
      loadUsers();
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setSaving(false);
    }
  };

  const toggleActive = async (user) => {
    setError('');
    setSuccess('');
    setBusyUserId(user.id);
    try {
      await apiService.updateUser(user.id, { is_active: !user.is_active });
      setSuccess(`Utente "${user.username}" ${user.is_active ? 'disattivato' : 'riattivato'}.`);
      loadUsers();
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setBusyUserId(null);
    }
  };

  const resendInvite = async (user) => {
    setError('');
    setSuccess('');
    setBusyUserId(user.id);
    try {
      const response = await apiService.resendUserInvite(user.id);
      setSuccess(
        `Invio del link di impostazione password predisposto per ${response.email}; `
        + 'la consegna dipende dal servizio email.'
      );
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setBusyUserId(null);
    }
  };

  const confirmDelete = async () => {
    if (!deleteConfirm) return;
    setError('');
    setSuccess('');
    setBusyUserId(deleteConfirm.id);
    try {
      await apiService.deleteUser(deleteConfirm.id);
      setSuccess(`Utente "${deleteConfirm.username}" eliminato.`);
      setDeleteConfirm(null);
      loadUsers();
    } catch (err) {
      setError(formatApiError(err));
      setDeleteConfirm(null);
    } finally {
      setBusyUserId(null);
    }
  };

  return (
    <div className="user-management">
      <div className="manager-header">
        <h1>Gestione Utenti</h1>
        <p>Crea account, assegna il ruolo, modifica o disattiva chi non serve più.</p>
        <div className="header-buttons">
          <button
            type="button"
            className={`add-button ${showForm && !editingUser ? 'active' : ''}`}
            onClick={openCreateForm}
          >
            {showForm && !editingUser ? '✕ Chiudi' : '+ Nuovo utente'}
          </button>
        </div>
      </div>

      {error && (
        <div className="message error-message">
          <span role="alert">{error}</span>
          <button type="button" onClick={() => setError('')} aria-label="Chiudi">✕</button>
        </div>
      )}
      {success && (
        <div className="message success-message">
          <span role="status">{success}</span>
          <button type="button" onClick={() => setSuccess('')} aria-label="Chiudi">✕</button>
        </div>
      )}

      {showForm && (
        <div className="form-section">
          <h2>{editingUser ? `Modifica "${editingUser.username}"` : 'Crea nuovo utente'}</h2>
          <p className="form-section-hint">
            {editingUser
              ? 'Lo username non è modificabile. La password resta quella già impostata dall\'utente.'
              : 'Inserisci solo i dati essenziali: lo username viene generato automaticamente e l’utente completerà telefono e foto nella propria Area personale.'}
          </p>

          <form className="user-form" onSubmit={submitForm}>
            {editingUser && (
              <label>
                <span>Username</span>
                <input value={editingUser.username} disabled />
              </label>
            )}

            <label>
              <span>Email</span>
              <input
                type="email"
                name="email"
                value={form.email}
                onChange={updateField}
                autoComplete="off"
                maxLength={100}
                required
                disabled={Boolean(editingUser) && Number(editingUser.id) === Number(currentUser?.id)}
              />
              {editingUser && Number(editingUser.id) === Number(currentUser?.id) && (
                <small>Per cambiare la tua email usa l’Area personale e conferma la password attuale.</small>
              )}
            </label>

            <label>
              <span>Nome</span>
              <input
                name="first_name"
                value={form.first_name}
                onChange={updateField}
                autoComplete="given-name"
                maxLength={50}
                required
              />
            </label>

            <label>
              <span>Cognome</span>
              <input
                name="last_name"
                value={form.last_name}
                onChange={updateField}
                autoComplete="family-name"
                maxLength={50}
                required
              />
            </label>

            <label>
              <span>Ruolo</span>
              <select
                name="role"
                value={form.role}
                onChange={updateField}
                required
                disabled={Boolean(editingUser) && isLastActiveAdmin(editingUser)}
              >
                {ROLE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
              {editingUser && isLastActiveAdmin(editingUser) && (
                <small>È l'unico amministratore attivo: il ruolo non può essere cambiato da qui.</small>
              )}
            </label>

            <div className="user-form-actions">
              <button type="button" className="cancel-button" onClick={closeForm}>
                Annulla
              </button>
              <button type="submit" className="add-button" disabled={saving}>
                {saving ? 'Salvataggio...' : editingUser ? 'Salva modifiche' : 'Crea utente'}
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="search-filters">
        <input
          type="search"
          className="search-input"
          placeholder="Cerca per username, email o nome..."
          value={searchTerm}
          onChange={(event) => setSearchTerm(event.target.value)}
        />
        <select
          className="sort-select"
          value={sortBy}
          onChange={(event) => setSortBy(event.target.value)}
          aria-label="Ordina per"
        >
          {SORT_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              Ordina per {option.label}
            </option>
          ))}
        </select>
        <button
          type="button"
          className="sort-direction-btn"
          onClick={() => setSortDir((previous) => (previous === 'asc' ? 'desc' : 'asc'))}
          title={sortDir === 'asc' ? 'Crescente' : 'Decrescente'}
        >
          {sortDir === 'asc' ? '↑' : '↓'}
        </button>
      </div>

      {loadingUsers ? (
        <div className="loading"><div className="spinner" /></div>
      ) : filteredSortedUsers.length === 0 ? (
        <div className="empty-state">
          <p>Nessun utente trovato.</p>
        </div>
      ) : (
        <div className="users-grid">
          {filteredSortedUsers.map((user) => {
            const isSelf = currentUser && user.id === currentUser.id;
            const lastAdmin = isLastActiveAdmin(user);
            const disableDangerousActions = isSelf || lastAdmin;
            const busy = busyUserId === user.id;

            return (
              <div className="user-card" key={user.id}>
                <div className="card-header">
                  <h3>
                    {user.username}
                    {isSelf && <span className="self-tag">tu</span>}
                  </h3>
                  <div className="card-actions">
                    <button
                      type="button"
                      className="edit-button"
                      onClick={() => openEditForm(user)}
                      title="Modifica"
                    >
                      ✏️
                    </button>
                    <button
                      type="button"
                      className="resend-invite-button"
                      onClick={() => resendInvite(user)}
                      disabled={busy || !user.is_active}
                      title={user.is_active ? 'Reinvia credenziali' : 'Riattiva prima di reinviare le credenziali'}
                    >
                      ✉️
                    </button>
                    <button
                      type="button"
                      className="toggle-active-button"
                      onClick={() => toggleActive(user)}
                      disabled={busy || (user.is_active && disableDangerousActions)}
                      title={
                        isSelf
                          ? 'Non puoi disattivare te stesso'
                          : lastAdmin
                            ? 'È l\'unico amministratore attivo'
                            : user.is_active ? 'Disattiva' : 'Riattiva'
                      }
                    >
                      {user.is_active ? '🔒' : '🔓'}
                    </button>
                    <button
                      type="button"
                      className="delete-button"
                      onClick={() => setDeleteConfirm(user)}
                      disabled={busy || disableDangerousActions}
                      title={
                        isSelf
                          ? 'Non puoi eliminare te stesso'
                          : lastAdmin
                            ? 'È l\'unico amministratore attivo'
                            : 'Elimina'
                      }
                    >
                      🗑️
                    </button>
                  </div>
                </div>

                <div className="card-info">
                  <div className="info-row">
                    <span className="label">Email</span>
                    <span>{user.email}</span>
                  </div>
                  <div className="info-row">
                    <span className="label">Nome</span>
                    <span>{user.full_name}</span>
                  </div>
                  <div className="info-row">
                    <span className="label">Ruolo</span>
                    <span>{getRoleLabel(user.role)}</span>
                  </div>
                  <div className="info-row">
                    <span className="label">Stato</span>
                    <span className={`status-badge ${user.is_active ? 'status-active' : 'status-cancelled'}`}>
                      {user.is_active ? 'Attivo' : 'Disattivo'}
                    </span>
                  </div>
                  <div className="info-row">
                    <span className="label">Creato il</span>
                    <span>{formatDate(user.created_at)}</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {deleteConfirm && (
        <div className="modal-overlay">
          <div className="confirm-modal">
            <h3>⚠️ Conferma eliminazione</h3>
            <p>
              Eliminare definitivamente l'utente <strong>{deleteConfirm.username}</strong>?
            </p>
            <p><strong>Questa azione non può essere annullata.</strong></p>

            <div className="modal-buttons">
              <button type="button" className="cancel-button" onClick={() => setDeleteConfirm(null)}>
                Annulla
              </button>
              <button type="button" className="delete-button" onClick={confirmDelete}>
                🗑️ Elimina
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default UserManagement;
