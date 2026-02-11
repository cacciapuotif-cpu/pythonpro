/**
 * React Query hooks for Items
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../lib/api';
import { QUERY_KEYS, UI } from '../lib/constants';
import { showToast } from '../components';
import type { Item } from '../types/api';

/**
 * Get all items
 */
export const useItems = () => {
  return useQuery({
    queryKey: QUERY_KEYS.ITEMS,
    queryFn: () => api.getItems(),
    staleTime: UI.STALE_TIME,
    gcTime: UI.CACHE_TIME,
  });
};

/**
 * Get single item
 */
export const useItem = (id: number) => {
  return useQuery({
    queryKey: QUERY_KEYS.ITEM(id),
    queryFn: () => api.getItem(id),
    staleTime: UI.STALE_TIME,
    gcTime: UI.CACHE_TIME,
    enabled: !!id,
  });
};

/**
 * Update item with optimistic update
 */
export const useUpdateItem = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<Item> }) =>
      api.updateItem(id, data),
    onMutate: async ({ id, data }) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: QUERY_KEYS.ITEM(id) });

      // Snapshot previous value
      const previousItem = queryClient.getQueryData<Item>(QUERY_KEYS.ITEM(id));

      // Optimistically update
      if (previousItem) {
        queryClient.setQueryData<Item>(QUERY_KEYS.ITEM(id), {
          ...previousItem,
          ...data,
        });
      }

      return { previousItem };
    },
    onError: (error, { id }, context) => {
      // Rollback on error
      if (context?.previousItem) {
        queryClient.setQueryData(QUERY_KEYS.ITEM(id), context.previousItem);
      }
      showToast({
        message: error.message || 'Errore durante il salvataggio',
        type: 'error',
      });
    },
    onSuccess: (data, { id }) => {
      // Update cache with server response
      queryClient.setQueryData(QUERY_KEYS.ITEM(id), data);
      // Invalidate list to refresh
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.ITEMS });
      showToast({
        message: 'Modifiche salvate con successo',
        type: 'success',
      });
    },
  });
};

/**
 * Create item
 */
export const useCreateItem = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: Omit<Item, 'id'>) => api.createItem(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.ITEMS });
      showToast({
        message: 'Item creato con successo',
        type: 'success',
      });
    },
    onError: (error) => {
      showToast({
        message: error.message || 'Errore durante la creazione',
        type: 'error',
      });
    },
  });
};

/**
 * Delete item
 */
export const useDeleteItem = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => api.deleteItem(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.ITEMS });
      showToast({
        message: 'Item eliminato con successo',
        type: 'success',
      });
    },
    onError: (error) => {
      showToast({
        message: error.message || 'Errore durante l\'eliminazione',
        type: 'error',
      });
    },
  });
};
