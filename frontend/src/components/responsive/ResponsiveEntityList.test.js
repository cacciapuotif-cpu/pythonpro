import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import ResponsiveEntityList from './ResponsiveEntityList';

const ITEMS = [
  { id: 1, name: 'Primo' },
  { id: 2, name: 'Secondo' },
];

const setLayout = (matches) => {
  document.documentElement.style.setProperty('--breakpoint-mobile-max', '48rem');
  window.matchMedia = jest.fn().mockReturnValue({
    matches,
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
  });
};

test('usa la stessa collezione per tabella desktop e card mobile', () => {
  setLayout(false);
  const desktop = render(
    <ResponsiveEntityList
      listId="prove"
      items={ITEMS}
      entityLabel="prove"
      renderDesktop={(items) => (
        <table>
          <tbody>
            {items.map((item) => <tr key={item.id}><td>{item.name}</td></tr>)}
          </tbody>
        </table>
      )}
      renderCard={(item) => <article>{item.name}</article>}
    />,
  );

  expect(desktop.container.querySelectorAll('[data-responsive-layout="desktop"] tr')).toHaveLength(2);
  expect(desktop.container.querySelector('[data-responsive-layout="mobile"]')).not.toBeInTheDocument();
  desktop.unmount();

  setLayout(true);
  const mobile = render(
    <ResponsiveEntityList
      listId="prove"
      items={ITEMS}
      entityLabel="prove"
      renderDesktop={jest.fn()}
      renderCard={(item) => <article>{item.name}</article>}
    />,
  );
  expect(mobile.container.querySelectorAll('[data-responsive-layout="mobile"] > li')).toHaveLength(2);
  expect(mobile.container.querySelector('[data-responsive-list="prove"]')).toBeInTheDocument();
  expect(mobile.container.querySelector('[data-responsive-layout="desktop"]')).not.toBeInTheDocument();
  expect(screen.getByText('Primo')).toBeInTheDocument();
});

test('lo stato vuoto non monta rese duplicate', () => {
  const { container } = render(
    <ResponsiveEntityList
      listId="prove"
      items={[]}
      emptyMessage="Nessun risultato"
      renderDesktop={jest.fn()}
      renderCard={jest.fn()}
    />,
  );

  expect(screen.getByRole('status')).toHaveTextContent('Nessun risultato');
  expect(container.querySelector('[data-responsive-list]')).not.toBeInTheDocument();
});
