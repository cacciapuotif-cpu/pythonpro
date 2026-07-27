/**
 * RADICE DELL'ALBERO APPLICATIVO
 *
 * Compone i provider globali e i componenti sempre montati.
 * index.js si limita a renderizzare questo componente, cosi' l'albero reale
 * dell'applicazione resta verificabile dai test.
 */

import React from 'react';
import App from './App';
import { AppProvider } from './context/AppContext';
import ErrorBoundary from './components/ErrorBoundary';
import NotificationSystem from './components/NotificationSystem';

const AppRoot = () => (
  <ErrorBoundary>
    <AppProvider>
      <App />
      <NotificationSystem />
    </AppProvider>
  </ErrorBoundary>
);

export default AppRoot;
