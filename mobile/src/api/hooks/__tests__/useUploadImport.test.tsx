/** @jest-environment jsdom */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react-native';
import type { ReactNode } from 'react';

import importFixture from '@/api/__fixtures__/import.json';
import * as client from '@/api/client';
import { useUploadImport } from '../useUploadImport';

const wrapper = ({ children }: { children: ReactNode }) => {
  // mutations: { gcTime: 0 } separately - the `queries` default does not reach
  // the MutationCache, and its timer would outlive the test as a real handle.
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { gcTime: 0 } },
  });

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
};

describe('useUploadImport', () => {
  beforeEach(() => jest.restoreAllMocks());

  it('sends the file as multipart, not JSON', async () => {
    // A JSON body arrives with no file and 422s on csv_file, which reads to
    // the user as "your CSV is invalid" rather than "the app sent it wrong".
    const spy = jest.spyOn(client, 'apiRequest').mockResolvedValue(importFixture);

    const { result } = renderHook(() => useUploadImport(), { wrapper });

    result.current.mutate({ uri: 'file:///tmp/q.csv', name: 'q.csv', mimeType: 'text/csv' });

    await waitFor(() => expect(spy).toHaveBeenCalled());

    const [path, options] = spy.mock.calls[0] ?? [];
    expect(path).toBe('/imports');
    expect(options?.method).toBe('POST');
    expect(options?.body).toBeInstanceOf(FormData);
  });

  it('names the part csv_file, which is what the endpoint validates', async () => {
    const spy = jest.spyOn(client, 'apiRequest').mockResolvedValue(importFixture);

    const { result } = renderHook(() => useUploadImport(), { wrapper });

    result.current.mutate({ uri: 'file:///tmp/q.csv', name: 'q.csv' });

    await waitFor(() => expect(spy).toHaveBeenCalled());

    const body = spy.mock.calls[0]?.[1]?.body as FormData;
    expect(body.get('csv_file')).not.toBeNull();
  });
});
