/**
 * COMPONENTE PRINCIPALE DELL'APPLICAZIONE REACT
 *
 * Questo è il componente "radice" che:
 * 1. Struttura l'intera applicazione
 * 2. Gestisce la navigazione tra le diverse sezioni
 * 3. Fornisce il layout principale con header e contenuto
 * 4. Coordina tutti i componenti figlio
 */

import React, { useState, useEffect, useCallback } from 'react';
import Calendar from './components/Calendar';
import CollaboratorManager from './components/CollaboratorManager';
import AllieviManager from './components/AllieviManager';
import ProjectManager from './components/ProjectManager';
import AziendeClientiManager from './components/AziendeClientiManager';
import CatalogoManager from './components/CatalogoManager';
import ListiniManager from './components/ListiniManager';
import PreventiviManager from './components/PreventiviManager';
import OrdiniManager from './components/OrdiniManager';
import Dashboard from './components/Dashboard';
import HomeCockpit from './components/HomeCockpit';
import PortaleAllievi from './components/PortaleAllievi';
import ImplementingEntitiesList from './components/ImplementingEntitiesList';
import TimesheetReport from './components/TimesheetReport';
import TimesheetPDF from './components/TimesheetPDF';
import DocumentiMancanti from './components/DocumentiMancanti';
import ContractTemplatesManager from './components/ContractTemplatesManager';
import AgentsManager from './components/AgentsManager';
import AgentsDashboard from './components/AgentsDashboard';
import AgentSuggestionsReview from './components/AgentSuggestionsReview';
import ResourceArchive from './components/ResourceArchive';
import ArchivioChiedi from './components/ArchivioChiedi';
import ResetPasswordPage, { ForgotPasswordForm } from './components/PasswordRecovery';
import UserManagement from './components/UserManagement';
import AreaPersonale from './components/AreaPersonale';
import apiService, { healthCheck } from './services/apiService';
import { http, ensureValidAccessToken } from './lib/http';
import { formatApiError } from './lib/errors';
import {
  ACCESS_PROFILES,
  canAccessSection,
  getRoleExperience,
  profileAcceptsRole,
} from './auth/permissions';
import SECTION_CONFIG from './navigation/sections.json';
import './App.scss';

const getSectionFromPath = (pathname) => {
  if (pathname.startsWith('/agents/dashboard')) {
    return 'agents-dashboard';
  }
  if (pathname.startsWith('/agents/review')) {
    return 'agents-review';
  }
  if (pathname.startsWith('/agents')) {
    return 'agents';
  }
  if (pathname.startsWith('/documenti-mancanti')) {
    return 'documenti-mancanti';
  }
  if (pathname.startsWith('/archivio-chiedi')) {
    return 'archivio-chiedi';
  }
  if (pathname.startsWith('/resources')) {
    return 'resources';
  }
  if (pathname.startsWith('/projects')) {
    return 'projects';
  }
  return null;
};

const getPathForSection = (sectionId) => {
  if (sectionId === 'agents-dashboard') {
    return '/agents/dashboard';
  }
  if (sectionId === 'agents-review') {
    return '/agents/review';
  }
  if (sectionId === 'agents') {
    return '/agents';
  }
  if (sectionId === 'documenti-mancanti') {
    return '/documenti-mancanti';
  }
  if (sectionId === 'archivio-chiedi') {
    return '/archivio-chiedi';
  }
  if (sectionId === 'resources') {
    return '/resources';
  }
  if (sectionId === 'projects') {
    return '/projects';
  }
  return '/';
};

const FILTER_QUERY_KEYS = {
  status: 'status',
  runStatus: 'run_status',
  suggestionId: 'suggestion_id',
  documentId: 'document_id',
  collaboratorId: 'collaborator_id',
  projectId: 'project_id',
  focus: 'focus',
  avvisoId: 'avviso_id',
};

const getFiltersFromLocation = () => {
  const params = new URLSearchParams(window.location.search);
  return Object.entries(FILTER_QUERY_KEYS).reduce((filters, [filterKey, queryKey]) => {
    const value = params.get(queryKey);
    if (value) filters[filterKey] = value;
    return filters;
  }, {});
};

