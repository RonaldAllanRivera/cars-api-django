import { useInfiniteQuery, useQuery } from '@tanstack/vue-query';
import { computed, toValue } from 'vue';
import type { MaybeRefOrGetter } from 'vue';

import { apiRequest } from '../client';
import { compact, queryKeys } from '../queryKeys';
import type { ImageFilters } from '../queryKeys';
import { cursorPage, ImageCountSchema, ImageSchema, single } from '../schemas';

const imagePage = cursorPage(ImageSchema);
const oneImage = single(ImageSchema);

export function useImages(filters: MaybeRefOrGetter<ImageFilters> = {}) {
  return useInfiniteQuery({
    queryKey: computed(() => queryKeys.images(compact(toValue(filters)))),
    // null rather than undefined so the first page is explicit; the client
    // omits null params, so no cursor is sent.
    initialPageParam: null as string | null,
    queryFn: ({ queryKey, pageParam, signal }) =>
      apiRequest('/images', {
        query: { ...queryKey[1], cursor: pageParam },
        schema: imagePage,
        signal,
      }),
    getNextPageParam: (lastPage) => lastPage.meta.next_cursor,
  });
}

export function useSearchImages(searchId: MaybeRefOrGetter<number>) {
  return useInfiniteQuery({
    queryKey: computed(() => queryKeys.searchImages(toValue(searchId))),
    initialPageParam: null as string | null,
    queryFn: ({ queryKey, pageParam, signal }) =>
      apiRequest(`/searches/${queryKey[1]}/images`, {
        query: { ...queryKey[3], cursor: pageParam },
        schema: imagePage,
        signal,
      }),
    getNextPageParam: (lastPage) => lastPage.meta.next_cursor,
  });
}

export function useImage(id: MaybeRefOrGetter<number>) {
  return useQuery({
    queryKey: computed(() => queryKeys.image(toValue(id))),
    queryFn: async ({ queryKey, signal }) =>
      (await apiRequest(`/images/${queryKey[1]}`, { schema: oneImage, signal })).data,
  });
}

/**
 * How many images match. Its own request because cursor pagination computes no
 * total. Advisory only: it labels the export buttons, and the server recounts.
 */
export function useImageCount(
  filters: MaybeRefOrGetter<ImageFilters>,
  enabled: MaybeRefOrGetter<boolean> = true,
) {
  return useQuery({
    queryKey: computed(() => queryKeys.imageCount(compact(toValue(filters)))),
    enabled: computed(() => toValue(enabled)),
    queryFn: async ({ queryKey, signal }) =>
      (
        await apiRequest('/images/count', {
          query: { ...queryKey[2] },
          schema: ImageCountSchema,
          signal,
        })
      ).count,
  });
}
