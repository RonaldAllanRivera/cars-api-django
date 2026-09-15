import { ScrollView, Text, View } from 'react-native';

import { useErrors } from '@/api/hooks/useErrors';
import { useHealth } from '@/api/hooks/useHealth';
import { useAuth } from '@/auth/AuthContext';
import { Button } from '@/ui/Button';
import { ErrorBanner } from '@/ui/ErrorBanner';
import { PageTitle } from '@/ui/PageTitle';
import { Screen } from '@/ui/Screen';
import { SectionHeading } from '@/ui/SectionHeading';
import { Skeleton, SkeletonGrid } from '@/ui/Skeleton';
import { StatTile } from '@/ui/StatTile';

/** Mirrors ErrorEvent::contexts() - keys to the labels Filament shows. */
const CONTEXT_LABELS: Record<string, string> = {
  csv_upload: 'CSV upload',
  csv_row: 'CSV row',
  search_run: 'Search run',
  image_download: 'Image download',
  wikimedia_block: 'Wikimedia block',
};

export default function Health() {
  const health = useHealth();
  const errors = useErrors();
  const { signOut } = useAuth();

  const events = errors.data?.pages.flatMap((page) => page.data) ?? [];

  return (
    <Screen>
      <PageTitle title="Pipeline health - Cars Images" />
      <ScrollView>
        {health.isError ? (
          <ErrorBanner
            message={health.error instanceof Error ? health.error.message : 'Health unavailable.'}
          />
        ) : null}

        {health.isLoading ? <SkeletonGrid count={4} numColumns={2} aspectRatio={2.4} /> : null}

        {health.data ? (
          <>
            <SectionHeading title="Runs" />
            <View className="mb-6 flex-row flex-wrap gap-2">
              {Object.entries(health.data.searches_by_status).map(([status, count]) => (
                <StatTile key={status} label={status} value={count} />
              ))}
            </View>

            <SectionHeading title="Recent" />
            <View className="mb-6 flex-row flex-wrap gap-2">
              <StatTile label="errors, 24h" value={health.data.errors_last_24h} />
              <StatTile label="images, 7d" value={health.data.images_last_7d} />
            </View>

            <SectionHeading title="Errors by context, 7 days" />
            <View className="mb-6 flex-row flex-wrap gap-2">
              {Object.entries(health.data.errors_by_context_last_7d).map(([context, count]) => (
                <StatTile key={context} label={CONTEXT_LABELS[context] ?? context} value={count} />
              ))}
            </View>
          </>
        ) : null}

        <SectionHeading title="Error log" />

        {errors.isError ? (
          <ErrorBanner
            message={errors.error instanceof Error ? errors.error.message : 'Error log unavailable.'}
          />
        ) : null}

        {errors.isLoading ? <Skeleton height={72} /> : null}

        {/* The compound guard is deliberate and has a test of its own: reduced
            to `events.length === 0` this reads "nothing logged" over a log
            that has not arrived yet, and over one that failed to arrive. */}
        {!errors.isLoading && !errors.isError && events.length === 0 ? (
          <Text className="mb-6 text-meta text-text-secondary">Nothing logged.</Text>
        ) : (
          events.map((event) => (
            <View key={event.id} className="mb-2 rounded-surface bg-surface-raised p-3">
              <View className="flex-row justify-between">
                <Text className="text-micro text-accent-text">
                  {CONTEXT_LABELS[event.context] ?? event.context}
                </Text>
                <Text className="text-micro text-text-muted">{event.occurred_at ?? ''}</Text>
              </View>
              <Text className="mt-1 text-body text-text">{event.message ?? '(no message)'}</Text>
              {event.exception_message ? (
                <Text className="mt-1 text-meta text-text-secondary" numberOfLines={2}>
                  {event.exception_class}: {event.exception_message}
                </Text>
              ) : null}
            </View>
          ))
        )}

        {errors.hasNextPage ? (
          <View className="mt-2">
            <Button
              label="Load more"
              variant="secondary"
              pending={errors.isFetchingNextPage}
              onPress={() => errors.fetchNextPage()}
            />
          </View>
        ) : null}

        <View className="my-8">
          <Button label="Sign out" variant="ghost" onPress={() => void signOut()} />
        </View>
      </ScrollView>
    </Screen>
  );
}
