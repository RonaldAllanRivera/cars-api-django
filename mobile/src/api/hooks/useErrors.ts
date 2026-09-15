import { useInfiniteQuery } from '@tanstack/react-query';

import { apiRequest } from '../client';
import type { ErrorFilters } from '../queryKeys';
import { queryKeys } from '../queryKeys';
import { cursorPage, ErrorEventSchema } from '../schemas';

const errorPage = cursorPage(ErrorEventSchema);

export function useErrors(filters: ErrorFilters = {}) {
  return useInfiniteQuery({
    queryKey: queryKeys.errors(filters),
    initialPageParam: null as string | null,
    queryFn: ({ pageParam }) =>
      apiRequest('/errors', {
        query: { ...filters, cursor: pageParam ?? undefined },
        schema: errorPage,
      }),
    getNextPageParam: (lastPage) => lastPage.meta.next_cursor,
  });
}
