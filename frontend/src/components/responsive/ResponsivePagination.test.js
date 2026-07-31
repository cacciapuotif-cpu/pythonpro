import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import ResponsivePagination from './ResponsivePagination';

const renderPagination = (mobile, props = {}) => {
  document.documentElement.style.setProperty('--breakpoint-mobile-max', '48rem');
  window.matchMedia = jest.fn().mockReturnValue({
    matches: mobile,
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
  });
  const onPageChange = jest.fn();
  render(
    <ResponsivePagination
      page={1}
      pages={3}
      total={45}
      visibleCount={20}
      onPageChange={onPageChange}
      entityLabel="allievi"
      {...props}
    />,
  );
  return onPageChange;
};

test('su mobile propone il caricamento progressivo con conteggio', () => {
  const onPageChange = renderPagination(true);
  expect(screen.getByText('20 di 45 allievi')).toBeInTheDocument();
  const loadMore = screen.getByRole('button', { name: 'Carica altri' });
  expect(loadMore).toHaveAttribute('data-load-more');
  fireEvent.click(loadMore);
  expect(onPageChange).toHaveBeenCalledWith(2);
  expect(document.querySelector('[data-pagination-layout="desktop"]')).not.toBeInTheDocument();
});

test('su desktop mantiene i controlli di pagina', () => {
  const onPageChange = renderPagination(false);
  fireEvent.click(screen.getByRole('button', { name: 'Pagina successiva' }));
  expect(onPageChange).toHaveBeenCalledWith(2);
  expect(document.querySelector('[data-pagination-layout="mobile"]')).not.toBeInTheDocument();
});
