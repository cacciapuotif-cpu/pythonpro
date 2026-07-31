import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import ResponsiveFilters from './ResponsiveFilters';

beforeEach(() => {
  document.documentElement.style.setProperty('--breakpoint-mobile-max', '48rem');
  window.matchMedia = jest.fn().mockReturnValue({
    matches: true,
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
  });
  window.history.replaceState({}, '', '/calendar');
});

test('su mobile espone contatore, azzera e dialog accessibile', () => {
  const onReset = jest.fn();
  render(
    <ResponsiveFilters activeCount={2} onReset={onReset} title="Filtri prova">
      <label>Stato<select><option>Attivo</option></select></label>
    </ResponsiveFilters>,
  );

  fireEvent.click(screen.getByRole('button', { name: 'Filtri (2)' }));
  expect(screen.getByRole('dialog', { name: 'Filtri prova' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Chiudi filtri' })).toHaveFocus();
  fireEvent.click(screen.getByRole('button', { name: 'Azzera' }));
  expect(onReset).toHaveBeenCalledTimes(1);

  fireEvent.popState(window, { state: {} });
  expect(screen.queryByRole('dialog', { name: 'Filtri prova' })).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Filtri (2)' })).toHaveFocus();
});
