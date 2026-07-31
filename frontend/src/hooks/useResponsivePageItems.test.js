import { renderHook, waitFor } from '@testing-library/react';
import useResponsivePageItems, { mergeUniqueItems } from './useResponsivePageItems';

test('accumula pagine sostituendo eventuali duplicati con il dato più recente', () => {
  expect(mergeUniqueItems(
    [{ id: 1, name: 'Uno' }, { id: 2, name: 'Due' }],
    [{ id: 2, name: 'Due aggiornato' }, { id: 3, name: 'Tre' }],
  )).toEqual([
    { id: 1, name: 'Uno' },
    { id: 2, name: 'Due aggiornato' },
    { id: 3, name: 'Tre' },
  ]);
});

test('accumula la seconda pagina mobile con la chiave predefinita senza render ripetuti', async () => {
  const firstPage = [{ id: 1, name: 'Uno' }];
  const secondPage = [{ id: 2, name: 'Due' }];
  const { result, rerender } = renderHook(
    ({ pageItems, page }) => useResponsivePageItems({
      pageItems,
      page,
      isMobile: true,
      resetKey: 'filtri-stabili',
    }),
    { initialProps: { pageItems: firstPage, page: 1 } },
  );

  expect(result.current).toEqual(firstPage);
  rerender({ pageItems: secondPage, page: 2 });

  await waitFor(() => {
    expect(result.current).toEqual([...firstPage, ...secondPage]);
  });
});
