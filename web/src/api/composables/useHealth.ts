import { useInfiniteQuery, useQuery } from '@tanstack/vue-query';
import { computed, toValue } from 'vue';
import type { MaybeRefOrGetter } from 'vue';

import { apiRequest } from '../client';
import { compact, queryKeys } from '../queryKeys';
import type { ErrorFilters } from '../queryKeys';
import { cursorPage, ErrorEventSchema, HealthSummarySchema, single } from '../schemas';

const health = single(HealthSummarySchema);
const errorPage = cursorPage(ErrorEventSchema);

export function useHealth() {
  return useQuery({
    queryKey: queryKeys.health(),
    queryFn: async ({ signal }) =>
      (await apiRequest('/health/summary', { schema: health, signal })).data,
    // "Is the pipeline broken now" goes stale fast.
    staleTime: 15_000,
  });
}

export function useErrors(filters: MaybeRefOrGetter<ErrorFilters> = {}) {
  return useInfiniteQuery({
    queryKey: computed(() => queryKeys.errors(compact(toValue(filters)))),
    initialPageParam: null as string | null,
    queryFn: ({ queryKey, pageParam, signal }) =>
      apiRequest('/errors', {
        query: { ...queryKey[1], cursor: pageParam },
        schema: errorPage,
        signal,
      }),
    getNextPageParam: (lastPage) => lastPage.meta.next_cursor,
  });
}
