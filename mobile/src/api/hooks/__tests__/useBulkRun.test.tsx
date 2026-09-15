/** @jest-environment jsdom */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react-native';
import type { ReactNode } from 'react';

import * as client from '@/api/client';
import { useBulkRun } from '../useBulkRun';

const wrapper = ({ children }: { children: ReactNode }) => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { gcTime: 0 } },
  });

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
};

const chunk = (over: Record<string, unknown> = {}) => ({
  outcomes: [{ id: 1, make: 'Honda', model: 'Civic', from_year: 1998, outcome: 'completed' }],
  ran_seconds: 1,
  remaining: 0,
  blocked: null,
  ...over,
});

describe('useBulkRun', () => {
  beforeEach(() => jest.restoreAllMocks());

  it('keeps asking until nothing remains', async () => {
    const spy = jest
      .spyOn(client, 'apiRequest')
      .mockResolvedValueOnce(chunk({ remaining: 1 }))
      .mockResolvedValueOnce(chunk({ remaining: 0 }));

    const { result } = renderHook(() => useBulkRun(12), { wrapper });

    act(() => result.current.start(2));

    await waitFor(() => expect(result.current.status).toBe('finished'));
    expect(spy).toHaveBeenCalledTimes(2);
    expect(result.current.processed).toBe(2);
  });

  it('stops on a block rather than retrying', async () => {
    // A block means stop asking. Retrying is how a temporary block becomes a
    // longer one.
    const spy = jest
      .spyOn(client, 'apiRequest')
      .mockResolvedValue(chunk({ remaining: 5, blocked: { status: 429, retry_after_seconds: 600 } }));

    const { result } = renderHook(() => useBulkRun(12), { wrapper });

    act(() => result.current.start(6));

    await waitFor(() => expect(result.current.status).toBe('blocked'));
    expect(spy).toHaveBeenCalledTimes(1);
    expect(result.current.blocked?.retry_after_seconds).toBe(600);
  });

  it('counts failures separately from successes', async () => {
    jest.spyOn(client, 'apiRequest').mockResolvedValueOnce(
      chunk({
        outcomes: [
          { id: 1, make: 'A', model: null, from_year: 1998, outcome: 'completed' },
          { id: 2, make: 'B', model: null, from_year: 1999, outcome: 'failed' },
        ],
        remaining: 0,
      }),
    );

    const { result } = renderHook(() => useBulkRun(12), { wrapper });

    act(() => result.current.start(2));

    await waitFor(() => expect(result.current.status).toBe('finished'));
    expect(result.current.processed).toBe(1);
    expect(result.current.failed).toBe(1);
  });

  it('stops asking when paused', async () => {
    const spy = jest.spyOn(client, 'apiRequest').mockResolvedValue(chunk({ remaining: 10 }));

    const { result } = renderHook(() => useBulkRun(12), { wrapper });

    act(() => result.current.start(11));
    await waitFor(() => expect(spy).toHaveBeenCalled());
    act(() => result.current.pause());

    await waitFor(() => expect(result.current.status).toBe('paused'));
    const callsAtPause = spy.mock.calls.length;

    // Nothing further goes out. A chunk already in flight still finishes - the
    // server cannot be interrupted - but no new one is sent.
    await new Promise((resolve) => setTimeout(resolve, 60));
    expect(spy.mock.calls.length).toBe(callsAtPause);
  });

  it('surfaces the cars in the last chunk', async () => {
    jest.spyOn(client, 'apiRequest').mockResolvedValueOnce(chunk({ remaining: 0 }));

    const { result } = renderHook(() => useBulkRun(12), { wrapper });

    act(() => result.current.start(1));

    await waitFor(() => expect(result.current.status).toBe('finished'));
    expect(result.current.lastOutcomes[0]?.make).toBe('Honda');
  });
});
