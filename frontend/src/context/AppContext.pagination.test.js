import { collectAllPages } from './AppContext';

test('carica tutte le pagine progetto senza troncare il multiplo del limite', async () => {
  const first = Array.from({ length: 2 }, (_, index) => ({ id: index + 1 }));
  const second = Array.from({ length: 2 }, (_, index) => ({ id: index + 3 }));
  const fetchPage = jest.fn()
    .mockResolvedValueOnce(first)
    .mockResolvedValueOnce(second)
    .mockResolvedValueOnce([{ id: 5 }]);

  await expect(collectAllPages(fetchPage, { skip: 0, limit: 2 }))
    .resolves.toEqual([...first, ...second, { id: 5 }]);
  expect(fetchPage.mock.calls).toEqual([
    [{ skip: 0, limit: 2 }],
    [{ skip: 2, limit: 2 }],
    [{ skip: 4, limit: 2 }],
  ]);
});
