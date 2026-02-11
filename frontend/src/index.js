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
import './index.css';  // Stili globali dell'applicazione
import App from './App';  // Il componente principale
import { AppProvider } from './context/AppContext';  // Context provider stabile

// CONFIGURAZIONE DEL RENDERING
// Creiamo il root dell'applicazione React collegandolo all'elemento HTML con id="root"
const root = ReactDOM.createRoot(document.getElementById('root'));

// RENDERIZZIAMO L'APPLICAZIONE
// StrictMode è un componente di React che aiuta a identificare potenziali problemi
// durante lo sviluppo (non influisce sulla produzione)
// AppProvider fornisce il context globale con import dinamici per stabilità
root.render(
  <React.StrictMode>
    <AppProvider>
      <App />
    </AppProvider>
  </React.StrictMode>
);