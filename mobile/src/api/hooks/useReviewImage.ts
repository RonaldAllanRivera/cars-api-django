import type { InfiniteData } from '@tanstack/react-query';
import { useMutation, useQueryClient } from '@tanstack/react-query';

import { apiRequest } from '../client';
import { queryKeys } from '../queryKeys';
import { ImageSchema, single } from '../schemas';
import type { CursorPage, Image, ReviewStatus } from '../schemas';

interface Variables {
  id: number;
  review_status: ReviewStatus;
}

const oneImage = single(ImageSchema);

/**
 * True for every cache entry that could hold a row for this image:
 * - `queryKeys.images(filters)` -> ['images', filters]
 * - `queryKeys.image(id)` -> ['images', id]
 * - `queryKeys.searchImages(searchId, filters)` -> ['searches', searchId, 'images', filters]
 *
 * A plain `{ queryKey: ['images'] }` prefix filter only reaches the first
 * two - `['searches', id, 'images', filters]` does not start with 'images',
 * so a run's own image list would keep showing a stale badge after a
 * review made from that screen. `queryKeys.searches(status)` (['searches',
 * {status}]) and `queryKeys.search(id)` (['searches', id]) are 2 elements
 * long and never have 'images' at index 2, so they are correctly excluded.
 */
const touchesImageCaches = (queryKey: readonly unknown[]) =>
  queryKey[0] === 'images' || queryKey[2] === 'images';

export function useReviewImage() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, review_status }: Variables) =>
      apiRequest(`/images/${id}/review`, {
        method: 'PATCH',
        // Only the verdict. make_confirmed and year_confirmed belong to
        // MakeRelevanceChecker and the API would ignore them anyway.
        body: { review_status },
        schema: oneImage,
      }),

    onMutate: async ({ id, review_status }) => {
      // Stop an in-flight refetch landing on top of the optimistic write.
      await queryClient.cancelQueries({ predicate: (query) => touchesImageCaches(query.queryKey) });

      const snapshot = queryClient.getQueriesData({
        predicate: (query) => touchesImageCaches(query.queryKey),
      });

      // Every cached list, whatever its filters or run scope, plus the
      // detail cache.
      queryClient.setQueriesData<InfiniteData<CursorPage<Image>>>(
        { predicate: (query) => touchesImageCaches(query.queryKey) },
        (current) => {
          if (!current?.pages) return current;

          return {
            ...current,
            pages: current.pages.map((page) => ({
              ...page,
              data: page.data.map((image) =>
                image.id === id ? { ...image, review_status } : image,
              ),
            })),
          };
        },
      );

      queryClient.setQueryData<Image>(queryKeys.image(id), (current) =>
        current ? { ...current, review_status } : current,
      );

      return { snapshot };
    },

    onError: (_error, _variables, context) => {
      // Put every cache back exactly as it was. An optimistic update that
      // cannot undo itself leaves the UI asserting something the server
      // never accepted.
      for (const [key, data] of context?.snapshot ?? []) {
        queryClient.setQueryData(key, data);
      }
    },

    onSettled: (_data, _error, { id }) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.image(id) });
      void queryClient.invalidateQueries({ predicate: (query) => touchesImageCaches(query.queryKey) });
    },
  });
}
