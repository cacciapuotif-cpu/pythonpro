import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import MobileNavigation, { getMobileDestinations } from './MobileNavigation';
import SECTION_CONFIG from '../navigation/sections.json';
import { canAccessSection, getAccessibleSectionIds } from '../auth/permissions';

const availableFor = (role) => SECTION_CONFIG.filter(
  (section) => canAccessSection(role, section.id),
);

test.each([
  ['admin', ['home', 'calendar', 'attendance', 'proposals']],
  ['operatore', ['home', 'calendar', 'attendance', 'proposals']],
  ['consultazione', ['home', 'calendar', 'people', 'archive']],
])('destinazioni primarie esatte per %s', (role, expected) => {
  expect(getMobileDestinations(role).map((item) => item.id)).toEqual(expected);
});

test.each(['admin', 'operatore', 'consultazione'])(
  'bottom + Altro coprono esattamente le sezioni RBAC di %s',
  (role) => {
    const destinations = getMobileDestinations(role);
    const primarySections = new Set(destinations.map((item) => item.section));
    const availableSections = availableFor(role);

    render(
      <MobileNavigation
        role={role}
        activeSection="home"
        availableSections={availableSections}
        menuOpen
        onOpenMenu={jest.fn()}
        onCloseMenu={jest.fn()}
        onNavigate={jest.fn()}
        onLogout={jest.fn()}
      />,
    );

    const menuSections = screen.getByRole('dialog')
      .querySelectorAll('[data-section-id]');
    const covered = new Set([
      ...primarySections,
      ...Array.from(menuSections, (item) => item.dataset.sectionId),
    ]);
    expect([...covered].sort()).toEqual(getAccessibleSectionIds(role).sort());
  },
);

test('la ricerca non espone Utenti ai ruoli senza permesso', () => {
  render(
    <MobileNavigation
      role="consultazione"
      activeSection="home"
      availableSections={availableFor('consultazione')}
      menuOpen
      onOpenMenu={jest.fn()}
      onCloseMenu={jest.fn()}
      onNavigate={jest.fn()}
      onLogout={jest.fn()}
    />,
  );

  fireEvent.change(screen.getByRole('searchbox', { name: /cerca nel menu/i }), {
    target: { value: 'Utenti' },
  });
  expect(screen.getByRole('status')).toHaveTextContent('Nessuna funzione trovata');
  expect(screen.queryByRole('link', { name: /utenti/i })).not.toBeInTheDocument();
});

test('Escape chiude il dialog e il focus resta confinato', () => {
  const onCloseMenu = jest.fn();
  render(
    <MobileNavigation
      role="admin"
      activeSection="home"
      availableSections={availableFor('admin')}
      menuOpen
      onOpenMenu={jest.fn()}
      onCloseMenu={onCloseMenu}
      onNavigate={jest.fn()}
      onLogout={jest.fn()}
    />,
  );

  fireEvent.keyDown(document, { key: 'Escape' });
  expect(onCloseMenu).toHaveBeenCalledTimes(1);
});
