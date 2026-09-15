import { useInfiniteQuery, useQuery } from '@tanstack/react-query';

import { apiRequest } from '../client';
import type { ImageFilters } from '../queryKeys';
import { queryKeys } from '../queryKeys';
import { cursorPage, ImageSchema, single } from '../schemas';

const imagePage = cursorPage(ImageSchema);
const oneImage = single(ImageSchema);

export function useImages(filters: ImageFilters = {}) {
  return useInfiniteQuery({
    queryKey: queryKeys.images(filters),
    // null rather than undefined so the first page is an explicit value;
    // the client omits null query params, so no cursor is sent.
    initialPageParam: null as string | null,
    queryFn: ({ pageParam }) =>
      apiRequest('/images', {
        query: { ...filters, cursor: pageParam ?? undefined },
        schema: imagePage,
      }),
    getNextPageParam: (lastPage) => lastPage.meta.next_cursor,
  });
}

export function useSearchImages(searchId: number, filters: ImageFilters = {}) {
  return useInfiniteQuery({
    queryKey: queryKeys.searchImages(searchId, filters),
    initialPageParam: null as string | null,
    queryFn: ({ pageParam }) =>
      apiRequest(`/searches/${searchId}/images`, {
        query: { ...filters, cursor: pageParam ?? undefined },
        schema: imagePage,
      }),
    getNextPageParam: (lastPage) => lastPage.meta.next_cursor,
  });
}

export function useImage(id: number) {
  return useQuery({
    queryKey: queryKeys.image(id),
    queryFn: async () => (await apiRequest(`/images/${id}`, { schema: oneImage })).data,
  });
}
