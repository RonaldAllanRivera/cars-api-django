import type { InfiniteData, Query } from '@tanstack/vue-query';
import { useMutation, useQueryClient } from '@tanstack/vue-query';
import { computed } from 'vue';

import { apiRequest } from '../client';
import { queryKeys } from '../queryKeys';
import { ImageSchema, single } from '../schemas';
import type { CursorPage, Image, ReviewStatus } from '../schemas';

import { useImages } from './useImages';

export interface ReviewVariables {
  id: number;
  review_status: ReviewStatus;
}

const oneImage = single(ImageSchema);

export const REVIEW_MUTATION_KEY = ['review-image'] as const;

/**
 * True for every cache entry that could hold a row for this image:
 * ['images', filters], ['images', id] and ['searches', searchId, 'images', {}].
 * A plain ['images'] prefix would miss a run's own image list. The count lives
 * at ['images', 'count', filters] and holds a number, which the updater skips.
 */
export const touchesImageCaches = (query: Pick<Query, 'queryKey'>) =>
  query.queryKey[0] === 'images' || query.queryKey[2] === 'images';

function isInfinite(value: unknown): value is InfiniteData<CursorPage<Image>> {
  return typeof value === 'object' && value !== null && Array.isArray((value as { pages?: unknown }).pages);
}

function isImage(value: unknown): value is Image {
  return typeof value === 'object' && value !== null && 'review_status' in value && 'id' in value;
}

/** Applies `change` to the row for `id` in whichever cache shape this is. */
function mapImage(data: unknown, id: number, change: (image: Image) => Image): unknown {
  if (isInfinite(data)) {
    return {
      ...data,
      pages: data.pages.map((page) => ({
        ...page,
        data: page.data.map((image) => (image.id === id ? change(image) : image)),
      })),
    };
  }

  return isImage(data) && data.id === id ? change(data) : data;
}

function findImage(data: unknown, id: number): Image | undefined {
  if (isInfinite(data)) {
    for (const page of data.pages) {
      const found = page.data.find((image) => image.id === id);
      if (found) return found;
    }

    return undefined;
  }

  return isImage(data) && data.id === id ? data : undefined;
}

export function useReviewImage() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationKey: REVIEW_MUTATION_KEY,
    mutationFn: ({ id, review_status }: ReviewVariables) =>
      apiRequest(`/images/${id}/review`, {
        method: 'PATCH',
        // Only the verdict. make_confirmed and year_confirmed are the relevance
        // checker's answer, and the API ignores them anyway.
        body: { review_status },
        schema: oneImage,
      }),

    onMutate: async ({ id, review_status }) => {
      // Stop an in-flight refetch landing on top of the optimistic write.
      await queryClient.cancelQueries({ predicate: touchesImageCaches });

      const snapshot = queryClient.getQueriesData({ predicate: touchesImageCaches });

      // Patched in place rather than removed, so undoing it is a patch too. The
      // review queue filters on read, which is what removes the card.
      queryClient.setQueriesData({ predicate: touchesImageCaches }, (current: unknown) =>
        mapImage(current, id, (image) => ({ ...image, review_status })),
      );

      return { snapshot };
    },

    onError: (_error, { id }, context) => {
      // Put this image back exactly as each cache had it - and only this image.
      // Restoring whole snapshots would also undo verdicts given on other
      // images while this request was in flight, which a fast reviewer does.
      for (const [key, before] of context?.snapshot ?? []) {
        const original = findImage(before, id);
        if (!original) continue;

        queryClient.setQueryData(key, (current: unknown) => mapImage(current, id, () => original));
      }
    },

    onSettled: () => {
      // Once, after the last of a burst: a reviewer working through the queue
      // by keyboard would otherwise refetch every loaded page per keystroke.
      // This mutation still counts as in flight while it settles, hence 1.
      if (queryClient.isMutating({ mutationKey: REVIEW_MUTATION_KEY }) > 1) return;

      void queryClient.invalidateQueries({ predicate: touchesImageCaches });
      void queryClient.invalidateQueries({ queryKey: queryKeys.health() });
    },
  });
}

/**
 * The pending-image list, with cached pages filtered to rows that are STILL
 * pending - which is what turns the optimistic in-place patch into a card
 * leaving the queue the instant a verdict lands.
 */
export function useReviewQueue() {
  const query = useImages({ review_status: 'pending' });

  const images = computed<Image[]>(
    () =>
      query.data.value?.pages.flatMap((page) =>
        page.data.filter((image) => image.review_status === 'pending'),
      ) ?? [],
  );

  return { query, images };
}
