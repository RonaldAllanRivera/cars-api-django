import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/vue-query';
import { computed, toValue } from 'vue';
import type { MaybeRefOrGetter } from 'vue';
import { z } from 'zod';

import { apiRequest, apiRequestRaw } from '../client';
import { compact, queryKeys } from '../queryKeys';
import type { SearchFilters } from '../queryKeys';
import { cursorPage, SearchSchema, single } from '../schemas';
import type { Search } from '../schemas';

const searchPage = cursorPage(SearchSchema);
const oneSearch = single(SearchSchema);

export function useSearches(filters: MaybeRefOrGetter<SearchFilters> = {}) {
  return useInfiniteQuery({
    queryKey: computed(() => queryKeys.searches(compact(toValue(filters)))),
    initialPageParam: null as string | null,
    queryFn: ({ queryKey, pageParam, signal }) =>
      apiRequest('/searches', {
        query: { ...queryKey[1], cursor: pageParam },
        schema: searchPage,
        signal,
      }),
    getNextPageParam: (lastPage) => lastPage.meta.next_cursor,
  });
}

export function useSearch(id: MaybeRefOrGetter<number>) {
  return useQuery({
    queryKey: computed(() => queryKeys.search(toValue(id))),
    queryFn: async ({ queryKey, signal }) =>
      (await apiRequest(`/searches/${queryKey[1]}`, { schema: oneSearch, signal })).data,
  });
}

/** Mirrors the server config. The form checks these before the round trip. */
export const MAX_YEAR_SPAN = 3;
export const MAX_IMAGES_PER_YEAR = 5;

export interface CreateSearchInput {
  make: string;
  model?: string;
  from_year: number;
  to_year: number;
  color?: string;
  transmission?: string;
  transparent_background?: boolean;
  images_per_year?: number;
}

export type CreateSearchOutcome = 'created' | 'existing' | 'blocked' | 'failed';

export interface CreateSearchResult {
  search: Search;
  outcome: CreateSearchOutcome;
  message?: string;
  retryAfterSeconds?: number;
}

const createEnvelope = z.object({
  data: SearchSchema,
  message: z.string().optional(),
  retry_after_seconds: z.number().int().nullable().optional(),
});

const OUTCOMES: Record<number, CreateSearchOutcome> = {
  201: 'created',
  200: 'existing',
  503: 'blocked',
  502: 'failed',
};

export async function createSearch(input: CreateSearchInput): Promise<CreateSearchResult> {
  const { status, body } = await apiRequestRaw('/searches', {
    method: 'POST',
    body: input,
    // 422 and 429 are not listed: a rejected cap or a throttle is a real error
    // the form must surface, not an outcome to render.
    acceptStatuses: [503, 502],
  });

  const parsed = createEnvelope.safeParse(body);

  if (!parsed.success) {
    throw new Error('The API response did not match the client contract for /searches.');
  }

  return {
    search: parsed.data.data,
    outcome: OUTCOMES[status] ?? 'failed',
    message: parsed.data.message,
    retryAfterSeconds: parsed.data.retry_after_seconds ?? undefined,
  };
}

export function useCreateSearch() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createSearch,
    onSuccess: () => {
      // A new run changes both the run list and the health counters.
      void queryClient.invalidateQueries({ queryKey: ['searches'] });
      void queryClient.invalidateQueries({ queryKey: queryKeys.health() });
    },
  });
}
