import { useKeepAwake } from 'expo-keep-awake';
import { Link, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Pressable, Text, View } from 'react-native';

import { useBulkRun } from '@/api/hooks/useBulkRun';
import { useImport } from '@/api/hooks/useImports';
import { useSearches } from '@/api/hooks/useSearches';
import type { Search } from '@/api/schemas';
import { CoveragePanel } from '@/ui/CoveragePanel';
import type { CoverageFilter } from '@/ui/CoveragePanel';
import { Button } from '@/ui/Button';
import { ErrorBanner } from '@/ui/ErrorBanner';
import { InfiniteGrid } from '@/ui/InfiniteGrid';
import { PageTitle } from '@/ui/PageTitle';
import { RunProgress } from '@/ui/RunProgress';
import { Screen } from '@/ui/Screen';
import { Skeleton } from '@/ui/Skeleton';
import { StatusBadge } from '@/ui/StatusBadge';

/**
 * Holds the screen on for as long as it is mounted, and is mounted only while
 * a run is active. A conditional `useKeepAwake()` is not possible - hooks
 * cannot be called conditionally - so the condition lives in whether this
 * renders at all.
 */
function KeepScreenAwake() {
  useKeepAwake();

  return null;
}

export default function ImportDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const importId = Number(id);

  // The coverage tile the user tapped, which is also the queries filter. One
  // piece of state, because they are the same choice: "23 not run yet" is both
  // a count and the list of those 23.
  const [coverage, setCoverage] = useState<CoverageFilter | null>(null);

  const csvImport = useImport(importId);
  const run = useBulkRun(importId);
  const queries = useSearches({ source: 'csv', csv_import_id: importId, ...(coverage ? { coverage } : {}) });

  if (csvImport.isLoading) {
    return (
      <Screen>
        <PageTitle title="Import - Cars Images" />
        <Skeleton height={140} />
      </Screen>
    );
  }

  if (csvImport.isError || !csvImport.data) {
    return (
      <Screen>
        <PageTitle title="Import - Cars Images" />
        <ErrorBanner
          message={csvImport.error instanceof Error ? csvImport.error.message : 'Not found.'}
        />
      </Screen>
    );
  }

  const data = csvImport.data;
  const notRun = data.coverage?.not_run ?? 0;

  return (
    <Screen>
      <PageTitle title="Import - Cars Images" />

      <Text className="text-section text-text" numberOfLines={1}>
        {data.original_filename}
      </Text>
      <Text className="mb-4 text-meta text-text-muted">
        {data.unique_combos ?? 0} queries
        {data.duplicates_skipped ? `, ${data.duplicates_skipped} duplicates skipped` : ''}
      </Text>

      <CoveragePanel coverage={data.coverage ?? null} selected={coverage} onSelect={setCoverage} />

      {run.status === 'running' || run.status === 'paused' ? <KeepScreenAwake /> : null}

      <RunProgress
        status={run.status}
        processed={run.processed}
        failed={run.failed}
        total={run.total}
        secondsRemaining={run.secondsRemaining}
        blocked={run.blocked}
        onPause={run.pause}
        onResume={run.resume}
      />

      {/* Offered only when there is work: a Run button over a finished import
          promises something the endpoint would answer with an empty chunk. */}
      {notRun > 0 && (run.status === 'idle' || run.status === 'finished' || run.status === 'blocked') ? (
        <View className="mb-6">
          <Button
            label={`Run ${notRun} ${notRun === 1 ? 'query' : 'queries'}`}
            size="lg"
            onPress={() => run.start(notRun)}
          />
        </View>
      ) : null}

      <InfiniteGrid
        query={queries}
        keyExtractor={(search) => String(search.id)}
        emptyTitle={coverage ? 'No queries match' : 'This import has no queries'}
        emptyHint={coverage ? 'Tap the highlighted count again to see them all.' : undefined}
        renderItem={(search: Search) => (
          <Link
            href={{ pathname: '/(app)/search/runs/[id]', params: { id: search.id } }}
            asChild
          >
            <Pressable className="mb-2 rounded-surface bg-surface-raised p-3 active:opacity-80">
              <Text className="text-body font-medium text-text" numberOfLines={1}>
                {search.make} {search.model ?? ''} · {search.from_year}
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
