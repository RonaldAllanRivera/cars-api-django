import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react-native';
import type { ReactNode } from 'react';

import imagesFixture from '../../__fixtures__/images.json';
import * as client from '../../client';
import { useImages } from '../useImages';

const wrapper = ({ children }: { children: ReactNode }) => {
  const queryClient = new QueryClient({
    // gcTime: 0 disposes the cache (and its GC timer) as soon as nothing
    // observes it, instead of leaving it scheduled for the default 5
    // minutes. Without this, the timer outlives the test as a real handle
    // and Jest hangs past its normal exit - `--detectOpenHandles` catches
    // it directly.
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
};

describe('useImages', () => {
  beforeEach(() => jest.restoreAllMocks());

  it('fetches the first page with no cursor', async () => {
    const spy = jest.spyOn(client, 'apiRequest').mockResolvedValue(imagesFixture);

    const { result } = renderHook(() => useImages({ make: 'Toyota' }), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(spy).toHaveBeenCalledWith(
      '/images',
      expect.objectContaining({ query: expect.objectContaining({ make: 'Toyota', cursor: undefined }) }),
    );
  });

  it('follows meta.next_cursor for the next page', async () => {
    const spy = jest
      .spyOn(client, 'apiRequest')
      .mockResolvedValueOnce(imagesFixture)
      .mockResolvedValueOnce({
        ...imagesFixture,
        meta: { ...imagesFixture.meta, next_cursor: null },
      });

    const { result } = renderHook(() => useImages(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.hasNextPage).toBe(true);

    await result.current.fetchNextPage();

    await waitFor(() => expect(result.current.hasNextPage).toBe(false));
    expect(spy).toHaveBeenLastCalledWith(
      '/images',
      expect.objectContaining({
        query: expect.objectContaining({ cursor: imagesFixture.meta.next_cursor }),
      }),
    );
  });
});
