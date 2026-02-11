/**
 * React Query Client Configuration
 * Disables retries for 404 errors to prevent excessive requests
 */

import { QueryClient } from 'react-query';

// Create query client with custom retry logic
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Custom retry logic: don't retry on 4xx errors (client errors)
      retry: (failureCount, error) => {
        const status = error?.response?.status;

        // Don't retry on client errors (4xx)
        if (status && status >= 400 && status < 500) {
          return false;
        }

        // Retry on 5xx (server errors) up to 3 times
        if (!status || status >= 500) {
          return failureCount < 3;
        }

        return false;
      },
      // Other default options
      refetchOnWindowFocus: false,
      staleTime: 5 * 60 * 1000, // 5 minutes
    },
  },
});

export default queryClient;
