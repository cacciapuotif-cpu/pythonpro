import React from 'react';
import { render, screen } from '@testing-library/react';
import DesktopOnlyNotice from './DesktopOnlyNotice';

describe('DesktopOnlyNotice', () => {
  test('mostra titolo e messaggio di default', () => {
    render(<DesktopOnlyNotice />);
    expect(screen.getByText('Disponibile solo da desktop')).toBeInTheDocument();
    expect(screen.getByText(/richiede schermo e strumenti desktop/)).toBeInTheDocument();
  });

  test('accetta titolo e messaggio personalizzati', () => {
    render(<DesktopOnlyNotice title="Piano finanziario" message="Apri da desktop per modificare il piano." />);
    expect(screen.getByText('Piano finanziario')).toBeInTheDocument();
    expect(screen.getByText('Apri da desktop per modificare il piano.')).toBeInTheDocument();
  });

  test('mostra il riepilogo passato come children', () => {
    render(
      <DesktopOnlyNotice>
        <span>Stato: bozza</span>
      </DesktopOnlyNotice>
    );
    expect(screen.getByText('Stato: bozza')).toBeInTheDocument();
  });

  test('non mostra il riquadro riepilogo se non ci sono children', () => {
    const { container } = render(<DesktopOnlyNotice />);
    expect(container.querySelector('.bg-gray-50')).not.toBeInTheDocument();
  });
});
