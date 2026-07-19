import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import CollaboratorsTable from './CollaboratorsTable';
import { getCollaboratorsPaginated } from '../../services/apiService';

jest.mock('../../services/apiService', () => ({
  getAgentSuggestions: jest.fn().mockResolvedValue([]),
  getCollaboratorsPaginated: jest.fn(),
}));

const handlers = {
  onEdit: jest.fn(), onDelete: jest.fn(), onOpenDocuments: jest.fn(),
  onOpenAssignmentModal: jest.fn(), onAssignProject: jest.fn(),
  onRemoveProject: jest.fn(), onEditAssignment: jest.fn(), onDownloadContract: jest.fn(),
};

beforeEach(() => {
  getCollaboratorsPaginated.mockResolvedValue({
    items: [{
      id: 1, first_name: 'Mario', last_name: 'Rossi', email: 'mario.rossi@gmail.com',
      position: 'Docente', city: 'Roma', projects: [],
    }],
    total: 1,
    pages: 1,
  });
});

test.each([
  ['admin', true],
  ['operatore', true],
  ['consultazione', false],
])('azioni collaboratore e assegnazione visibili per %s: %s', async (role, expected) => {
  render(
    <CollaboratorsTable
      projects={[]}
      assignments={[]}
      currentUser={{ role }}
      refreshTrigger={0}
      {...handlers}
    />,
  );

  await screen.findByText('Rossi Mario');
  expect(Boolean(screen.queryByTitle('Modifica'))).toBe(expected);
  expect(Boolean(screen.queryByTitle('Assegna'))).toBe(expected);
  expect(Boolean(screen.queryByTitle('Elimina'))).toBe(expected);
  expect(screen.getByTitle('Documenti')).toBeInTheDocument();
});

