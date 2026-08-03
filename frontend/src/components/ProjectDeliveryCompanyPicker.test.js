import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';

import ProjectDeliveryCompanyPicker from './ProjectDeliveryCompanyPicker';
import {
  getProjectDeliveryCompanies,
  getProjectDeliveryCompanyStudents,
} from '../services/apiService';

jest.mock('../services/apiService', () => ({
  getProjectDeliveryCompanies: jest.fn(),
  getProjectDeliveryCompanyStudents: jest.fn(),
}));

const company = {
  id: 7,
  ragione_sociale: 'Alpha Srl',
  partita_iva: '12345678901',
  sedi_operative: [],
};

describe('ProjectDeliveryCompanyPicker', () => {
  beforeEach(() => {
    jest.useFakeTimers();
    jest.clearAllMocks();
    getProjectDeliveryCompanies.mockResolvedValue({
      items: [company],
      total: 1,
      limit: 20,
      offset: 0,
      has_more: false,
    });
    getProjectDeliveryCompanyStudents.mockResolvedValue({
      items: [{ id: 81, nome: 'Ada', cognome: 'Lovelace', azienda_cliente_id: 7 }],
      total: 1,
      limit: 100,
      offset: 0,
      has_more: false,
    });
  });

  afterEach(() => {
    jest.clearAllTimers();
    jest.useRealTimers();
  });

  test('cerca sul server e carica gli allievi soltanto quando si espande azienda', async () => {
    const onChange = jest.fn();
    render(
      <ProjectDeliveryCompanyPicker
        projectId={11}
        aziendeSelezionate={[]}
        allieviSelezionati={[]}
        onChange={onChange}
        onCompaniesLoaded={jest.fn()}
        onStudentsLoaded={jest.fn()}
        onError={jest.fn()}
      />,
    );

    expect(getProjectDeliveryCompanyStudents).not.toHaveBeenCalled();
    await waitFor(() => expect(screen.getByText('Alpha Srl')).toBeInTheDocument());
    expect(getProjectDeliveryCompanies).toHaveBeenCalledWith(11, {
      q: '',
      limit: 20,
      offset: 0,
    });
    expect(getProjectDeliveryCompanyStudents).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'Mostra allievi' }));
    await waitFor(() => expect(getProjectDeliveryCompanyStudents).toHaveBeenCalledWith(11, 7, {
      limit: 100,
      offset: 0,
    }));
    expect(await screen.findByText(/Ada/)).toBeInTheDocument();
  });

  test('il testo digitato diventa parametro q dopo debounce, senza filtro locale', async () => {
    getProjectDeliveryCompanies
      .mockResolvedValueOnce({ items: [company], total: 1, has_more: false })
      .mockResolvedValueOnce({
        items: [{ ...company, id: 8, ragione_sociale: 'Beta Srl' }],
        total: 1,
        has_more: false,
      });

    render(
      <ProjectDeliveryCompanyPicker
        projectId={11}
        onChange={jest.fn()}
        onCompaniesLoaded={jest.fn()}
        onStudentsLoaded={jest.fn()}
        onError={jest.fn()}
      />,
    );
    await act(async () => {
      jest.advanceTimersByTime(300);
      await Promise.resolve();
    });
    await waitFor(() => expect(screen.getByText('Alpha Srl')).toBeInTheDocument());

    fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'Beta' } });
    expect(getProjectDeliveryCompanies).toHaveBeenCalledTimes(1);
    await act(async () => {
      jest.advanceTimersByTime(300);
      await Promise.resolve();
    });
    await waitFor(() => expect(getProjectDeliveryCompanies).toHaveBeenLastCalledWith(11, {
      q: 'Beta',
      limit: 20,
      offset: 0,
    }));
    expect(await screen.findByText('Beta Srl')).toBeInTheDocument();
    expect(screen.queryByText('Alpha Srl')).not.toBeInTheDocument();
  });
});
