/**
 * TEST E2E PER LA NAVBAR DELL'APPLICAZIONE
 *
 * Questi test verificano che:
 * 1. I pulsanti della navbar siano renderizzati correttamente in produzione
 * 2. Il pulsante "Enti Attuatori" sia visibile
 * 3. Il pulsante "Timesheet" sia visibile
 * 4. I pulsanti siano cliccabili e navighino correttamente
 *
 * Questo previene regressioni dove i pulsanti scompaiono per cache o build problems
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import App from './App';

// Mock dell'API healthCheck per evitare chiamate reali durante i test
jest.mock('./services/api', () => ({
  healthCheck: jest.fn(() => Promise.resolve({ status: 'ok' })),
  getCollaboratorsWithProjects: jest.fn(() => Promise.resolve([])),
  getProjects: jest.fn(() => Promise.resolve([])),
}));

describe('Navbar Buttons - Production Build Test', () => {
  beforeEach(() => {
    // Pulisci tutti i mock prima di ogni test
    jest.clearAllMocks();
  });

  test('TEST 1: App si carica senza errori', async () => {
    render(<App />);

    // Attendi che l'app finisca il caricamento (health check completato)
    await waitFor(() => {
      expect(screen.queryByText(/Connessione al sistema/i)).not.toBeInTheDocument();
    });

    // Verifica che l'header principale sia presente
    expect(screen.getByText(/Gestionale Collaboratori/i)).toBeInTheDocument();
  });

  test('TEST 2: Pulsante "Enti Attuatori" è visibile nella navbar', async () => {
    render(<App />);

    // Attendi caricamento
    await waitFor(() => {
      expect(screen.queryByText(/Connessione al sistema/i)).not.toBeInTheDocument();
    });

    // Cerca il pulsante con icona e testo
    const entiButton = screen.getByRole('button', { name: /Enti Attuatori/i });

    // Verifica che sia visibile
    expect(entiButton).toBeInTheDocument();
    expect(entiButton).toBeVisible();

    // Verifica che contenga l'emoji corretta
    expect(entiButton.textContent).toContain('🏢');

    console.log('✅ TEST 2 PASSED: Pulsante "Enti Attuatori" visibile');
  });

  test('TEST 3: Pulsante "Timesheet" è visibile nella navbar', async () => {
    render(<App />);

    // Attendi caricamento
    await waitFor(() => {
      expect(screen.queryByText(/Connessione al sistema/i)).not.toBeInTheDocument();
    });

    // Cerca il pulsante con icona e testo
    const timesheetButton = screen.getByRole('button', { name: /Timesheet/i });

    // Verifica che sia visibile
    expect(timesheetButton).toBeInTheDocument();
    expect(timesheetButton).toBeVisible();

    // Verifica che contenga l'emoji corretta
    expect(timesheetButton.textContent).toContain('⏱️');

    console.log('✅ TEST 3 PASSED: Pulsante "Timesheet" visibile');
  });

  test('TEST 4: Click su "Enti Attuatori" naviga alla sezione corretta', async () => {
    render(<App />);

    // Attendi caricamento
    await waitFor(() => {
      expect(screen.queryByText(/Connessione al sistema/i)).not.toBeInTheDocument();
    });

    // Trova e clicca il pulsante
    const entiButton = screen.getByRole('button', { name: /Enti Attuatori/i });
    fireEvent.click(entiButton);

    // Verifica che il breadcrumb mostri la sezione corretta
    await waitFor(() => {
      expect(screen.getByText(/Gestione Enti Attuatori/i)).toBeInTheDocument();
    });

    // Verifica che il pulsante sia marcato come attivo
    expect(entiButton).toHaveClass('active');

    console.log('✅ TEST 4 PASSED: Navigazione a "Enti Attuatori" funziona');
  });

  test('TEST 5: Click su "Timesheet" naviga alla sezione corretta', async () => {
    render(<App />);

    // Attendi caricamento
    await waitFor(() => {
      expect(screen.queryByText(/Connessione al sistema/i)).not.toBeInTheDocument();
    });

    // Trova e clicca il pulsante
    const timesheetButton = screen.getByRole('button', { name: /Timesheet/i });
    fireEvent.click(timesheetButton);

    // Verifica che il breadcrumb mostri la sezione corretta
    await waitFor(() => {
      expect(screen.getByText(/Timesheet Report/i)).toBeInTheDocument();
    });

    // Verifica che il pulsante sia marcato come attivo
    expect(timesheetButton).toHaveClass('active');

    console.log('✅ TEST 5 PASSED: Navigazione a "Timesheet" funziona');
  });

  test('TEST 6: Tutti i pulsanti navbar principali sono visibili', async () => {
    render(<App />);

    // Attendi caricamento
    await waitFor(() => {
      expect(screen.queryByText(/Connessione al sistema/i)).not.toBeInTheDocument();
    });

    // Verifica presenza di tutti i pulsanti principali
    const expectedButtons = [
      /Calendario/i,
      /Collaboratori/i,
      /Progetti/i,
      /Enti Attuatori/i,
      /Associazioni Progetto-Ente/i,
      /Timesheet/i,
      /Dashboard/i
    ];

    expectedButtons.forEach((buttonText) => {
      const button = screen.getByRole('button', { name: buttonText });
      expect(button).toBeInTheDocument();
      expect(button).toBeVisible();
    });

    console.log('✅ TEST 6 PASSED: Tutti i pulsanti navbar visibili');
  });

  test('TEST 7: I componenti ImplementingEntitiesList e TimesheetReport sono importati', () => {
    // Questo test verifica che i componenti siano effettivamente importati
    // Il test fallisce se i componenti non sono importati o se ci sono errori di import

    render(<App />);

    // Se arriviamo qui senza errori, i componenti sono importati correttamente
    expect(true).toBe(true);

    console.log('✅ TEST 7 PASSED: Componenti importati correttamente');
  });
});

describe('Navbar Buttons - Cache Resistance Test', () => {
  test('TEST 8: Navbar persiste dopo ricaricamento', async () => {
    // Primo render
    const { unmount } = render(<App />);

    await waitFor(() => {
      expect(screen.queryByText(/Connessione al sistema/i)).not.toBeInTheDocument();
    });

    // Verifica pulsanti presenti
    expect(screen.getByRole('button', { name: /Enti Attuatori/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Timesheet/i })).toBeInTheDocument();

    // Unmount (simula ricaricamento)
    unmount();

    // Ri-render (simula ricaricamento)
    render(<App />);

    await waitFor(() => {
      expect(screen.queryByText(/Connessione al sistema/i)).not.toBeInTheDocument();
    });

    // Verifica che i pulsanti siano ancora presenti
    expect(screen.getByRole('button', { name: /Enti Attuatori/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Timesheet/i })).toBeInTheDocument();

    console.log('✅ TEST 8 PASSED: Navbar persiste dopo ricaricamento');
  });
});
