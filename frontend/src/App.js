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
import ProjectManager from './components/ProjectManager';
import AziendeClientiManager from './components/AziendeClientiManager';
import CatalogoManager from './components/CatalogoManager';
import ListiniManager from './components/ListiniManager';
import PreventiviManager from './components/PreventiviManager';
import OrdiniManager from './components/OrdiniManager';
import Dashboard from './components/Dashboard';
import ImplementingEntitiesList from './components/ImplementingEntitiesList';
import TimesheetReport from './components/TimesheetReport';
import PianiFinanziariHub from './components/PianiFinanziariHub';
import DocumentiMancanti from './components/DocumentiMancanti';
import ContractTemplatesManager from './components/ContractTemplatesManager';
import AgentsManager from './components/AgentsManager';
import AgentsDashboard from './components/AgentsDashboard';
import AgentSuggestionsReview from './components/AgentSuggestionsReview';
import apiService, { healthCheck } from './services/apiService';
import './App.css';

const ACCESS_PROFILES = {
  admin: {
    id: 'admin',
    label: 'Amministratore',
    description: 'Gestione completa del gestionale, configurazioni e controllo operativo.',
    expectedRoles: ['admin'],
  },
  operator: {
    id: 'operator',
    label: 'Operatore',
    description: 'Accesso operativo alle funzioni quotidiane del gestionale.',
    expectedRoles: ['user', 'manager'],
  },
};

const ROLE_EXPERIENCE = {
  admin: {
    label: 'Amministratore',
    homeSection: 'dashboard',
  },
  manager: {
    label: 'Operatore',
    homeSection: 'collaborators',
  },
  user: {
    label: 'Operatore',
    homeSection: 'collaborators',
  },
};

// group: raggruppa le voci nella nav — null = nessun separatore
const SECTION_CONFIG = [
  { id: 'dashboard',         label: 'Dashboard',      icon: '📊', group: null,           title: 'Statistiche e report',               breadcrumb: '📊 Dashboard',            roles: ['admin', 'user', 'manager'] },
  { id: 'calendar',          label: 'Calendario',     icon: '📅', group: 'Attività',     title: 'Presenze sul calendario',            breadcrumb: '📅 Calendario Presenze',   roles: ['admin', 'user', 'manager'] },
  { id: 'timesheet',         label: 'Timesheet',      icon: '⏱️', group: null,           title: 'Timesheet delle ore lavorate',       breadcrumb: '⏱️ Timesheet',             roles: ['admin', 'user', 'manager'] },
  { id: 'documenti-mancanti', label: 'Documenti',     icon: '📑', group: 'Reportistica', title: 'Documenti mancanti o in scadenza',    breadcrumb: '📑 Documenti Mancanti',    roles: ['admin', 'user', 'manager'] },
  { id: 'collaborators',     label: 'Collaboratori',  icon: '👥', group: 'Persone',      title: 'Gestione collaboratori',             breadcrumb: '👥 Collaboratori',         roles: ['admin', 'user', 'manager'] },
  { id: 'projects',          label: 'Progetti',       icon: '📁', group: null,           title: 'Progetti formativi',                 breadcrumb: '📁 Progetti',              roles: ['admin', 'user', 'manager'] },
  { id: 'aziende-clienti',   label: 'Aziende',        icon: '🏭', group: 'Commerciale',  title: 'Aziende clienti',                    breadcrumb: '🏭 Aziende Clienti',       roles: ['admin', 'user', 'manager'] },
  { id: 'catalogo',          label: 'Catalogo',       icon: '📦', group: null,           title: 'Catalogo prodotti e servizi',        breadcrumb: '📦 Catalogo',              roles: ['admin', 'user', 'manager'] },
  { id: 'listini',           label: 'Listini',        icon: '💰', group: null,           title: 'Listini prezzi',                     breadcrumb: '💰 Listini',               roles: ['admin', 'user', 'manager'] },
  { id: 'preventivi',        label: 'Preventivi',     icon: '📝', group: null,           title: 'Preventivi commerciali',             breadcrumb: '📝 Preventivi',            roles: ['admin', 'user', 'manager'] },
  { id: 'ordini',            label: 'Ordini',         icon: '🛒', group: null,           title: 'Gestione ordini',                    breadcrumb: '🛒 Ordini',                roles: ['admin', 'user', 'manager'] },
  { id: 'entities',          label: 'Enti Attuatori', icon: '🏢', group: 'Config',       title: 'Enti attuatori',                     breadcrumb: '🏢 Enti Attuatori',        roles: ['admin'] },
  { id: 'piani-finanziari',  label: 'Piani Finanziari', icon: '🧮', group: null,         title: 'Piani finanziari per progetto',      breadcrumb: '🧮 Piani Finanziari',      roles: ['admin'] },
  { id: 'agents-dashboard',  label: 'Agents Dashboard', icon: '📡', group: null,         title: 'Panoramica sistema agenti',          breadcrumb: '📡 Agents Dashboard',      roles: ['admin'] },
  { id: 'agents',            label: 'Agenti',         icon: '🤖', group: null,           title: 'Agenti operativi e revisioni AI',    breadcrumb: '🤖 Agenti Operativi',      roles: ['admin'] },
  { id: 'templates',         label: 'Template',       icon: '📋', group: null,           title: 'Template documentali',               breadcrumb: '📋 Template',              roles: ['admin'] },
];

