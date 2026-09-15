<script setup lang="ts">
import { computed, ref } from 'vue';
import { RouterLink } from 'vue-router';

import { errorMessage } from '@/api/client';
import { useErrors, useHealth } from '@/api/composables/useHealth';
import type { ErrorContext, ErrorSeverity, SearchStatus } from '@/api/schemas';
import ChipGroup from '@/components/ChipGroup.vue';
import ContextBars from '@/components/ContextBars.vue';
import EmptyState from '@/components/EmptyState.vue';
import ErrorBanner from '@/components/ErrorBanner.vue';
import LoadMore from '@/components/LoadMore.vue';
import PageHeader from '@/components/PageHeader.vue';
import SelectField from '@/components/SelectField.vue';
import SkeletonBlock from '@/components/SkeletonBlock.vue';
import StatTile from '@/components/StatTile.vue';
import StatusBadge from '@/components/StatusBadge.vue';
import { useDocumentTitle } from '@/composables/useDocumentTitle';
import { CONTEXT_LABELS } from '@/format/labels';
import { formatDateTime, timeAgo } from '@/format/time';

useDocumentTitle('Health');

const health = useHealth();

const context = ref<ErrorContext | ''>('');
const severity = ref<ErrorSeverity | 'all'>('all');
const errors = useErrors(() => ({
  context: context.value || undefined,
  severity: severity.value === 'all' ? undefined : severity.value,
}));
const events = computed(() => errors.data.value?.pages.flatMap((page) => page.data) ?? []);

const STATUS_ORDER: SearchStatus[] = ['running', 'pending', 'completed', 'failed'];
const STATUS_TONE = { running: 'info', pending: 'default', completed: 'success', failed: 'danger' } as const;
const STATUS_LABEL = { running: 'Running', pending: 'Pending', completed: 'Completed', failed: 'Failed' } as const;

const totalRuns = computed(() =>
  Object.values(health.data.value?.searches_by_status ?? {}).reduce((sum, count) => sum + (count ?? 0), 0),
);

/** One stacked bar under the run tiles: the share of each status at a glance. */
const runShares = computed(() =>
  STATUS_ORDER.map((status) => ({
    status,
    count: health.data.value?.searches_by_status[status] ?? 0,
    share: totalRuns.value ? (100 * (health.data.value?.searches_by_status[status] ?? 0)) / totalRuns.value : 0,
  })),
);
const SHARE_COLOR = { running: 'bg-info', pending: 'bg-line-strong', completed: 'bg-success', failed: 'bg-danger' } as const;

const CONTEXT_OPTIONS = [
  { value: '' as const, label: 'All contexts' },
  ...(Object.entries(CONTEXT_LABELS) as [ErrorContext, string][]).map(([value, label]) => ({ value, label })),
];
const SEVERITY_OPTIONS: { value: ErrorSeverity | 'all'; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'error', label: 'Errors' },
  { value: 'warning', label: 'Warnings' },
];

const filtered = computed(() => context.value !== '' || severity.value !== 'all');

function pretty(details: unknown): string {
  try {
    return JSON.stringify(details, null, 2);
  } catch {
    return String(details);
  }
}
</script>

