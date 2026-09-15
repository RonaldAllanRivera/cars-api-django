<script setup lang="ts">
import { computed, reactive, ref } from 'vue';
import { RouterLink, useRouter } from 'vue-router';

import { ApiValidationError, errorMessage } from '@/api/client';
import {
  MAX_IMAGES_PER_YEAR,
  MAX_YEAR_SPAN,
  useCreateSearch,
  useSearches,
} from '@/api/composables/useSearches';
import type { CreateSearchResult } from '@/api/composables/useSearches';
import type { SearchStatus } from '@/api/schemas';
import BaseButton from '@/components/BaseButton.vue';
import ChipGroup from '@/components/ChipGroup.vue';
import EmptyState from '@/components/EmptyState.vue';
import ErrorBanner from '@/components/ErrorBanner.vue';
import LoadMore from '@/components/LoadMore.vue';
import PageHeader from '@/components/PageHeader.vue';
import SearchRow from '@/components/SearchRow.vue';
import SelectField from '@/components/SelectField.vue';
import SkeletonBlock from '@/components/SkeletonBlock.vue';
import TextField from '@/components/TextField.vue';
import { useDocumentTitle } from '@/composables/useDocumentTitle';
import { showToast } from '@/composables/useToast';
import { humanSeconds, plural } from '@/format/time';

useDocumentTitle('Search');

const router = useRouter();
const create = useCreateSearch();

const CURRENT_YEAR = new Date().getFullYear();
const EARLIEST_YEAR = 1886;

const form = reactive({
  make: '',
  model: '',
  fromYear: '',
  toYear: '',
  imagesPerYear: String(MAX_IMAGES_PER_YEAR),
  color: '',
  transmission: '',
});

type Field = 'make' | 'from_year' | 'to_year' | 'images_per_year' | 'model' | 'color' | 'transmission';
const errors = ref<Partial<Record<Field, string>>>({});
const formError = ref<string | null>(null);
const notice = ref<CreateSearchResult | null>(null);

const IMAGES_PER_YEAR = Array.from({ length: MAX_IMAGES_PER_YEAR }, (_, index) => ({
  value: String(index + 1),
  label: plural(index + 1, 'image'),
}));

const TRANSMISSIONS = [
  { value: '', label: 'Any' },
  { value: 'Automatic', label: 'Automatic' },
  { value: 'Manual', label: 'Manual' },
  { value: 'CVT', label: 'CVT' },
];

function parseYear(raw: string): number | null {
  const trimmed = raw.trim();
  if (!/^\d{4}$/.test(trimmed)) return null;
  const year = Number(trimmed);

  return year >= EARLIEST_YEAR && year <= CURRENT_YEAR + 1 ? year : null;
}

/** Checked before the round trip: the search runs inside the request, so a rejected span is a wasted wait. */
function validate(): { from: number; to: number } | null {
  const next: typeof errors.value = {};
  const from = parseYear(form.fromYear);
  const to = parseYear(form.toYear || form.fromYear);

  if (!form.make.trim()) next.make = 'Enter a make, for example Toyota.';
  if (from === null) next.from_year = `Enter a year between ${EARLIEST_YEAR} and ${CURRENT_YEAR + 1}.`;
  if (form.toYear.trim() && parseYear(form.toYear) === null) {
    next.to_year = `Enter a year between ${EARLIEST_YEAR} and ${CURRENT_YEAR + 1}.`;
  }

  if (from !== null && to !== null && !next.to_year) {
    if (to < from) next.to_year = 'The end year must not be before the start year.';
    else if (to - from > MAX_YEAR_SPAN) {
      next.to_year = `A search covers at most ${MAX_YEAR_SPAN + 1} years (${from}–${from + MAX_YEAR_SPAN}), because it runs while you wait.`;
    }
  }

  errors.value = next;

  return Object.keys(next).length === 0 && from !== null && to !== null ? { from, to } : null;
}

async function submit(): Promise<void> {
  formError.value = null;
  notice.value = null;

  const years = validate();
  if (!years) return;

  try {
    const result = await create.mutateAsync({
      make: form.make.trim(),
      model: form.model.trim() || undefined,
      from_year: years.from,
      to_year: years.to,
      images_per_year: Number(form.imagesPerYear),
      color: form.color.trim() || undefined,
      transmission: form.transmission || undefined,
    });

    if (result.outcome === 'blocked' || result.outcome === 'failed') {
      // Stay: the run page only knows the row failed, not that Wikimedia is
      // throttling or for how long. The notice links to the run instead.
      notice.value = result;

      return;
    }

    const count = result.search.images_count ?? result.search.images?.length ?? 0;
    showToast(
      result.outcome === 'existing'
        ? `This search already ran. Showing the earlier run with ${plural(count, 'image')}.`
        : `Search complete: ${plural(count, 'image')} found.`,
    );
    await router.push({ name: 'run', params: { id: result.search.id } });
  } catch (caught) {
    if (caught instanceof ApiValidationError) {
      const fields: Field[] = ['make', 'model', 'from_year', 'to_year', 'images_per_year', 'color', 'transmission'];
      errors.value = Object.fromEntries(
        fields.flatMap((field) => {
          const message = caught.first(field);

          return message ? [[field, message]] : [];
        }),
      );
      if (Object.keys(errors.value).length === 0) formError.value = caught.message;
    } else {
      formError.value = errorMessage(caught, 'The search could not be started.');
    }
  }
}

const noticeText = computed(() => {
  const result = notice.value;
  if (!result) return '';

  if (result.outcome === 'blocked') {
    const wait = result.retryAfterSeconds ? ` Try again in ${humanSeconds(result.retryAfterSeconds)}.` : '';

    return `${result.message ?? 'Wikimedia is rate-limiting this server.'}${wait}`;
  }

  return result.message ?? 'The search failed. The reason is in the error log on the Health page.';
});

