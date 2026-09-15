import { beforeEach, describe, expect, it } from 'vitest';

import type { Image } from '@/api/schemas';
import { setSessionForTests } from '@/auth/auth';
import { mockApi } from '@/test/http';
import { mountAt, waitFor } from '@/test/mount';

import images from '../../api/__fixtures__/images.json';
import me from '../../api/__fixtures__/me.json';

const base = images.data[0] as Image;
const queue: Image[] = [
  { ...base, id: 11, make: 'Toyota', model: 'RAV4', year: 1997 },
  { ...base, id: 12, make: 'Honda', model: 'Civic', year: 1998 },
  { ...base, id: 13, make: 'Mazda', model: 'MX-5', year: 1990 },
];

/** A tiny stand-in server: verdicts it accepts stick, so refetches see the queue shrink. */
function routes(over: Record<string, unknown> = {}) {
  const statuses = new Map(queue.map((image) => [image.id, 'pending']));
  const review = (id: number) => (request: { body: unknown }) => {
    const status = (request.body as { review_status: string }).review_status;
    statuses.set(id, status);

    return { body: { data: { ...queue.find((image) => image.id === id), review_status: status } } };
  };

  return {
    'GET /images': () => ({
      body: {
        ...images,
        data: queue.filter((image) => statuses.get(image.id) === 'pending'),
        meta: { ...images.meta, next_cursor: null },
      },
    }),
    'GET /images/count': () => ({ body: { count: [...statuses.values()].filter((s) => s === 'pending').length } }),
    'PATCH /images/11/review': review(11),
    'PATCH /images/12/review': review(12),
    'PATCH /images/13/review': review(13),
    ...over,
  } as Parameters<typeof mockApi>[0];
}

const heading = (wrapper: Awaited<ReturnType<typeof mountAt>>['wrapper']) => wrapper.get('section h2').text();

describe('review page', () => {
  beforeEach(() => setSessionForTests(me.data));

  it('shows the first pending image with its checks', async () => {
    const api = mockApi(routes());
    const { wrapper } = await mountAt('/review');

    await waitFor(() => expect(heading(wrapper)).toBe('Toyota RAV4 1997'));
    expect(api.calls('GET /images')[0]?.url.searchParams.get('review_status')).toBe('pending');
    expect(wrapper.text()).toContain('1 of 3');
    expect(wrapper.findAll('nav[aria-label="Review queue"] button')).toHaveLength(3);
  });

  it('approves, removes the image at once and moves to the next', async () => {
    const api = mockApi(routes());
    const { wrapper } = await mountAt('/review');
    await waitFor(() => expect(heading(wrapper)).toBe('Toyota RAV4 1997'));

    const approve = wrapper.findAll('button').find((button) => button.text().startsWith('Approve'));
    await approve?.trigger('click');

    await waitFor(() => expect(heading(wrapper)).toBe('Honda Civic 1998'));
    expect(api.calls('PATCH /images/11/review')[0]?.body).toEqual({ review_status: 'approved' });
    expect(wrapper.text()).toContain('Approved Toyota RAV4 1997.');
  });

  it('takes verdicts and moves by keyboard', async () => {
    const api = mockApi(routes());
    const { wrapper } = await mountAt('/review');
    await waitFor(() => expect(heading(wrapper)).toBe('Toyota RAV4 1997'));

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight' }));
    await waitFor(() => expect(heading(wrapper)).toBe('Honda Civic 1998'));

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'r' }));

    await waitFor(() => expect(api.calls('PATCH /images/12/review')[0]?.body).toEqual({ review_status: 'rejected' }));
    await waitFor(() => expect(heading(wrapper)).toBe('Mazda MX-5 1990'));
  });

  it('ignores shortcuts typed with a modifier', async () => {
    const api = mockApi(routes());
    const { wrapper } = await mountAt('/review');
    await waitFor(() => expect(heading(wrapper)).toBe('Toyota RAV4 1997'));

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'a', metaKey: true }));
    await new Promise((resolve) => setTimeout(resolve, 20));

    expect(api.calls('PATCH /images/11/review')).toHaveLength(0);
  });

  it('puts the image back and says so when the verdict is refused', async () => {
    let refuse!: () => void;
    mockApi(
      routes({
        'PATCH /images/11/review': () =>
          new Promise((resolve) => (refuse = () => resolve({ status: 403, body: { message: 'Invalid ability provided.' } }))),
      }),
    );
    const { wrapper } = await mountAt('/review');
    await waitFor(() => expect(heading(wrapper)).toBe('Toyota RAV4 1997'));

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'a' }));
    await waitFor(() => expect(heading(wrapper)).toBe('Honda Civic 1998'));

    refuse();

    await waitFor(() =>
      expect(wrapper.find('[role="alert"]').text()).toContain('Invalid ability provided. Toyota RAV4 1997 is back in the queue.'),
    );
    await waitFor(() => expect(wrapper.findAll('nav[aria-label="Review queue"] button')).toHaveLength(3));
  });

  it('says when the queue is empty', async () => {
    mockApi({ 'GET /images': { body: { ...images, data: [], meta: { ...images.meta, next_cursor: null } } }, 'GET /images/count': { body: { count: 0 } } });
    const { wrapper } = await mountAt('/review');

    await waitFor(() => expect(wrapper.text()).toContain('Nothing left to review'));
  });
});
