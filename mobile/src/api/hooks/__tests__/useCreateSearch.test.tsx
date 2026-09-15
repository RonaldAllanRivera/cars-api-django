import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react-native';
import type { ReactNode } from 'react';

import searchFixture from '../../__fixtures__/search-create.json';
import * as client from '../../client';
import { MAX_IMAGES_PER_YEAR, MAX_YEAR_SPAN, useCreateSearch } from '../useCreateSearch';

const wrapper = ({ children }: { children: ReactNode }) => {
  const queryClient = new QueryClient({
    // gcTime: 0 disposes the cache (and its GC timer) as soon as nothing
    // observes it, instead of leaving it scheduled for the default 5
    // minutes. Without this, the timer outlives the test as a real handle
    // and Jest hangs past its normal exit - `--detectOpenHandles` catches
    // it directly.
    //
    // `mutations` needs it as well as `queries`: the MutationCache keeps its
    // own GC timer, and `queries.gcTime` does not reach it. This suite is
    // the first to render a mutation, so it is the first to hang without it.
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { gcTime: 0 } },
  });

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
};

const input = { make: 'Toyota', model: 'RAV4', from_year: 1997, to_year: 1999 };

describe('useCreateSearch', () => {
  beforeEach(() => jest.restoreAllMocks());

  it('mirrors the API caps so the form can enforce them locally', () => {
    expect(MAX_YEAR_SPAN).toBe(3);
    expect(MAX_IMAGES_PER_YEAR).toBe(5);
  });

  it('reports a fresh run as created', async () => {
    jest.spyOn(client, 'apiRequestRaw').mockResolvedValueOnce({ status: 201, body: searchFixture });

    const { result } = renderHook(() => useCreateSearch(), { wrapper });

    await act(async () => {
      await result.current.mutateAsync(input);
    });

    await waitFor(() => expect(result.current.data?.outcome).toBe('created'));
    expect(result.current.data?.search.id).toBe(searchFixture.data.id);
  });

  it('reports a deduped run as existing', async () => {
    jest.spyOn(client, 'apiRequestRaw').mockResolvedValueOnce({ status: 200, body: searchFixture });

    const { result } = renderHook(() => useCreateSearch(), { wrapper });

    await act(async () => {
      await result.current.mutateAsync(input);
    });

    await waitFor(() => expect(result.current.data?.outcome).toBe('existing'));
  });

  it('reports a Wikimedia block without throwing, keeping the run link', async () => {
    jest.spyOn(client, 'apiRequestRaw').mockResolvedValueOnce({
      status: 503,
      body: { ...searchFixture, message: 'Wikimedia is rate-limiting this server.', retry_after_seconds: 120 },
    });

    const { result } = renderHook(() => useCreateSearch(), { wrapper });

    await act(async () => {
      await result.current.mutateAsync(input);
    });

    await waitFor(() => expect(result.current.data?.outcome).toBe('blocked'));
    expect(result.current.data?.retryAfterSeconds).toBe(120);
    expect(result.current.data?.search.id).toBe(searchFixture.data.id);
  });

  it('reports a failed run as failed', async () => {
    jest.spyOn(client, 'apiRequestRaw').mockResolvedValueOnce({
      status: 502,
      body: { ...searchFixture, message: 'The search failed.' },
    });

    const { result } = renderHook(() => useCreateSearch(), { wrapper });

    await act(async () => {
      await result.current.mutateAsync(input);
    });

    await waitFor(() => expect(result.current.data?.outcome).toBe('failed'));
  });
});
