import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react-native';
import type { ReactNode } from 'react';

import searchFixture from '@/api/__fixtures__/search-create.json';
import * as client from '@/api/client';
import { MAX_YEAR_SPAN } from '@/api/hooks/useCreateSearch';
import SearchForm from '../index';

// The screen only ever calls `router` from a press handler, so a plain object
// is enough - and it keeps the test off react-navigation entirely.
jest.mock('expo-router', () => ({ router: { push: jest.fn(), replace: jest.fn() } }));

const wrapper = ({ children }: { children: ReactNode }) => {
  // gcTime: 0 on both caches - the mutation cache keeps its own GC timer, and
  // a timer left scheduled outlives the test as a real handle.
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { gcTime: 0 } },
  });

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
};

// By label, not by placeholder. Every field carries a real label now, and a
// label is what the field is; a placeholder is a disposable hint that can be
// reworded without the form changing meaning.
const fillIn = (make: string, fromYear: string, toYear: string) => {
  fireEvent.changeText(screen.getByLabelText('Make'), make);
  fireEvent.changeText(screen.getByLabelText('From year'), fromYear);
  fireEvent.changeText(screen.getByLabelText('To year'), toYear);
  fireEvent.press(screen.getByLabelText('Run search'));
};

describe('<SearchForm /> cap enforcement', () => {
  beforeEach(() => jest.restoreAllMocks());

  it('refuses a year range wider than the cap without asking the API', async () => {
    // The cap is a global constraint of this client: the search runs inline
    // inside the request, so the user has to see the limit before the wait
    // rather than after a round trip that 422s.
    const request = jest.spyOn(client, 'apiRequestRaw');

    render(<SearchForm />, { wrapper });
    fillIn('Toyota', '1990', '2000');

    await waitFor(() =>
      expect(
        screen.getByText(
          `The year range may span at most ${MAX_YEAR_SPAN} years, because the search runs inside the request.`,
        ),
      ).toBeTruthy(),
    );
    expect(request).not.toHaveBeenCalled();
  });

  it('submits a range inside the cap', async () => {
    // The control for the test above: without it, a submit button that never
    // fires at all would pass the "did not call the API" assertion too.
    const request = jest
      .spyOn(client, 'apiRequestRaw')
      .mockResolvedValue({ status: 201, body: searchFixture });

    render(<SearchForm />, { wrapper });
    fillIn('Toyota', '1997', '1999');

    await waitFor(() => expect(request).toHaveBeenCalledTimes(1));
    expect(request.mock.calls[0]?.[0]).toBe('/searches');
    expect(screen.queryByText(/may span at most/)).toBeNull();
  });
});
