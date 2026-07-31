import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';

import CalendarFilterBar from './CalendarFilterBar';
import { DEFAULT_CALENDAR_FILTERS } from './calendarFilters';

const PROJECTS = [
  { id: 1, name: 'Progetto Alfa', is_active: true },
  { id: 2, name: 'Progetto Beta (chiuso)', is_active: false },
];
const COLLABORATORS = [
  { id: 10, first_name: 'Mario', last_name: 'Rossi' },
  { id: 11, first_name: 'Giulia', last_name: 'Bianchi' },
];

test('mostra il contatore eventi', () => {
  render(
    <CalendarFilterBar
      filters={DEFAULT_CALENDAR_FILTERS}
      projects={PROJECTS}
      collaborators={COLLABORATORS}
      eventCount={7}
      onChange={jest.fn()}
      onReset={jest.fn()}
    />,
  );
  expect(screen.getByText(/7 eventi mostrati/i)).toBeInTheDocument();
});

test('selezionare un collaboratore aggiunge il suo id (multi-selezione)', () => {
  const onChange = jest.fn();
  render(
    <CalendarFilterBar
      filters={DEFAULT_CALENDAR_FILTERS}
      projects={PROJECTS}
      collaborators={COLLABORATORS}
      eventCount={0}
      onChange={onChange}
      onReset={jest.fn()}
    />,
  );

  fireEvent.click(screen.getByLabelText(/rossi mario/i));

  expect(onChange).toHaveBeenCalledWith({ collaboratorIds: [10] });
});

test('deselezionare un collaboratore già scelto lo rimuove', () => {
  const onChange = jest.fn();
  render(
    <CalendarFilterBar
      filters={{ ...DEFAULT_CALENDAR_FILTERS, collaboratorIds: [10, 11] }}
      projects={PROJECTS}
      collaborators={COLLABORATORS}
      eventCount={0}
      onChange={onChange}
      onReset={jest.fn()}
    />,
  );

  fireEvent.click(screen.getByLabelText(/rossi mario/i));

  expect(onChange).toHaveBeenCalledWith({ collaboratorIds: [11] });
});

test('la ricerca collaboratore filtra la lista visibile', () => {
  render(
    <CalendarFilterBar
      filters={DEFAULT_CALENDAR_FILTERS}
      projects={PROJECTS}
      collaborators={COLLABORATORS}
      eventCount={0}
      onChange={jest.fn()}
      onReset={jest.fn()}
    />,
  );

  fireEvent.change(screen.getByPlaceholderText(/cerca collaboratore/i), { target: { value: 'giulia' } });

  expect(screen.queryByLabelText(/rossi mario/i)).not.toBeInTheDocument();
  expect(screen.getByLabelText(/bianchi giulia/i)).toBeInTheDocument();
});

test('il toggle "includi chiusi" mostra anche il progetto chiuso nel select', () => {
  render(
    <CalendarFilterBar
      filters={{ ...DEFAULT_CALENDAR_FILTERS, includeClosedProjects: true }}
      projects={PROJECTS}
      collaborators={COLLABORATORS}
      eventCount={0}
      onChange={jest.fn()}
      onReset={jest.fn()}
    />,
  );
  expect(screen.getByText('Progetto Beta (chiuso)')).toBeInTheDocument();
});

test('azzera filtri chiama onReset', () => {
  const onReset = jest.fn();
  render(
    <CalendarFilterBar
      filters={DEFAULT_CALENDAR_FILTERS}
      projects={PROJECTS}
      collaborators={COLLABORATORS}
      eventCount={0}
      onChange={jest.fn()}
      onReset={onReset}
    />,
  );
  fireEvent.click(screen.getByRole('button', { name: /azzera filtri/i }));
  expect(onReset).toHaveBeenCalled();
});
