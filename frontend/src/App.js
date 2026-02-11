/**
 * COMPONENTE PRINCIPALE DELL'APPLICAZIONE REACT
 *
 * Questo è il componente "radice" che:
 * 1. Struttura l'intera applicazione
 * 2. Gestisce la navigazione tra le diverse sezioni
 * 3. Fornisce il layout principale con header e contenuto
 * 4. Coordina tutti i componenti figlio
 */

import React, { useState, useEffect } from 'react';
import Calendar from './components/Calendar';
import CollaboratorManager from './components/CollaboratorManager';
import ProjectManager from './components/ProjectManager';
import Dashboard from './components/Dashboard';
import ImplementingEntitiesList from './components/ImplementingEntitiesList';
import TimesheetReport from './components/TimesheetReport';
import ProgettoMansioneEnteManager from './components/ProgettoMansioneEnteManager';
import ContractTemplatesManager from './components/ContractTemplatesManager';
import { healthCheck } from './services/apiService';
import './App.css';

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

  // ==========================================
  // VERIFICA CONNESSIONE API AL CARICAMENTO
  // ==========================================

  /**
   * Controlla se l'API backend è raggiungibile
   * Si esegue una sola volta quando l'app si carica
   */
  useEffect(() => {
    checkApiConnection();
  }, []);

  /**
   * FUNZIONE PER VERIFICARE LA CONNESSIONE ALL'API
   */
  const checkApiConnection = async () => {
    try {
      setApiStatus('checking');
      await healthCheck();  // Chiamata all'endpoint /health
      setApiStatus('connected');
      console.log('✅ Connessione API stabilita');
    } catch (error) {
      setApiStatus('error');
      console.error('❌ Errore connessione API:', error);
    }
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
        return <CollaboratorManager />;

      case 'projects':
        return <ProjectManager />;

      case 'entities':
        return <ImplementingEntitiesList />;

      case 'progetto-mansione-ente':
        return <ProgettoMansioneEnteManager />;

      case 'timesheet':
        return <TimesheetReport />;

      case 'templates':
        return <ContractTemplatesManager />;

      case 'dashboard':
        return <Dashboard />;

      default:
        return <Calendar />;
    }
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
          <p>Verifica della connessione con il backend in corso...</p>
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
  return (
    <div className="app">
      {/* HEADER DELL'APPLICAZIONE */}
      <header className="app-header">
        {/* LOGO E TITOLO */}
        <div className="header-brand">
          <h1>📋 Gestionale Collaboratori</h1>
          <p>Sistema di gestione progetti formativi e presenze</p>
        </div>

        {/* INDICATORE STATO API */}
        <div className="api-status">
          <div className={`status-indicator status-${apiStatus}`}>
            {apiStatus === 'connected' ? '🟢' : '🔴'}
          </div>
          <span className="status-text">
            {apiStatus === 'connected' ? 'Sistema Connesso' : 'Sistema Offline'}
          </span>
        </div>
      </header>

      {/* BARRA DI NAVIGAZIONE */}
      <nav className="app-navigation">
        <div className="nav-container">
          {/* MENU PRINCIPALE */}
          <div className="nav-menu">
            <button
              className={`nav-button ${activeSection === 'calendar' ? 'active' : ''}`}
              onClick={() => navigateToSection('calendar')}
              title="Visualizza e gestisci le presenze sul calendario"
            >
              📅 Calendario
            </button>

            <button
              className={`nav-button ${activeSection === 'collaborators' ? 'active' : ''}`}
              onClick={() => navigateToSection('collaborators')}
              title="Gestisci i collaboratori"
            >
              👥 Collaboratori
            </button>

            <button
              className={`nav-button ${activeSection === 'projects' ? 'active' : ''}`}
              onClick={() => navigateToSection('projects')}
              title="Gestisci i progetti formativi"
            >
              📁 Progetti
            </button>

            <button
              className={`nav-button ${activeSection === 'entities' ? 'active' : ''}`}
              onClick={() => navigateToSection('entities')}
              title="Gestisci gli enti attuatori"
            >
              🏢 Enti Attuatori
            </button>

            <button
              className={`nav-button ${activeSection === 'progetto-mansione-ente' ? 'active' : ''}`}
              onClick={() => navigateToSection('progetto-mansione-ente')}
              title="Gestisci le associazioni tra progetti, mansioni ed enti"
            >
              🔗 Associazioni Progetto-Ente
            </button>

            <button
              className={`nav-button ${activeSection === 'timesheet' ? 'active' : ''}`}
              onClick={() => navigateToSection('timesheet')}
              title="Visualizza il timesheet delle ore lavorate"
            >
              ⏱️ Timesheet
            </button>

            <button
              className={`nav-button ${activeSection === 'templates' ? 'active' : ''}`}
              onClick={() => navigateToSection('templates')}
              title="Gestisci i template per i contratti"
            >
              📋 Template Contratti
            </button>

            <button
              className={`nav-button ${activeSection === 'dashboard' ? 'active' : ''}`}
              onClick={() => navigateToSection('dashboard')}
              title="Visualizza statistiche e report"
            >
              📊 Dashboard
            </button>
          </div>
        </div>
      </nav>

      {/* CONTENUTO PRINCIPALE */}
      <main className="app-main">
        <div className="content-container">
          {/* BREADCRUMB PER ORIENTARSI */}
          <div className="breadcrumb">
            <span className="breadcrumb-home">🏠 Home</span>
            <span className="breadcrumb-separator">→</span>
            <span className="breadcrumb-current">
              {activeSection === 'calendar' && '📅 Calendario Presenze'}
              {activeSection === 'collaborators' && '👥 Gestione Collaboratori'}
              {activeSection === 'projects' && '📁 Gestione Progetti'}
              {activeSection === 'entities' && '🏢 Gestione Enti Attuatori'}
              {activeSection === 'progetto-mansione-ente' && '🔗 Associazioni Progetto-Ente'}
              {activeSection === 'timesheet' && '⏱️ Timesheet Report'}
              {activeSection === 'templates' && '📋 Template Contratti'}
              {activeSection === 'dashboard' && '📊 Dashboard e Report'}
            </span>
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