import type { InfiniteData } from '@tanstack/react-query';

import type { CursorPage, Image } from '../schemas';
import { useImages } from './useImages';

/**
 * The review queue's own view of the pending-image list: everything
 * `useImages({ review_status: 'pending' })` returns, with the cached pages
 * filtered down to rows that are STILL pending.
 *
 * useReviewImage's optimistic update patches `review_status` in every
 * cached copy of an image without ever removing the row - that is what
 * lets its rollback be a plain snapshot restore instead of a
 * splice-and-reinsert (see useReviewImage.ts). Filtering here, on read, is
 * what turns that in-place patch into a card actually leaving the queue
 * the instant the optimistic write lands, rather than waiting for
 * onSettled's real network refetch to catch up and remove the row itself.
 */
export function useReviewQueueImages() {
  const query = useImages({ review_status: 'pending' });

  const data: InfiniteData<CursorPage<Image>> | undefined = query.data
    ? {
        ...query.data,
        pages: query.data.pages.map((page) => ({
          ...page,
          data: page.data.filter((image) => image.review_status === 'pending'),
        })),
      }
    : query.data;

  return { ...query, data };
}
