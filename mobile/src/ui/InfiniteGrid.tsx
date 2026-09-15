import type { InfiniteData } from '@tanstack/react-query';
import type { ReactElement } from 'react';
import { ActivityIndicator, FlatList, RefreshControl } from 'react-native';

import type { CursorPage } from '@/api/schemas';
import { color } from '@/theme/tokens';
import { EmptyState } from './EmptyState';
import { ErrorBanner } from './ErrorBanner';
import { SkeletonGrid } from './Skeleton';

interface Props<T> {
  query: {
    data?: InfiniteData<CursorPage<T>>;
    isLoading: boolean;
    isRefetching: boolean;
    // Without these a failed fetch is indistinguishable from an empty result:
    // React Query clears isLoading once a query errors, so the list would fall
    // through to ListEmptyComponent and tell the user "nothing matched".
    isError: boolean;
    error: unknown;
    hasNextPage: boolean;
    isFetchingNextPage: boolean;
    fetchNextPage: () => void;
    refetch: () => void;
  };
  renderItem: (item: T) => ReactElement;
  keyExtractor: (item: T) => string;
  numColumns?: number;
  emptyTitle: string;
  emptyHint?: string;
  /** An empty screen is an invitation to act, where there is an act to offer. */
  emptyAction?: { label: string; onPress: () => void };
}

export function InfiniteGrid<T>({
  query,
  renderItem,
  keyExtractor,
  numColumns = 1,
  emptyTitle,
  emptyHint,
  emptyAction,
}: Props<T>) {
  const items = query.data?.pages.flatMap((page) => page.data) ?? [];

  if (query.isLoading) {
    // Shaped like the content it replaces, so the layout does not jump when
    // the first page lands. Six fills a phone screen at either column count.
    return <SkeletonGrid count={6} numColumns={numColumns} />;
  }

  return (
    <FlatList
      data={items}
      numColumns={numColumns}
      // A multi-column list needs the gap or the cards touch.
      columnWrapperStyle={numColumns > 1 ? { gap: 12 } : undefined}
      keyExtractor={keyExtractor}
      renderItem={({ item }) => renderItem(item)}
      onEndReachedThreshold={0.5}
      onEndReached={() => {
        if (query.hasNextPage && !query.isFetchingNextPage) query.fetchNextPage();
      }}
      refreshControl={
        <RefreshControl
          refreshing={query.isRefetching}
          onRefresh={query.refetch}
          tintColor={color.accentText}
        />
      }
      ListEmptyComponent={
        query.isError ? (
          <ErrorBanner
            message={
              query.error instanceof Error ? query.error.message : 'Something went wrong.'
            }
          />
        ) : (
          <EmptyState title={emptyTitle} hint={emptyHint} action={emptyAction} />
        )
      }
      ListFooterComponent={
        query.isFetchingNextPage ? (
          <ActivityIndicator className="my-4" color={color.accentText} />
        ) : null
      }
    />
  );
}
