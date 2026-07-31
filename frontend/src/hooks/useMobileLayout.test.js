import React from 'react';
import { act, render, screen } from '@testing-library/react';
import useMobileLayout from './useMobileLayout';

test('legge il breakpoint esportato dal CSS e reagisce al cambio viewport', () => {
  document.documentElement.style.setProperty('--breakpoint-mobile-max', '48rem');
  let onChange;
  window.matchMedia = jest.fn().mockReturnValue({
    matches: false,
    addEventListener: jest.fn((event, callback) => {
      if (event === 'change') onChange = callback;
    }),
    removeEventListener: jest.fn(),
  });
  const Probe = () => <span>{useMobileLayout() ? 'mobile' : 'desktop'}</span>;

  render(<Probe />);
  expect(window.matchMedia).toHaveBeenCalledWith('(max-width: 48rem)');
  expect(screen.getByText('desktop')).toBeInTheDocument();

  act(() => onChange({ matches: true }));
  expect(screen.getByText('mobile')).toBeInTheDocument();
});
