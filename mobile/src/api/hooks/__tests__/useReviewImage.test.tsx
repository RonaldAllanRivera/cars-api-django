import { notifyManager, QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react-native';
import type { ReactNode } from 'react';

import * as client from '../../client';
import { queryKeys } from '../../queryKeys';
import type { Image } from '../../schemas';
import { useReviewImage } from '../useReviewImage';

// notifyManager's default scheduler defers every observer notification
// through a real setTimeout(fn, 0), independent of whichever test's
// act()/waitFor cycle is running when that timer actually fires. With four
// mutations rendered in this file, a still-pending flush from one test can
// land during a later test and touch its already-unmounted HookContainer,
// producing an "not wrapped in act()" warning that has nothing to do with
// that later test's own behaviour. Running the scheduled callback
// immediately removes the cross-test timing race at its source.
notifyManager.setScheduler((callback) => callback());

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

// mutations.gcTime: 0 schedules the MutationCache entry's disposal via a
// real `setTimeout(fn, 0)` the moment the mutation observer unmounts, rather
// than clearing it synchronously. RNTL's automatic per-test cleanup unmounts
// the hook before that timer necessarily fires, so - with four tests in this
// file - a previous test's disposal timeout can land during a later test's
// act()/waitFor cycle and touch its already-unmounted HookContainer,
// producing a spurious "not wrapped in act()" warning that has nothing to do
// with this test's own behaviour. Disposing each QueryClient synchronously
// in afterEach (destroying any still-pending gc timeout immediately) closes
// that race without weakening the gcTime: 0 the mutation cache actually
// needs to avoid hanging the process.
const clients: QueryClient[] = [];

afterEach(() => {
  for (const queryClient of clients.splice(0)) queryClient.clear();
});

function setup(seed: Partial<Image> = {}) {
  const queryClient = new QueryClient({
    // mutations.gcTime: 0 disposes the MutationCache entry (and its own GC
    // timer) as soon as nothing observes it, instead of leaving it scheduled
    // for the default 5 minutes - queries.gcTime does not reach the
    // MutationCache, so without this the suite hangs past its normal exit.
    //
    // queries.gcTime is Infinity, not 0, for the opposite reason: this test
    // seeds `queryKeys.images(...)` directly via setQueryData with no
    // `useInfiniteQuery` observer ever mounted for it. An observer-less
    // query with gcTime: 0 is scheduled for eviction on the very next tick,
    // which races the mutation's optimistic patch and empties the cache
    // before the assertions ever see it. Infinity means no GC timeout is
    // scheduled at all, so the seeded data survives for the test's short
    // life and there is no timer left dangling afterwards either.
    defaultOptions: {
      queries: { retry: false, gcTime: Infinity },
      mutations: { retry: false, gcTime: 0 },
    },
  });
  clients.push(queryClient);

  queryClient.setQueryData(queryKeys.images({ review_status: 'pending' }), {
    pages: [page([image(seed)])],
    pageParams: [null],
  });

  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );

  return { queryClient, wrapper };
}

const cachedStatus = (queryClient: QueryClient) => {
  const cached = queryClient.getQueryData<{ pages: ReturnType<typeof page>[] }>(
    queryKeys.images({ review_status: 'pending' }),
  );

  return cached?.pages[0]?.data[0]?.review_status;
};

describe('useReviewImage', () => {
  beforeEach(() => jest.restoreAllMocks());

  it('moves the card before the request resolves', async () => {
    const { queryClient, wrapper } = setup();
    let resolve: ((value: unknown) => void) | undefined;
    jest.spyOn(client, 'apiRequest').mockReturnValueOnce(
      new Promise((r) => {
        resolve = r;
      }),
    );

    const { result } = renderHook(() => useReviewImage(), { wrapper });

    act(() => {
      result.current.mutate({ id: 1, review_status: 'approved' });
    });

    // The cache is already updated while the PATCH is still in flight.
    await waitFor(() => expect(cachedStatus(queryClient)).toBe('approved'));

    act(() => {
      resolve?.({ data: image({ review_status: 'approved', reviewed_by: 7 }) });
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });

  it('rolls the card back when the PATCH fails', async () => {
    const { queryClient, wrapper } = setup();
    jest
      .spyOn(client, 'apiRequest')
      .mockRejectedValueOnce(new client.ApiError(500, 'Server error'));

    const { result } = renderHook(() => useReviewImage(), { wrapper });

    act(() => {
      result.current.mutate({ id: 1, review_status: 'approved' });
    });

    await waitFor(() => expect(result.current.isError).toBe(true));

    // The snapshot is restored - the UI must not keep claiming "approved".
    expect(cachedStatus(queryClient)).toBe('pending');
  });

  it('restores the actual prior verdict on rollback, not a hardcoded default', async () => {
    // Seeded as 'rejected', not 'pending' - the realistic case of
    // re-reviewing an already-rejected image. This is what distinguishes a
    // real snapshot restore from a buggy
    // `onError: () => setQueryData(key, { ...current, review_status: 'pending' })`,
    // which the test above cannot catch because it starts at 'pending' too.
    const { queryClient, wrapper } = setup({ review_status: 'rejected' });
    jest
      .spyOn(client, 'apiRequest')
      .mockRejectedValueOnce(new client.ApiError(500, 'Server error'));

    const { result } = renderHook(() => useReviewImage(), { wrapper });

    act(() => {
      result.current.mutate({ id: 1, review_status: 'approved' });
    });

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(cachedStatus(queryClient)).toBe('rejected');
  });

  it('never sends the machine verdict fields', async () => {
    const { wrapper } = setup();
    const spy = jest
      .spyOn(client, 'apiRequest')
      .mockResolvedValueOnce({ data: image({ review_status: 'rejected' }) });

    const { result } = renderHook(() => useReviewImage(), { wrapper });

    await act(async () => {
      await result.current.mutateAsync({ id: 1, review_status: 'rejected' });
    });

    expect(spy).toHaveBeenCalledWith(
      '/images/1/review',
      expect.objectContaining({ method: 'PATCH', body: { review_status: 'rejected' } }),
    );
  });
});
