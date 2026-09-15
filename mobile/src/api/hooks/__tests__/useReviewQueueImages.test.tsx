import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react-native';
import type { ReactNode } from 'react';

import * as client from '../../client';
import type { Image } from '../../schemas';
import { useReviewQueueImages } from '../useReviewQueueImages';

const image = (overrides: Partial<Image> = {}): Image =>
  ({
    id: 1,
    car_search_id: 1,
    make: 'Toyota',
    model: 'RAV4',
    year: 1997,
    color: null,
    title: 'File:RAV4.jpg',
    description: null,
    source_url: 'https://upload.wikimedia.org/a.jpg',
    thumbnail_url: null,
    width: null,
    height: null,
    license: null,
    attribution: null,
    make_confirmed: true,
    year_confirmed: null,
    review_status: 'pending',
    reviewed_by: null,
    reviewed_at: null,
    download_status: 'not_downloaded',
    created_at: '2026-01-15T09:00:00+00:00',
    ...overrides,
  }) as Image;

const page = (items: Image[]) => ({
  data: items,
  links: { first: null, last: null, prev: null, next: null },
  meta: { path: '/api/v1/images', per_page: 24, next_cursor: null, prev_cursor: null },
});

const wrapper = ({ children }: { children: ReactNode }) => {
  const queryClient = new QueryClient({
    // gcTime: 0 disposes the cache (and its GC timer) as soon as nothing
    // observes it, instead of leaving it scheduled for the default 5
    // minutes - this suite mounts a real useInfiniteQuery observer (unlike
    // useReviewImage.test.tsx, which pre-seeds an unobserved cache entry),
    // so there is no eviction race here to avoid gcTime: 0 for.
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
};

describe('useReviewQueueImages', () => {
  beforeEach(() => jest.restoreAllMocks());

  it('excludes a row the instant its cached review_status is no longer pending', async () => {
    // Simulates exactly what useReviewImage's optimistic onMutate leaves
    // behind: it patches review_status in place and never removes the row
    // (so its rollback can be a plain snapshot restore). This is the case
    // that proves the queue actually drops the card on the optimistic
    // write, rather than only after a real network refetch.
    jest.spyOn(client, 'apiRequest').mockResolvedValueOnce({
      ...page([image({ id: 1, review_status: 'pending' }), image({ id: 2, review_status: 'approved' })]),
    });

    const { result } = renderHook(() => useReviewQueueImages(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const ids = result.current.data?.pages.flatMap((p) => p.data.map((i) => i.id));
    expect(ids).toEqual([1]);
  });

  it('keeps every page shape InfiniteGrid needs when there is nothing left', async () => {
    jest.spyOn(client, 'apiRequest').mockResolvedValueOnce({
      ...page([image({ id: 1, review_status: 'approved' })]),
    });

    const { result } = renderHook(() => useReviewQueueImages(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.pages[0]?.data).toEqual([]);
    // meta/links survive the filter untouched - InfiniteGrid's pagination
    // (hasNextPage etc.) reads meta.next_cursor via getNextPageParam, not
    // this filtered view.
    expect(result.current.data?.pages[0]?.meta.next_cursor).toBeNull();
  });
});
