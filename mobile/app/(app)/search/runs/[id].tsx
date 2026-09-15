import { useLocalSearchParams } from 'expo-router';
import { Text, View } from 'react-native';

import { useSearchImages } from '@/api/hooks/useImages';
import { useSearch } from '@/api/hooks/useSearches';
import { ErrorBanner } from '@/ui/ErrorBanner';
import { ImageCard } from '@/ui/ImageCard';
import { InfiniteGrid } from '@/ui/InfiniteGrid';
import { PageTitle } from '@/ui/PageTitle';
import { Screen } from '@/ui/Screen';
import { Skeleton } from '@/ui/Skeleton';
import { StatusBadge } from '@/ui/StatusBadge';

export default function RunDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const searchId = Number(id);
  const search = useSearch(searchId);
  const images = useSearchImages(searchId);

  if (search.isLoading) {
    return (
      <Screen>
        <PageTitle title="Run - Cars Images" />
        <Skeleton height={96} />
      </Screen>
    );
  }

  // Matches search/[id].tsx: a failed lookup must say so rather than render a
  // headerless screen over an empty grid.
  if (search.isError) {
    return (
      <Screen>
        <PageTitle title="Run - Cars Images" />
        <ErrorBanner
          message={search.error instanceof Error ? search.error.message : 'Not found.'}
        />
      </Screen>
    );
  }

  return (
    <Screen>
      <PageTitle title="Run - Cars Images" />
      {search.data ? (
        <View className="mb-3">
          <Text className="text-section text-text">
            {search.data.make} {search.data.model ?? ''} · {search.data.from_year}–
            {search.data.to_year}
          </Text>
          <View className="mt-1 flex-row items-center gap-2">
            <StatusBadge status={search.data.status} />
            <Text className="text-meta text-text-secondary">
              {search.data.images_count ?? 0} images
            </Text>
          </View>
          {search.data.status === 'failed' ? (
            <Text className="mt-2 text-meta text-danger-text">
              This run failed. The reason is on the Health tab&apos;s error log.
            </Text>
          ) : null}
        </View>
      ) : null}

      <InfiniteGrid
        query={images}
        numColumns={2}
        keyExtractor={(image) => String(image.id)}
        renderItem={(image) => (
          <ImageCard
            image={image}
            href={{ pathname: '/(app)/search/[id]', params: { id: image.id } }}
          />
        )}
        emptyTitle="This run returned no images"
      />
    </Screen>
  );
}
