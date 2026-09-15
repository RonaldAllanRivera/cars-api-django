import type { InfiniteData } from '@tanstack/react-query';
import { render } from '@testing-library/react-native';
import { Text } from 'react-native';

import type { CursorPage, Image as CarImage } from '@/api/schemas';
import { InfiniteGrid } from '../InfiniteGrid';

const page = (items: CarImage[]) => ({
  pages: [
    {
      data: items,
      links: { first: null, last: null, prev: null, next: null },
      meta: { path: '/images', per_page: 15, next_cursor: null, prev_cursor: null },
    },
  ],
  pageParams: [null],
});

// Widened deliberately: an inferred literal would fix `data` to undefined and
// `error` to null, so the error cases below could not be expressed.
const base = {
  data: undefined as InfiniteData<CursorPage<CarImage>> | undefined,
  isLoading: false,
  isRefetching: false,
  isError: false,
  error: null as unknown,
  hasNextPage: false,
  isFetchingNextPage: false,
  fetchNextPage: jest.fn(),
  refetch: jest.fn(),
};

const grid = (query: typeof base) =>
  render(
    <InfiniteGrid
      query={query}
      keyExtractor={(item: CarImage) => String(item.id)}
      renderItem={(item: CarImage) => <Text>{item.title}</Text>}
      emptyTitle="No images match"
      emptyHint="Try a different make, or run a new search."
    />,
  );

describe('InfiniteGrid', () => {
  it('shows the empty state when the fetch succeeded with no rows', () => {
    const { getByText, queryByText } = grid({ ...base, data: page([]) });

    expect(getByText('No images match')).toBeTruthy();
    expect(queryByText(/went wrong/i)).toBeNull();
  });

  it('shows the error instead of the empty state when the fetch failed', () => {
    // React Query clears isLoading once a query errors, so without an explicit
    // error branch a 500 renders as "No images match" - a swallowed failure
    // the user reads as "there is nothing here".
    const { getByText, queryByText } = grid({
      ...base,
      isError: true,
      error: new Error('The request failed (500).'),
    });

    expect(getByText('The request failed (500).')).toBeTruthy();
    expect(queryByText('No images match')).toBeNull();
  });

  it('falls back to a generic message when the error is not an Error', () => {
    const { getByText } = grid({ ...base, isError: true, error: 'boom' });

    expect(getByText('Something went wrong.')).toBeTruthy();
  });

  it('shows skeletons rather than a bare spinner on first load', () => {
    const { getByLabelText, queryByText } = grid({ ...base, isLoading: true });

    expect(getByLabelText('Loading')).toBeTruthy();
    // The empty state must not flash before the first page arrives - the two
    // branches are mutually exclusive and the order matters.
    expect(queryByText('No images match')).toBeNull();
  });

  it('fills the viewport with skeletons rather than showing one', () => {
    const { getAllByTestId } = grid({ ...base, isLoading: true });

    // Skeletons are hidden from assistive tech, so the query has to opt in;
    // RNTL's default includeHiddenElements: false would find none of them.
    expect(getAllByTestId('skeleton', { includeHiddenElements: true }).length).toBeGreaterThanOrEqual(
      4,
    );
  });
});