const getSectionFromPath = (pathname) => {
  if (pathname.startsWith('/agents/dashboard')) {
    return 'agents-dashboard';
  }
  if (pathname.startsWith('/agents/review')) {
    return 'agents-review';
  }
  if (pathname.startsWith('/piani-finanziari') || pathname.startsWith('/piani-fondimpresa')) {
    return 'piani-finanziari';
  }
  if (pathname.startsWith('/agents')) {
    return 'agents';
  }
  if (pathname.startsWith('/documenti-mancanti')) {
    return 'documenti-mancanti';
  }
  return null;
};

const getPathForSection = (sectionId) => {
  if (sectionId === 'piani-finanziari') {
    return '/piani-finanziari';
  }
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
  return '/';
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

  // Stato di connessione con l'API backend
  const [apiStatus, setApiStatus] = useState('checking'); // checking, connected, error

  // Tentativi correnti di connessione (per la UI)
  const [retryAttempt, setRetryAttempt] = useState(0);

  const [currentUser, setCurrentUser] = useState(null);
  const [selectedProfile, setSelectedProfile] = useState('admin');
  const [credentials, setCredentials] = useState({ username: '', password: '' });
  const [authError, setAuthError] = useState('');
  const [isAuthenticating, setIsAuthenticating] = useState(false);

  const getRoleExperience = (role) => ROLE_EXPERIENCE[role] || ROLE_EXPERIENCE.user;
  const getRoleLabel = (role) => getRoleExperience(role).label;

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
    const existingToken = localStorage.getItem('access_token');
    if (!existingToken) {
      setCurrentUser(null);
      return;
    }

    try {
      const user = await apiService.getCurrentUser();
      setCurrentUser(user);
      setActiveSection(getSectionFromPath(window.location.pathname) || getRoleExperience(user.role).homeSection);
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
    checkApiConnection();
  }, [checkApiConnection]);

  const availableSections = SECTION_CONFIG.filter((section) => {
    if (!currentUser) {
      return false;
    }
    return section.roles.includes(currentUser.role);
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

      if (!profile.expectedRoles.includes(response.role)) {
        throw new Error(`Le credenziali inserite non corrispondono al profilo ${profile.label.toLowerCase()}.`);
      }

      localStorage.setItem('access_token', response.access_token);
      localStorage.setItem('refresh_token', response.refresh_token);
      const user = await apiService.getCurrentUser();
      setCurrentUser(user);
      setActiveSection(getSectionFromPath(window.location.pathname) || getRoleExperience(user.role).homeSection);
      setCredentials({ username: '', password: '' });
    } catch (error) {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      setAuthError(error.response?.data?.detail || error.message || 'Accesso non riuscito.');
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
    setActiveSection('calendar');
  };

  // ==========================================
  // FUNZIONI DI NAVIGAZIONE
  // ==========================================

  /**
   * CAMBIA LA SEZIONE ATTIVA
   * @param {string} section - Nome della sezione da mostrare
   */
  const navigateToSection = (section) => {
    setActiveSection(section);
    window.history.replaceState({}, '', getPathForSection(section));
    console.log(`📍 Navigazione verso: ${section}`);
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
        return <Calendar />;

      case 'collaborators':
        return <CollaboratorManager currentUser={currentUser} />;

      case 'projects':
        return <ProjectManager currentUser={currentUser} />;

      case 'entities':
        return <ImplementingEntitiesList currentUser={currentUser} />;

      case 'piani-finanziari':
        return <PianiFinanziariHub />;

      case 'agents-dashboard':
        return <AgentsDashboard currentUser={currentUser} />;

      case 'agents-review':
        return <AgentSuggestionsReview currentUser={currentUser} />;

      case 'timesheet':
        return <TimesheetReport />;

      case 'documenti-mancanti':
        return <DocumentiMancanti />;

      case 'templates':
        return <ContractTemplatesManager />;

      case 'agents':
        return <AgentsManager currentUser={currentUser} />;

      case 'dashboard':
        return <Dashboard currentUser={currentUser} />;

      case 'aziende-clienti':
        return <AziendeClientiManager currentUser={currentUser} />;

      case 'catalogo':
        return <CatalogoManager />;

      case 'listini':
        return <ListiniManager />;

      case 'preventivi':
        return <PreventiviManager />;

      case 'ordini':
        return <OrdiniManager />;

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
            In questa fase sono previsti due accessi: amministratore e operatore.
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

            <button type="submit" className="login-submit" disabled={isAuthenticating}>
              {isAuthenticating ? 'Accesso in corso...' : `Accedi come ${selectedProfileData.label}`}
            </button>
          </form>

          <div className="login-help">
            <strong>Profili disponibili ora:</strong>
            <span>Amministratore e Operatore. Potremo aggiungere altri tipi di accesso dopo.</span>
          </div>
        </section>
      </div>
    );
  };

  // ==========================================
  // RENDER PRINCIPALE
  // ==========================================

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
  const navGroups = buildNavGroups(availableSections);

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
              <span className="header-user-name">{currentUser.full_name || currentUser.username}</span>
              <span className="header-user-role">{getRoleLabel(currentUser.role)}</span>
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
      <main className="app-main">
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
            <span className="footer-separator">•</span>
            <a
              href="http://localhost:8001/docs"
              target="_blank"
              rel="noopener noreferrer"
              title="Apri la documentazione API"
            >
              📚 Documentazione API
            </a>
          </p>
        </div>
      </footer>
    </div>
  );
}

export default App;
