import type { InfiniteData } from '@tanstack/vue-query';
import { describe, expect, it } from 'vitest';

import { mockApi } from '@/test/http';
import { waitFor, withSetup } from '@/test/mount';

import images from '../../__fixtures__/images.json';
import reviewed from '../../__fixtures__/review.json';
import type { CursorPage, Image } from '../../schemas';
import { useReviewImage, useReviewQueue } from '../useReviewImage';

type Pages = InfiniteData<CursorPage<Image>>;

const pending = images.data[0] as Image;
const other: Image = { ...pending, id: 7, title: 'File:Other.jpg' };

function seed(queryClient: ReturnType<typeof withSetup>['queryClient']) {
  const page = { ...images, data: [pending, other] } as CursorPage<Image>;
  const infinite: Pages = { pages: [page], pageParams: [null] };

  queryClient.setQueryData(['images', { review_status: 'pending' }], infinite);
  queryClient.setQueryData(['searches', 1, 'images', {}], infinite);
  queryClient.setQueryData(['images', pending.id], pending);
}

const statusIn = (queryClient: ReturnType<typeof withSetup>['queryClient'], key: unknown[], id = pending.id) =>
  (queryClient.getQueryData<Pages>(key)?.pages[0]?.data ?? []).find((image) => image.id === id)?.review_status;

describe('useReviewImage', () => {
  it('patches every cached copy of the image before the server answers', async () => {
    let answer!: () => void;
    const api = mockApi({
      'PATCH /images/2/review': () => new Promise((resolve) => (answer = () => resolve({ body: reviewed }))),
      'GET /images': { body: images },
      'GET /images/2': { body: { data: reviewed.data } },
      'GET /searches/1/images': { body: images },
    });
    const { result: review, queryClient } = withSetup(() => useReviewImage());
    seed(queryClient);

    review.mutate({ id: pending.id, review_status: 'rejected' });

    await waitFor(() => expect(statusIn(queryClient, ['images', { review_status: 'pending' }])).toBe('rejected'));
    expect(statusIn(queryClient, ['searches', 1, 'images', {}])).toBe('rejected');
    expect(queryClient.getQueryData<Image>(['images', pending.id])?.review_status).toBe('rejected');
    expect(statusIn(queryClient, ['images', { review_status: 'pending' }], other.id)).toBe('pending');

    answer();
    await waitFor(() => expect(review.isSuccess.value).toBe(true));
    expect(api.calls('PATCH /images/2/review')[0]?.body).toEqual({ review_status: 'rejected' });
  });

  it('rolls every cache back when the server refuses', async () => {
    mockApi({
      'PATCH /images/2/review': { status: 403, body: { message: 'Invalid ability provided.' } },
      'GET /images': { body: { ...images, data: [pending, other] } },
      'GET /images/2': { body: { data: pending } },
      'GET /searches/1/images': { body: { ...images, data: [pending, other] } },
    });
    const { result: review, queryClient } = withSetup(() => useReviewImage());
    seed(queryClient);

    review.mutate({ id: pending.id, review_status: 'approved' });

    await waitFor(() => expect(review.isError.value).toBe(true));
    expect(statusIn(queryClient, ['images', { review_status: 'pending' }])).toBe('pending');
    expect(statusIn(queryClient, ['searches', 1, 'images', {}])).toBe('pending');
    expect(queryClient.getQueryData<Image>(['images', pending.id])?.review_status).toBe('pending');
    expect(review.error.value?.message).toBe('Invalid ability provided.');
  });

  it("rolls back only the failed image, keeping another verdict given meanwhile", async () => {
    mockApi({
      'PATCH /images/2/review': { status: 500, body: { message: 'Server Error' } },
      'PATCH /images/7/review': { body: { data: { ...other, review_status: 'approved' } } },
    });
    const { queryClient, result } = withSetup(() => ({ a: useReviewImage(), b: useReviewImage() }));
    seed(queryClient);

    // The refetch after settling would overwrite the caches from the mock;
    // stop it so the assertion is about the rollback alone.
    queryClient.setDefaultOptions({ queries: { enabled: false, retry: false } });

    result.b.mutate({ id: other.id, review_status: 'approved' });
    result.a.mutate({ id: pending.id, review_status: 'rejected' });

    await waitFor(() => expect(result.a.isError.value).toBe(true));
    await waitFor(() => expect(result.b.isSuccess.value).toBe(true));
    expect(statusIn(queryClient, ['images', { review_status: 'pending' }], pending.id)).toBe('pending');
    expect(statusIn(queryClient, ['images', { review_status: 'pending' }], other.id)).toBe('approved');
  });
});

describe('useReviewQueue', () => {
  it('drops a card the moment its verdict is patched in, and restores it on rollback', async () => {
    let fail!: () => void;
    mockApi({
      'GET /images': { body: { ...images, data: [pending, other], meta: { ...images.meta, next_cursor: null } } },
      'PATCH /images/2/review': () =>
        new Promise((resolve) => (fail = () => resolve({ status: 500, body: { message: 'Server Error' } }))),
    });
    const { result, queryClient } = withSetup(() => ({ queue: useReviewQueue(), review: useReviewImage() }));

    await waitFor(() => expect(result.queue.images.value.map((image) => image.id)).toEqual([2, 7]));
    queryClient.setDefaultOptions({ queries: { enabled: false } });

    result.review.mutate({ id: 2, review_status: 'approved' });

    await waitFor(() => expect(result.queue.images.value.map((image) => image.id)).toEqual([7]));
    fail();
    await waitFor(() => expect(result.review.isError.value).toBe(true));
    expect(result.queue.images.value.map((image) => image.id)).toEqual([2, 7]);
  });
});