<template>
  <div>
    <PageHeader title="Health" description="Whether the pipeline is keeping up, and what went wrong when it did not." />

    <ErrorBanner v-if="health.isError.value" :message="errorMessage(health.error.value, 'The health summary could not be loaded.')" :retry="() => health.refetch()" class="mb-6" />

    <div v-else-if="health.isPending.value" class="mb-10 grid grid-cols-2 gap-3 lg:grid-cols-4" aria-label="Loading health summary">
      <SkeletonBlock v-for="n in 8" :key="n" class="h-28" />
    </div>

    <template v-else-if="health.data.value">
      <section aria-labelledby="runs-heading" class="mb-10">
        <div class="mb-3 flex items-baseline justify-between gap-3">
          <h2 id="runs-heading" class="text-section font-semibold text-ink">Searches</h2>
          <p class="text-meta text-ink-3 tabular-nums">{{ totalRuns.toLocaleString('en') }} in total</p>
        </div>
        <div class="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <StatTile
            v-for="status in STATUS_ORDER"
            :key="status"
            :label="STATUS_LABEL[status]"
            :value="(health.data.value.searches_by_status[status] ?? 0).toLocaleString('en')"
            :tone="(health.data.value.searches_by_status[status] ?? 0) > 0 ? STATUS_TONE[status] : 'default'"
          />
        </div>
        <div v-if="totalRuns > 0" class="mt-3 flex h-2 overflow-hidden rounded-full bg-sunken" role="img" :aria-label="runShares.map((s) => `${s.count} ${s.status}`).join(', ')">
          <span v-for="share in runShares" :key="share.status" :class="SHARE_COLOR[share.status]" :style="{ width: `${share.share}%` }" />
        </div>
      </section>

      <section aria-labelledby="recent-heading" class="mb-10 grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
        <div>
          <h2 id="recent-heading" class="mb-3 text-section font-semibold text-ink">Recent activity</h2>
          <div class="grid grid-cols-2 gap-3">
            <StatTile
              label="Errors, last 24 hours"
              :value="health.data.value.errors_last_24h.toLocaleString('en')"
              :tone="health.data.value.errors_last_24h > 0 ? 'danger' : 'default'"
              :detail="health.data.value.latest_error_at ? `Latest ${timeAgo(health.data.value.latest_error_at)}` : 'None recorded'"
            />
            <StatTile label="Images found, last 7 days" :value="health.data.value.images_last_7d.toLocaleString('en')" />
          </div>
        </div>
        <div>
          <h2 class="mb-3 text-section font-semibold text-ink">Errors by context, last 7 days</h2>
          <div class="rounded-surface border border-line bg-raised p-3">
            <ContextBars :counts="health.data.value.errors_by_context_last_7d" :selected="context || null" @select="context = $event ?? ''" />
          </div>
        </div>
      </section>
    </template>

    <section aria-labelledby="log-heading">
      <div class="mb-4 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <h2 id="log-heading" class="text-section font-semibold text-ink">Error log</h2>
        <div class="flex flex-wrap items-end gap-4">
          <div class="w-48"><SelectField v-model="context" label="Context" :options="CONTEXT_OPTIONS" /></div>
          <ChipGroup v-model="severity" label="Severity" :options="SEVERITY_OPTIONS" />
        </div>
      </div>

      <ErrorBanner v-if="errors.isError.value" :message="errorMessage(errors.error.value, 'The error log could not be loaded.')" :retry="() => errors.refetch()" />
      <div v-else-if="errors.isPending.value" class="flex flex-col gap-2" aria-label="Loading error log">
        <SkeletonBlock v-for="n in 4" :key="n" class="h-20" />
      </div>
      <!-- Only once the log has arrived: "nothing logged" over a log that failed to load would be a lie. -->
      <EmptyState
        v-else-if="events.length === 0"
        :title="filtered ? 'No errors match these filters' : 'Nothing logged'"
        :hint="filtered ? 'Choose All to see every entry.' : 'Failures during imports, searches and downloads are recorded here.'"
      />
      <template v-else>
        <ul class="flex flex-col gap-2">
          <li v-for="event in events" :key="event.id">
            <details class="group rounded-surface border border-line bg-raised open:border-line-strong">
              <summary class="focus-ring flex cursor-pointer list-none items-start gap-3 rounded-surface p-4 [&::-webkit-details-marker]:hidden">
                <StatusBadge :status="event.severity" class="mt-0.5" />
                <div class="min-w-0 flex-1">
                  <p class="text-body break-words text-ink">{{ event.message ?? event.exception_message ?? 'No message recorded' }}</p>
                  <p class="mt-0.5 text-meta text-ink-3">
                    {{ CONTEXT_LABELS[event.context] ?? event.context
                    }}<template v-if="event.occurred_at">, <time :datetime="event.occurred_at" :title="formatDateTime(event.occurred_at) ?? undefined">{{ timeAgo(event.occurred_at) }}</time></template>
                  </p>
                </div>
                <span class="mt-1 text-meta text-ink-3 transition-transform group-open:rotate-180" aria-hidden="true">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m6 9 6 6 6-6" /></svg>
                </span>
              </summary>
              <div class="flex flex-col gap-3 border-t border-line px-4 py-4 text-meta">
                <p v-if="event.exception_class || event.exception_message" class="break-words text-ink-2">
                  <span class="font-semibold text-ink">{{ event.exception_class }}</span>
                  <template v-if="event.exception_message">: {{ event.exception_message }}</template>
                </p>
                <div class="flex flex-wrap gap-x-5 gap-y-1">
                  <RouterLink v-if="event.car_search_id" :to="{ name: 'run', params: { id: event.car_search_id } }" class="focus-ring rounded font-semibold text-accent-text hover:underline">
                    Search {{ event.car_search_id }}
                  </RouterLink>
                  <RouterLink v-if="event.csv_import_id" :to="{ name: 'import', params: { id: event.csv_import_id } }" class="focus-ring rounded font-semibold text-accent-text hover:underline">
                    Import {{ event.csv_import_id }}
                  </RouterLink>
                  <RouterLink v-if="event.car_image_id" :to="{ name: 'image', params: { id: event.car_image_id } }" class="focus-ring rounded font-semibold text-accent-text hover:underline">
                    Image {{ event.car_image_id }}
                  </RouterLink>
                  <span v-if="event.occurred_at" class="text-ink-3">{{ formatDateTime(event.occurred_at) }}</span>
                </div>
                <div v-if="event.trace_excerpt" class="overflow-x-auto rounded-control bg-surface p-3">
                  <pre class="font-mono text-micro whitespace-pre text-ink-2">{{ event.trace_excerpt }}</pre>
                </div>
                <div v-if="event.details !== null && event.details !== undefined" class="overflow-x-auto rounded-control bg-surface p-3">
                  <pre class="font-mono text-micro whitespace-pre text-ink-2">{{ pretty(event.details) }}</pre>
                </div>
              </div>
            </details>
          </li>
        </ul>
        <LoadMore
          :auto="false"
          :has-next-page="errors.hasNextPage.value"
          :is-fetching-next-page="errors.isFetchingNextPage.value"
          :fetch-next-page="errors.fetchNextPage"
        />
      </template>
    </section>
  </div>
</template>