const getPathWithFilters = (section, filters = {}) => {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      params.set(FILTER_QUERY_KEYS[key] || key, String(value));
    }
  });
  const query = params.toString();
  return `${getPathForSection(section)}${query ? `?${query}` : ''}`;
};

/**
 * COMPONENTE PRINCIPALE APP
 */
function App() {

  // ==========================================
  // STATE MANAGEMENT
  // ==========================================

  // Gestisce quale sezione dell'app è attualmente attiva
  const [activeSection, setActiveSection] = useState('calendar');
  const [sectionFilters, setSectionFilters] = useState({});

  // Stato di connessione con l'API backend
  const [apiStatus, setApiStatus] = useState('checking'); // checking, connected, error

  // Tentativi correnti di connessione (per la UI)
  const [retryAttempt, setRetryAttempt] = useState(0);

  const [currentUser, setCurrentUser] = useState(null);
  const [selectedProfile, setSelectedProfile] = useState('admin');
  const [credentials, setCredentials] = useState({ username: '', password: '' });
  const [authNotice, setAuthNotice] = useState('');
  const [authError, setAuthError] = useState('');
  const [isAuthenticating, setIsAuthenticating] = useState(false);
  const [showForgotPassword, setShowForgotPassword] = useState(false);
  const [, setPublicRouteRevision] = useState(0);

  // Costruisce la nav raggruppata: array di { groupLabel, sections[] }
  const buildNavGroups = (sections) => {
    const groups = [];
    let current = null;
    for (const section of sections) {
      if (section.group !== null) {
        // Apri nuovo gruppo
        current = { label: section.group, sections: [section] };
        groups.push(current);
      } else if (current) {
        current.sections.push(section);
      } else {
        // Sezioni prima di qualsiasi gruppo (es. Dashboard)
        current = { label: null, sections: [section] };
        groups.push(current);
      }
    }
    return groups;
  };

  // ==========================================
  // VERIFICA CONNESSIONE API AL CARICAMENTO
  // ==========================================

  /**
   * Controlla se l'API backend è raggiungibile
   * Si esegue una sola volta quando l'app si carica
   */
  const restoreSession = useCallback(async () => {
    const validToken = await ensureValidAccessToken();
    if (!validToken) {
      setCurrentUser(null);
      return;
    }

    try {
      const user = await apiService.getCurrentUser();
      setCurrentUser(user);
      setActiveSection(getSectionFromPath(window.location.pathname) || getRoleExperience(user.role).homeSection);
      setSectionFilters(getFiltersFromLocation());
    } catch (error) {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      setCurrentUser(null);
    }
  }, []);

  /**
   * FUNZIONE PER VERIFICARE LA CONNESSIONE ALL'API
   * Esegue fino a 5 tentativi con backoff esponenziale (2s, 3s, 4.5s, 6.75s, ~10s)
   */
  const checkApiConnection = useCallback(async () => {
    const MAX_RETRIES = 5;
    const INITIAL_DELAY_MS = 2000;
    const BACKOFF_MULTIPLIER = 1.5;

    setApiStatus('checking');
    setRetryAttempt(0);

    for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
      try {
        await healthCheck();
        await restoreSession();
        setApiStatus('connected');
        console.log('✅ Connessione API stabilita');
        return;
      } catch (error) {
        console.warn(`⚠️ Tentativo ${attempt + 1}/${MAX_RETRIES} fallito:`, error.message);

        if (attempt < MAX_RETRIES - 1) {
          const delay = Math.round(INITIAL_DELAY_MS * Math.pow(BACKOFF_MULTIPLIER, attempt));
          setRetryAttempt(attempt + 1);
          await new Promise(resolve => setTimeout(resolve, delay));
        }
      }
    }

    setApiStatus('error');
    console.error('❌ Tutti i tentativi di connessione API falliti');
  }, [restoreSession]);

  useEffect(() => {
    if (window.location.pathname === '/portale-allievi') {
      return;
    }
    checkApiConnection();
  }, [checkApiConnection]);

  const availableSections = SECTION_CONFIG.filter((section) => {
    if (!currentUser) {
      return false;
    }
    return canAccessSection(currentUser.role, section.id);
  });

  useEffect(() => {
    if (!currentUser || availableSections.length === 0) {
      return;
    }

    const hasAccessToCurrentSection = availableSections.some((section) => section.id === activeSection);
    if (!hasAccessToCurrentSection) {
      setActiveSection(availableSections[0].id);
    }
  }, [currentUser, activeSection, availableSections]);

  const handleInputChange = (event) => {
    const { name, value } = event.target;
    setCredentials((previous) => ({ ...previous, [name]: value }));
  };

  const handleLogin = async (event) => {
    event.preventDefault();
    setIsAuthenticating(true);
    setAuthError('');

    try {
      const response = await apiService.login(credentials);
      const profile = ACCESS_PROFILES[selectedProfile];

      if (!profileAcceptsRole(profile, response.role)) {
        throw new Error(`Le credenziali inserite non corrispondono al profilo ${profile.label.toLowerCase()}.`);
      }

      localStorage.setItem('access_token', response.access_token);
      localStorage.setItem('refresh_token', response.refresh_token);
      const user = await apiService.getCurrentUser();
      setCurrentUser(user);
      setActiveSection(getSectionFromPath(window.location.pathname) || getRoleExperience(user.role).homeSection);
      setSectionFilters(getFiltersFromLocation());
      setCredentials({ username: '', password: '' });
      setAuthNotice('');
      setShowForgotPassword(false);
    } catch (error) {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      setAuthError(formatApiError(error));
    } finally {
      setIsAuthenticating(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    setCurrentUser(null);
    setCredentials({ username: '', password: '' });
    setAuthError('');
    setAuthNotice('');
    setShowForgotPassword(false);
    setActiveSection('calendar');
  };

  const handlePasswordChanged = (message) => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    setCurrentUser(null);
    setCredentials({ username: '', password: '' });
    setAuthError('');
    setAuthNotice(message || 'Password aggiornata. Accedi con la nuova password.');
    setShowForgotPassword(false);
    setActiveSection('calendar');
    window.history.replaceState({}, '', '/');
  };

  const returnToLogin = (notice = '') => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    setCurrentUser(null);
    setCredentials({ username: '', password: '' });
    setAuthError('');
    setAuthNotice(notice);
    setShowForgotPassword(false);
    window.history.replaceState({}, '', '/');
    setPublicRouteRevision((previous) => previous + 1);
  };

  // ==========================================
  // FUNZIONI DI NAVIGAZIONE
  // ==========================================

  /**
   * CAMBIA LA SEZIONE ATTIVA
   * @param {string} section - Nome della sezione da mostrare
   */
  const navigateToSection = (section, filters = {}) => {
    setActiveSection(section);
    setSectionFilters(filters);
    window.history.replaceState({}, '', getPathWithFilters(section, filters));
    console.log(`📍 Navigazione verso: ${section}`);
  };

  const navigateFromCockpit = ({ section, filters = {} }) => {
    if (canAccessSection(currentUser?.role, section)) {
      navigateToSection(section, filters);
    }
  };

  const navigateToAvvisoReview = () => {
    setActiveSection('agents-review');
    window.history.replaceState({}, '', '/agents/review?agent_type=avviso_extractor&entity_type=avviso_revisione');
  };

  // E3.3: deep-link citazione → vista avviso. LIMITE ONESTO (coerente NEW-031):
  // ResourceArchive seleziona l'avviso ma non possiede una vista per la singola
  // regola/articolo, quindi l'ancoraggio si ferma all'avviso. I riferimenti
  // (regola/articolo) restano nella citazione d'origine.
  const navigateToAvviso = (avvisoId) => {
    if (!canAccessSection(currentUser?.role, 'resources')) return;
    navigateToSection('resources', { avvisoId });
  };

  // ==========================================
  // RENDER DELLA SEZIONE ATTIVA
  // ==========================================

  /**
   * RENDERIZZA IL CONTENUTO BASATO SULLA SEZIONE ATTIVA
   */
  const renderActiveSection = () => {
    switch (activeSection) {
      case 'calendar':
        return <Calendar currentUser={currentUser} />;

      case 'collaborators':
        return <CollaboratorManager currentUser={currentUser} />;

      case 'allievi':
        return <AllieviManager currentUser={currentUser} />;

      case 'projects':
        return <ProjectManager currentUser={currentUser} initialFilters={sectionFilters} />;

      case 'entities':
        return <ImplementingEntitiesList currentUser={currentUser} />;

      case 'utenti':
        return <UserManagement currentUser={currentUser} />;

      case 'agents-dashboard':
        return <AgentsDashboard currentUser={currentUser} initialFilters={sectionFilters} />;

      case 'agents-review':
        return <AgentSuggestionsReview currentUser={currentUser} initialFilters={sectionFilters} />;

      case 'resources':
        return (
          <ResourceArchive
            currentUser={currentUser}
            onReviewSuggestions={navigateToAvvisoReview}
            initialFilters={sectionFilters}
          />
        );

      case 'archivio-chiedi':
        return <ArchivioChiedi currentUser={currentUser} onOpenAvviso={navigateToAvviso} />;

      case 'timesheet':
        return <TimesheetView currentUser={currentUser} />;

      case 'documenti-mancanti':
        return <DocumentiMancanti currentUser={currentUser} initialFilters={sectionFilters} />;

      case 'templates':
        return <ContractTemplatesManager />;

      case 'agents':
        return <AgentsManager currentUser={currentUser} />;

      case 'home':
        return <HomeCockpit currentUser={currentUser} onNavigate={navigateFromCockpit} />;
      case 'dashboard':
        return <Dashboard currentUser={currentUser} />;

      case 'aziende-clienti':
        return <AziendeClientiManager currentUser={currentUser} />;

      case 'catalogo':
        return <CatalogoManager currentUser={currentUser} />;

      case 'listini':
        return <ListiniManager currentUser={currentUser} />;

      case 'preventivi':
        return <PreventiviManager currentUser={currentUser} />;

      case 'ordini':
        return <OrdiniManager currentUser={currentUser} />;

      default:
        return <Calendar />;
    }
  };

  const renderLoginPage = () => {
    const selectedProfileData = ACCESS_PROFILES[selectedProfile];

    return (
      <div className="login-shell">
        <section className="login-hero">
          <div className="login-hero-badge">Gestionale Collaboratori</div>
          <h1>Accesso al gestionale</h1>
          <p>
            Accedi dalla home page con il tuo profilo per entrare nel sistema.
            Sono previsti tre accessi: amministratore, operatore e consultazione.
          </p>
          <div className="profile-selector">
            {Object.values(ACCESS_PROFILES).map((profile) => (
              <button
                key={profile.id}
                type="button"
                className={`profile-card ${selectedProfile === profile.id ? 'active' : ''}`}
                onClick={() => {
                  setSelectedProfile(profile.id);
                  setAuthError('');
                }}
              >
                <span className="profile-title">{profile.label}</span>
                <span className="profile-description">{profile.description}</span>
              </button>
            ))}
          </div>
        </section>

        <section className="login-panel">
          {showForgotPassword ? (
            <ForgotPasswordForm onBack={() => setShowForgotPassword(false)} />
          ) : (
            <>
              <div className="login-panel-header">
                <span className="login-panel-eyebrow">Pagina di accesso</span>
                <h2>{selectedProfileData.label}</h2>
                <p>Inserisci username e password per entrare nel gestionale.</p>
              </div>

              <form className="login-form" onSubmit={handleLogin}>
                <label className="login-field">
                  <span>Username</span>
                  <input
                    type="text"
                    name="username"
                    value={credentials.username}
                    onChange={handleInputChange}
                    placeholder="Inserisci lo username"
                    autoComplete="username"
                    required
                  />
                </label>

                <label className="login-field">
                  <span>Password</span>
                  <input
                    type="password"
                    name="password"
                    value={credentials.password}
                    onChange={handleInputChange}
                    placeholder="Inserisci la password"
                    autoComplete="current-password"
                    required
                  />
                </label>

                {authError ? <div className="login-error">{authError}</div> : null}
                {authNotice ? <div className="login-notice" role="status">{authNotice}</div> : null}

                <button type="submit" className="login-submit" disabled={isAuthenticating}>
                  {isAuthenticating ? 'Accesso in corso...' : `Accedi come ${selectedProfileData.label}`}
                </button>
                <button
                  type="button"
                  className="login-link-button"
                  onClick={() => {
                    setAuthError('');
                    setAuthNotice('');
                    setShowForgotPassword(true);
                  }}
                >
                  Password dimenticata?
                </button>
              </form>

              <div className="login-help">
                <strong>Profili disponibili ora:</strong>
                <span>Amministratore, Operatore e Consultazione.</span>
              </div>
            </>
          )}
        </section>
      </div>
    );
  };

  // ==========================================
  // RENDER PRINCIPALE
  // ==========================================

  // Route pubblica: il magic token è l'unica autenticazione del portale.
  // Deve precedere health-check, login ERP e qualsiasi route guard gestionale.
  const isPortaleAllievi = window.location.pathname === '/portale-allievi';
  if (isPortaleAllievi) {
    return <PortaleAllievi />;
  }

  const isResetPassword = window.location.pathname === '/reset-password';
  if (isResetPassword) {
    return (
      <ResetPasswordPage
        onComplete={(message) => returnToLogin(message)}
        onBack={() => returnToLogin('')}
      />
    );
  }

  // Se stiamo ancora controllando la connessione API
  if (apiStatus === 'checking') {
    return (
      <div className="app">
        <div className="loading-screen">
          <div className="loading-spinner"></div>
          <h2>Connessione al sistema...</h2>
          {retryAttempt === 0 ? (
            <p>Verifica della connessione con il backend in corso...</p>
          ) : (
            <p>Nuovo tentativo {retryAttempt}/5 in corso...</p>
          )}
        </div>
      </div>
    );
  }

  // Se c'è un errore di connessione API
  if (apiStatus === 'error') {
    return (
      <div className="app">
        <div className="error-screen">
          <div className="error-icon">⚠️</div>
          <h2>Errore di Connessione</h2>
          <p>
            Non riesco a connettermi al backend dell'applicazione.
            <br />
            Assicurati che il server sia avviato e riprova.
          </p>
          <div className="error-details">
            <p><strong>Possibili cause:</strong></p>
            <ul>
              <li>Il server backend non è stato avviato</li>
              <li>Problemi di connessione di rete</li>
              <li>Il database non è accessibile</li>
            </ul>
            <p><strong>Come risolvere:</strong></p>
            <ul>
              <li>Esegui <code>docker-compose up</code> per avviare tutti i servizi</li>
              <li>Verifica che il backend sia in ascolto sulla porta 8000</li>
              <li>Controlla i log di Docker per eventuali errori</li>
            </ul>
          </div>
          <button
            onClick={checkApiConnection}
            className="retry-button"
          >
            🔄 Riprova Connessione
          </button>
        </div>
      </div>
    );
  }

  // Render principale quando tutto funziona
  if (!currentUser) {
    return (
      <div className="app login-app">
        {renderLoginPage()}
      </div>
    );
  }

  const currentSection = availableSections.find((section) => section.id === activeSection) || availableSections[0];
  const navGroups = buildNavGroups(availableSections.filter((section) => !section.hidden));

  return (
    <div className="app">
      {/* HEADER DELL'APPLICAZIONE */}
      <header className="app-header">
        <div className="header-brand">
          <div>
            <h1>Gestionale</h1>
            <p>Collaboratori · Progetti · Contratti</p>
          </div>
          <div className="header-right">
            <div className="api-status">
              <span className={`status-dot status-${apiStatus}`} />
              <span className="status-text">
                {apiStatus === 'connected' ? 'Online' : 'Offline'}
              </span>
            </div>
            <div className="header-user">
              <AreaPersonale
                currentUser={currentUser}
                onUserUpdated={setCurrentUser}
                onPasswordChanged={handlePasswordChanged}
              />
              <button type="button" className="logout-button" onClick={handleLogout}>
                Esci
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* BARRA DI NAVIGAZIONE RAGGRUPPATA */}
      <nav className="app-navigation">
        <div className="nav-container">
          <div className="nav-menu">
            {navGroups.map((group, gi) => (
              <div key={gi} className="nav-group">
                {group.label && (
                  <span className="nav-group-label">{group.label}</span>
                )}
                {group.sections.map((section) => (
                  <button
                    key={section.id}
                    data-section-id={section.id}
                    className={`nav-button ${activeSection === section.id ? 'active' : ''}`}
                    onClick={() => navigateToSection(section.id)}
                    title={section.title}
                  >
                    {section.icon} {section.label}
                  </button>
                ))}
              </div>
            ))}
          </div>
        </div>
      </nav>

      {/* CONTENUTO PRINCIPALE */}
      <main className="app-main" data-active-section={activeSection}>
        <div className="content-container">
          {/* TITOLO SEZIONE ATTIVA */}
          <div className="breadcrumb">
            <span className="breadcrumb-current">
              {currentSection?.breadcrumb}
            </span>
            {currentSection?.title && (
              <span className="breadcrumb-subtitle">{currentSection.title}</span>
            )}
          </div>

          {/* CONTENUTO DELLA SEZIONE ATTIVA */}
          <div className="section-content">
            {renderActiveSection()}
          </div>
        </div>
      </main>

      {/* FOOTER DELL'APPLICAZIONE */}
      <footer className="app-footer">
        <div className="footer-content">
          <p>
            © 2024 Gestionale Collaboratori e Progetti
          </p>
        </div>
      </footer>
    </div>
  );
}

