import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import AppRoot from './AppRoot';

// L'app reale non serve: interessa solo che una notifica emessa da un
// qualunque componente dell'albero diventi visibile all'utente.
jest.mock('./App', () => {
  const ReactModule = require('react');
  const { useNotifications } = require('./hooks/useEntity');

  return function AppStub() {
    const { showError, showSuccess } = useNotifications();
    return ReactModule.createElement(
      'div',
      null,
      ReactModule.createElement(
        'button',
        { type: 'button', onClick: () => showError('Il nome del progetto è obbligatorio') },
        'emetti errore'
      ),
      ReactModule.createElement(
        'button',
        { type: 'button', onClick: () => showSuccess('Progetto aggiunto con successo!') },
        'emetti successo'
      )
    );
  };
});

test('un errore emesso da showError è visibile nell’interfaccia', () => {
  render(<AppRoot />);

  fireEvent.click(screen.getByRole('button', { name: /emetti errore/i }));

  expect(screen.getByText('Il nome del progetto è obbligatorio')).toBeInTheDocument();
});

test('un messaggio di successo emesso da showSuccess è visibile nell’interfaccia', () => {
  render(<AppRoot />);

  fireEvent.click(screen.getByRole('button', { name: /emetti successo/i }));

  expect(screen.getByText('Progetto aggiunto con successo!')).toBeInTheDocument();
});
