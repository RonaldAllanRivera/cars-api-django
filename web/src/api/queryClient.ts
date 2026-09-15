import { QueryClient } from '@tanstack/vue-query';

import { ApiError } from './client';

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // A 4xx will not become a 2xx by being asked again: a dead token would
        // fire three 401s, a 429 would hit the shared bucket twice more. A 5xx
        // or a dropped connection still gets its retries.
        retry: (count, error) =>
          !(error instanceof ApiError && error.status >= 400 && error.status < 500) && count < 2,
        staleTime: 30_000,
        refetchOnWindowFocus: false,
      },
    },
  });
}

export const queryClient = createQueryClient();
