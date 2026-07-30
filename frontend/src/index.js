/**
 * PUNTO DI INGRESSO DELL'APPLICAZIONE REACT
 *
 * Questo file è il primo ad essere eseguito quando l'applicazione si avvia.
 * Si occupa di:
 * 1. Importare tutte le dipendenze necessarie
 * 2. Configurare l'ambiente React
 * 3. Renderizzare il componente App nell'elemento root del DOM
 */

import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.scss';  // Stili globali dell'applicazione
import AppRoot from './AppRoot';  // Albero applicativo (provider + componenti sempre montati)

// CONFIGURAZIONE DEL RENDERING
// Creiamo il root dell'applicazione React collegandolo all'elemento HTML con id="root"
const root = ReactDOM.createRoot(document.getElementById('root'));

// RENDERIZZIAMO L'APPLICAZIONE
// StrictMode è un componente di React che aiuta a identificare potenziali problemi
// durante lo sviluppo (non influisce sulla produzione)
// AppRoot compone ErrorBoundary, AppProvider, App e il sistema di notifiche
root.render(
  <React.StrictMode>
    <AppRoot />
  </React.StrictMode>
);
