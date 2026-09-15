<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue';
import { onBeforeRouteLeave, RouterLink } from 'vue-router';

import { errorMessage } from '@/api/client';
import { useBulkRun } from '@/api/composables/useBulkRun';
import { useImport } from '@/api/composables/useImports';
import { useSearches } from '@/api/composables/useSearches';
import type { CoverageFilter } from '@/api/queryKeys';
import { useAuth } from '@/auth/auth';
import BaseButton from '@/components/BaseButton.vue';
import CoveragePanel from '@/components/CoveragePanel.vue';
import EmptyState from '@/components/EmptyState.vue';
import ErrorBanner from '@/components/ErrorBanner.vue';
import LoadMore from '@/components/LoadMore.vue';
import PageHeader from '@/components/PageHeader.vue';
import RunProgress from '@/components/RunProgress.vue';
import SearchRow from '@/components/SearchRow.vue';
import SkeletonBlock from '@/components/SkeletonBlock.vue';
import { useDocumentTitle } from '@/composables/useDocumentTitle';
import { showToast } from '@/composables/useToast';
import { formatDateTime, humanSeconds, plural } from '@/format/time';

const props = defineProps<{ id: number }>();

const { can } = useAuth();
const csvImport = useImport(() => props.id);
const run = reactive(useBulkRun(() => props.id));

// The tile the user picked is also the query-list filter: "23 not run yet" is
// both a count and the list of those 23.
const coverage = ref<CoverageFilter | null>(null);
const queries = useSearches(() => ({
  source: 'csv' as const,
  csv_import_id: props.id,
  coverage: coverage.value ?? undefined,
}));
const queryList = computed(() => queries.data.value?.pages.flatMap((page) => page.data) ?? []);

const data = computed(() => csvImport.data.value);
useDocumentTitle(() => data.value?.original_filename ?? 'Import');

const headerMeta = computed(() => {
  const current = data.value;
  if (!current) return '';

  const counts = [
    `${plural(current.unique_combos ?? 0, 'unique query', 'unique queries')} from ${plural(current.total_rows ?? 0, 'row')}`,
    current.duplicates_skipped ? `${current.duplicates_skipped} duplicates skipped` : null,
  ]
    .filter(Boolean)
    .join(', ');
  const who = [current.importer_name ? `Uploaded by ${current.importer_name}` : null, formatDateTime(current.created_at)]
    .filter(Boolean)
    .join(', ');

  return who ? `${counts}. ${who}` : counts;
});

const notRun = computed(() => data.value?.coverage?.not_run ?? 0);
const canRun = computed(() => can('search:run'));
const showRunButton = computed(
  () => canRun.value && notRun.value > 0 && (run.status === 'idle' || run.status === 'finished'),
);

watch(
  () => run.status,
  (status, previous) => {
    if (status === 'finished' && previous === 'running') {
      showToast(
        `Run complete: ${plural(run.processed, 'query', 'queries')} searched${run.failed ? `, ${run.failed} failed` : ''}.`,
        run.failed ? 'info' : 'success',
      );
    }
  },
);

// Leaving the page stops the loop. Nothing is lost - the rows are the queue -
// but the user should know it is not still going in the background.
onBeforeRouteLeave(() => {
  if (run.status === 'running') {
    showToast('The run stopped when you left the import. Open it again to resume.', 'info');
  }
});

// Leaving mid-run stops it (nothing is lost, but it does stop), so say so.
const warnBeforeUnload = (event: BeforeUnloadEvent) => {
  if (run.status === 'running') event.preventDefault();
};
window.addEventListener('beforeunload', warnBeforeUnload);
onBeforeUnmount(() => window.removeEventListener('beforeunload', warnBeforeUnload));
</script>

<template>
  <div>
    <div v-if="csvImport.isPending.value" class="space-y-4" aria-label="Loading import">
      <SkeletonBlock class="h-9 w-80 rounded" />
      <SkeletonBlock class="h-28" />
      <SkeletonBlock class="h-40" />
    </div>

    <template v-else-if="csvImport.isError.value || !data">
      <PageHeader title="Import" :back="{ to: { name: 'pipeline' }, label: 'Pipeline' }" />
      <ErrorBanner :message="errorMessage(csvImport.error.value, 'This import could not be loaded.')" :retry="() => csvImport.refetch()" />
    </template>

    <template v-else>
      <PageHeader :title="data.original_filename" :back="{ to: { name: 'pipeline' }, label: 'Pipeline' }">
        <template #meta>
          <p class="mt-2 text-meta text-ink-2">{{ headerMeta }}</p>
        </template>
        <template #actions>
          <RouterLink
            :to="{ name: 'library', query: { import: data.id } }"
            class="focus-ring inline-flex h-10 items-center rounded-control border border-line-strong bg-sunken px-4 font-semibold text-ink hover:border-ink-3"
          >
            View images
          </RouterLink>
          <BaseButton v-if="showRunButton" icon="play" @click="run.start(notRun)">
            Run {{ plural(notRun, 'query', 'queries') }}
          </BaseButton>
        </template>
      </PageHeader>

      <div class="flex flex-col gap-6">
        <CoveragePanel v-if="data.coverage" :coverage="data.coverage" :selected="coverage" @select="coverage = $event" />
        <p v-else class="text-body text-ink-2">This import has no searches yet.</p>

        <p v-if="!canRun && notRun > 0" class="text-meta text-ink-3">
          Your account cannot start runs, so the {{ notRun }} queries not yet run stay queued.
        </p>
        <p v-else-if="showRunButton && run.status === 'idle'" class="text-meta text-ink-3">
          At the observed pace of about two seconds a query, this takes roughly {{ humanSeconds(notRun * 2) }}.
          You can pause at any time.
        </p>

        <RunProgress :run="run" />

        <section aria-labelledby="queries-heading">
          <div class="mb-3 flex flex-wrap items-baseline justify-between gap-2">
            <h2 id="queries-heading" class="text-section font-semibold text-ink">Queries</h2>
            <button
              v-if="coverage"
              type="button"
              class="focus-ring rounded-control text-meta font-semibold text-accent-text hover:underline"
              @click="coverage = null"
            >
              Show all queries
            </button>
          </div>

          <ErrorBanner v-if="queries.isError.value" :message="errorMessage(queries.error.value)" :retry="() => queries.refetch()" />
          <div v-else-if="queries.isPending.value" class="flex flex-col gap-2" aria-label="Loading queries">
            <SkeletonBlock v-for="n in 5" :key="n" class="h-14" />
          </div>
          <EmptyState
            v-else-if="queryList.length === 0"
            :title="coverage ? 'No queries in this group' : 'This import has no queries'"
            :hint="coverage ? 'Pick the highlighted tile again, or show all queries.' : undefined"
          />
          <template v-else>
            <ul class="grid gap-x-2 rounded-surface border border-line bg-raised p-1.5 md:grid-cols-2">
              <li v-for="search in queryList" :key="search.id">
                <SearchRow :search="search" />
              </li>
            </ul>
            <LoadMore
              :has-next-page="queries.hasNextPage.value"
              :is-fetching-next-page="queries.isFetchingNextPage.value"
              :fetch-next-page="queries.fetchNextPage"
            />
          </template>
        </section>
      </div>
    </template>
  </div>
</template>