const TimesheetView = ({ currentUser }) => {
  const [activeTab, setActiveTab] = React.useState('report');
  const [selectedProjectId, setSelectedProjectId] = React.useState('');

  return (
    <div>
      <div style={{ display: 'flex', gap: '8px', padding: '0 0 1rem 0', borderBottom: '0.5px solid var(--color-border-tertiary)', marginBottom: '1rem' }}>
        <button
          onClick={() => setActiveTab('report')}
          style={{
            padding: '8px 16px',
            fontSize: '13px',
            cursor: 'pointer',
            borderRadius: '6px',
            border: '0.5px solid var(--color-border-secondary)',
            background: activeTab === 'report' ? '#2c3e50' : 'var(--color-background-primary)',
            color: activeTab === 'report' ? 'white' : 'var(--color-text-primary)',
          }}
        >
          Report Ore
        </button>
        <button
          onClick={() => setActiveTab('pdf')}
          style={{
            padding: '8px 16px',
            fontSize: '13px',
            cursor: 'pointer',
            borderRadius: '6px',
            border: '0.5px solid var(--color-border-secondary)',
            background: activeTab === 'pdf' ? '#2c3e50' : 'var(--color-background-primary)',
            color: activeTab === 'pdf' ? 'white' : 'var(--color-text-primary)',
          }}
        >
          Genera PDF
        </button>
      </div>

      {activeTab === 'report' && <TimesheetReport currentUser={currentUser} />}

      {activeTab === 'pdf' && (
        <div>
          <div style={{ marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '12px' }}>
            <label style={{ fontSize: '13px', color: 'var(--color-text-secondary)', whiteSpace: 'nowrap' }}>
              Seleziona progetto:
            </label>
            <ProjectSelect onSelect={setSelectedProjectId} selectedId={selectedProjectId} />
          </div>
          {selectedProjectId
            ? <TimesheetPDF projectId={selectedProjectId} />
            : <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--color-text-secondary)', fontSize: '14px' }}>
                Seleziona un progetto per vedere i timesheet dei collaboratori
              </div>
          }
        </div>
      )}
    </div>
  );
};

const ProjectSelect = ({ onSelect, selectedId }) => {
  const [projects, setProjects] = React.useState([]);
  React.useEffect(() => {
    http.get('/projects/', { params: { limit: 100 } })
      .then(r => setProjects(Array.isArray(r.data) ? r.data : (r.data.items || [])))
      .catch(() => {});
  }, []);

  return (
    <select
      value={selectedId}
      onChange={e => onSelect(e.target.value)}
      style={{ padding: '8px 12px', fontSize: '13px', borderRadius: '6px', border: '0.5px solid var(--color-border-secondary)', minWidth: '200px' }}
    >
      <option value="">— Scegli progetto —</option>
      {projects.map(p => (
        <option key={p.id} value={p.id}>{p.name}</option>
      ))}
    </select>
  );
};

export default App;
