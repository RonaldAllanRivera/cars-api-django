import { useInfiniteQuery, useQuery } from '@tanstack/react-query';

import { apiRequest } from '../client';
import { queryKeys } from '../queryKeys';
import type { SearchFilters } from '../queryKeys';
import { cursorPage, SearchSchema, single } from '../schemas';

const searchPage = cursorPage(SearchSchema);
const oneSearch = single(SearchSchema);

/**
 * A filters object rather than a bare status: the Pipeline tab needs `source`,
 * `csv_import_id` and `coverage`, and the Search tab needs `source: 'adhoc'`
 * so the two stop showing each other's runs.
 */
export function useSearches(filters: SearchFilters = {}) {
  return useInfiniteQuery({
    queryKey: queryKeys.searches(filters),
    initialPageParam: null as string | null,
    queryFn: ({ pageParam }) =>
      apiRequest('/searches', {
        query: { ...filters, cursor: pageParam ?? undefined },
        schema: searchPage,
      }),
    getNextPageParam: (lastPage) => lastPage.meta.next_cursor,
  });
}

export function useSearch(id: number) {
  return useQuery({
    queryKey: queryKeys.search(id),
    queryFn: async () => (await apiRequest(`/searches/${id}`, { schema: oneSearch })).data,
  });
}
