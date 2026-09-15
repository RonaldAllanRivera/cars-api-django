import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react-native';
import type { ReactNode } from 'react';

import errorsFixture from '@/api/__fixtures__/errors.json';
import healthFixture from '@/api/__fixtures__/health.json';
import * as client from '@/api/client';
import Health from '../index';

jest.mock('@/auth/AuthContext', () => ({
  useAuth: () => ({ status: 'authenticated', user: null, signIn: jest.fn(), signOut: jest.fn() }),
}));

const wrapper = ({ children }: { children: ReactNode }) => {
  // gcTime: 0 disposes the cache (and its GC timer) as soon as nothing
  // observes it, instead of leaving it scheduled for the default 5 minutes.
  // Without this the timer outlives the test as a real handle and Jest
  // hangs past its normal exit - `--detectOpenHandles` catches it directly.
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
};

describe('<Health />', () => {
  beforeEach(() => jest.restoreAllMocks());

  it('renders the counters and the error log', async () => {
    jest.spyOn(client, 'apiRequest').mockImplementation((path) =>
      Promise.resolve(path === '/health/summary' ? healthFixture : errorsFixture),
    );

    render(<Health />, { wrapper });

    await waitFor(() => expect(screen.getByText('completed')).toBeTruthy());

    // Assert the count alongside its label, scoped to that one tile - not
    // just that "completed" and "1" each appear somewhere on the screen.
    // getByText('completed') alone would still pass if a status/count
    // mapping bug swapped values between statuses.
    // Two levels up: `.parent` of the matched host text is RN's own `Text`
    // composite, and its `.parent` is the `StatTile`'s enclosing `View` -
    // the tile that also holds the sibling `<Text>{value}</Text>`.
    const completedTile = screen.getByText('completed').parent?.parent;
    expect(completedTile).not.toBeNull();
    expect(within(completedTile!).getByText('1')).toBeTruthy();

    // getByText on the fixture's own message text, not a query for "search
    // run": the humanized "Search run" label also renders in the "Errors by
    // context, 7d" counters (driven by useHealth alone), so a query that
    // only checks for that text passes even if the error log never renders.
    // This message string is unique to the logged event, so it only exists
    // if useErrors actually resolved and the log rendered it.
    expect(screen.getByText('The search run failed.')).toBeTruthy();
  });

  it('does not call the log empty while it is still loading', async () => {
    // The empty-log line is guarded by a compound condition
    // (`!isLoading && !isError && length === 0`), and the tempting tidy-up is
    // to reduce it to `events.length === 0`. That reads "nothing logged" over
    // a log that has not arrived yet, and over one that failed to arrive at
    // all - the same swallowed-failure shape already fixed in InfiniteGrid.
    jest
      .spyOn(client, 'apiRequest')
      .mockImplementation((path) =>
        path === '/health/summary' ? Promise.resolve(healthFixture) : new Promise(() => {}),
      );

    render(<Health />, { wrapper });

    await waitFor(() => expect(screen.getByText('completed')).toBeTruthy());
    expect(screen.queryByText('Nothing logged.')).toBeNull();
  });

  it('shows the failure instead of calling the log empty when it cannot be read', async () => {
    jest
      .spyOn(client, 'apiRequest')
      .mockImplementation((path) =>
        path === '/health/summary'
          ? Promise.resolve(healthFixture)
          : Promise.reject(new client.ApiError(500, 'The error log is unavailable (500).')),
      );

    render(<Health />, { wrapper });

    await waitFor(() =>
      expect(screen.getByText('The error log is unavailable (500).')).toBeTruthy(),
    );
    expect(screen.queryByText('Nothing logged.')).toBeNull();
  });

  it('says so when the log really is empty', async () => {
    jest.spyOn(client, 'apiRequest').mockImplementation((path) =>
      Promise.resolve(
        path === '/health/summary'
          ? healthFixture
          : { ...errorsFixture, data: [] },
      ),
    );

    render(<Health />, { wrapper });

    await waitFor(() => expect(screen.getByText('Nothing logged.')).toBeTruthy());
  });
});