// Recent ad-hoc runs. CSV queries live under Pipeline.
type StatusFilter = SearchStatus | 'all';
const status = ref<StatusFilter>('all');
const STATUS_OPTIONS: { value: StatusFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'pending', label: 'Pending' },
  { value: 'running', label: 'Running' },
  { value: 'completed', label: 'Completed' },
  { value: 'failed', label: 'Failed' },
];
const runs = useSearches(() => ({
  source: 'adhoc' as const,
  status: status.value === 'all' ? undefined : status.value,
}));
const runList = computed(() => runs.data.value?.pages.flatMap((page) => page.data) ?? []);
</script>

<template>
  <div>
    <PageHeader
      title="Search"
      :description="`Runs straight away against Wikimedia Commons: up to ${MAX_YEAR_SPAN + 1} years and ${MAX_IMAGES_PER_YEAR} images per year.`"
    />

    <div class="grid items-start gap-8 lg:grid-cols-[minmax(0,26rem)_minmax(0,1fr)] xl:gap-12">
      <section aria-labelledby="new-search" class="rounded-surface border border-line bg-raised p-5 sm:p-6">
        <h2 id="new-search" class="text-section font-semibold text-ink">New search</h2>

        <form class="mt-5 flex flex-col gap-4" novalidate @submit.prevent="submit">
          <ErrorBanner v-if="formError" :message="formError" />

          <div
            v-if="notice"
            role="alert"
            class="rounded-surface border px-4 py-3"
            :class="notice.outcome === 'blocked' ? 'border-accent/40 bg-accent/10' : 'border-danger/35 bg-danger/10'"
          >
            <p class="text-body" :class="notice.outcome === 'blocked' ? 'text-accent-text' : 'text-danger-text'">
              {{ noticeText }}
            </p>
            <RouterLink
              :to="{ name: 'run', params: { id: notice.search.id } }"
              class="focus-ring mt-2 inline-block rounded-control text-meta font-semibold text-ink underline-offset-4 hover:underline"
            >
              View the run
            </RouterLink>
          </div>

          <TextField v-model="form.make" label="Make" placeholder="e.g. Toyota" autocomplete="off" :error="errors.make" />
          <TextField
            v-model="form.model"
            label="Model"
            optional
            placeholder="e.g. RAV4"
            autocomplete="off"
            :error="errors.model"
          />

          <div class="grid grid-cols-2 gap-3">
            <TextField
              v-model="form.fromYear"
              label="From year"
              inputmode="numeric"
              maxlength="4"
              placeholder="1997"
              :error="errors.from_year"
            />
            <TextField
              v-model="form.toYear"
              label="To year"
              inputmode="numeric"
              maxlength="4"
              :placeholder="form.fromYear || '1999'"
              :error="errors.to_year"
            />
          </div>

          <SelectField v-model="form.imagesPerYear" label="Images per year" :options="IMAGES_PER_YEAR" :error="errors.images_per_year" />

          <details class="group rounded-control border border-line px-3 py-2 open:pb-4">
            <summary class="focus-ring cursor-pointer list-none rounded-control text-meta font-medium text-ink-2 marker:hidden hover:text-ink">
              <span class="inline-block transition-transform group-open:rotate-90" aria-hidden="true">›</span>
              Narrow by colour or transmission
            </summary>
            <div class="mt-3 grid gap-3 sm:grid-cols-2">
              <TextField v-model="form.color" label="Colour" optional placeholder="e.g. red" :error="errors.color" />
              <SelectField v-model="form.transmission" label="Transmission" :options="TRANSMISSIONS" :error="errors.transmission" />
            </div>
          </details>

          <BaseButton type="submit" size="lg" block icon="search" :pending="create.isPending.value">
            {{ create.isPending.value ? 'Searching Wikimedia' : 'Run search' }}
          </BaseButton>
          <p v-if="create.isPending.value" class="text-center text-meta text-ink-3" role="status">
            This runs while you wait and can take several seconds.
          </p>
        </form>
      </section>

      <section aria-labelledby="recent-runs" class="min-w-0">
        <div class="mb-4 flex flex-wrap items-end justify-between gap-3">
          <h2 id="recent-runs" class="text-section font-semibold text-ink">Recent runs</h2>
          <ChipGroup v-model="status" label="Filter runs by status" hide-label :options="STATUS_OPTIONS" />
        </div>

        <ErrorBanner v-if="runs.isError.value" :message="errorMessage(runs.error.value)" :retry="() => runs.refetch()" />
        <div v-else-if="runs.isPending.value" class="flex flex-col gap-2" aria-label="Loading runs">
          <SkeletonBlock v-for="n in 5" :key="n" class="h-14" />
        </div>
        <EmptyState
          v-else-if="runList.length === 0"
          :title="status === 'all' ? 'No runs yet' : `No ${status} runs`"
          :hint="status === 'all' ? 'Runs you start from the form appear here.' : 'Choose All to see every run.'"
          icon="search"
        />
        <template v-else>
          <ul class="divide-y divide-line rounded-surface border border-line bg-raised p-1.5">
            <li v-for="search in runList" :key="search.id">
              <SearchRow :search="search" show-when />
            </li>
          </ul>
          <LoadMore
            :has-next-page="runs.hasNextPage.value"
            :is-fetching-next-page="runs.isFetchingNextPage.value"
            :fetch-next-page="runs.fetchNextPage"
          />
        </template>
      </section>
    </div>
  </div>
</template>
