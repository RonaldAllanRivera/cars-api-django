import { Link } from 'expo-router';
import { useState } from 'react';
import { Pressable, Text, View } from 'react-native';

import { useSearches } from '@/api/hooks/useSearches';
import type { SearchStatus } from '@/api/schemas';
import { InfiniteGrid } from '@/ui/InfiniteGrid';
import { PageTitle } from '@/ui/PageTitle';
import { Screen } from '@/ui/Screen';
import { StatusBadge } from '@/ui/StatusBadge';

const STATUSES: (SearchStatus | 'all')[] = ['all', 'pending', 'running', 'completed', 'failed'];

export default function Runs() {
  const [status, setStatus] = useState<SearchStatus | 'all'>('all');
  // source: 'adhoc' - runs started from the form on this tab. CSV-derived
  // queries live under Pipeline, which is the split the panel already makes
  // between CarSearchResource and SearchQueryResource.
  const query = useSearches({
    source: 'adhoc',
    ...(status === 'all' ? {} : { status }),
  });

  return (
    <Screen>
      <PageTitle title="Runs - Cars Images" />
      <View className="mb-3 flex-row flex-wrap gap-2">
        {STATUSES.map((option) => (
          <Pressable
            key={option}
            accessibilityRole="button"
            accessibilityState={{ selected: status === option }}
            className={`rounded-pill px-3 py-1 ${
              status === option ? 'bg-accent' : 'bg-surface-sunken'
            }`}
            onPress={() => setStatus(option)}
          >
            <Text
              className={`text-micro ${
                status === option ? 'text-accent-fg' : 'text-text-secondary'
              }`}
            >
              {option}
            </Text>
          </Pressable>
        ))}
      </View>

      <InfiniteGrid
        query={query}
        keyExtractor={(search) => String(search.id)}
        emptyTitle="No runs yet"
        emptyHint="Start one from the Search tab."
        renderItem={(search) => (
          <Link href={{ pathname: '/(app)/search/runs/[id]', params: { id: search.id } }} asChild>
            <Pressable className="mb-2 rounded-surface bg-surface-raised p-3 active:opacity-80">
              <Text className="text-body font-medium text-text">
                {search.make} {search.model ?? ''} · {search.from_year}–{search.to_year}
              </Text>
              <View className="mt-1 flex-row items-center gap-2">
                <StatusBadge status={search.status} />
                <Text className="text-meta text-text-secondary">
                  {search.images_count ?? 0} images
                </Text>
              </View>
            </Pressable>
          </Link>
        )}
      />
    </Screen>
  );
}
