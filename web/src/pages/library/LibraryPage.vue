<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import type { LocationQueryRaw } from 'vue-router';

import { errorMessage } from '@/api/client';
import { useExport } from '@/api/composables/useExport';
import type { ExportFormat } from '@/api/composables/useExport';
import { useImageCount, useImages } from '@/api/composables/useImages';
import { useImports } from '@/api/composables/useImports';
import type { ImageFilters } from '@/api/queryKeys';
import { ReviewStatusSchema } from '@/api/schemas';
import { useAuth } from '@/auth/auth';
import ChipGroup from '@/components/ChipGroup.vue';
import ExportPanel from '@/components/ExportPanel.vue';
import Icon from '@/components/Icon.vue';
import ImageGrid from '@/components/ImageGrid.vue';
import PageHeader from '@/components/PageHeader.vue';
import SelectField from '@/components/SelectField.vue';
import TextField from '@/components/TextField.vue';
import { useDebounced } from '@/composables/useDebounced';
import { useDocumentTitle } from '@/composables/useDocumentTitle';
import { showToast } from '@/composables/useToast';

useDocumentTitle('Library');

const route = useRoute();
const router = useRouter();
const { can } = useAuth();

/*
 * Filters live in the URL, so a filtered view survives a reload, can be shared,
 * and the back button undoes a filter change - and so Pipeline can link here
 * with an import already selected.
 */
const one = (value: unknown): string => (typeof value === 'string' ? value : '');

type Review = 'all' | 'pending' | 'approved' | 'rejected';
type Verdict = 'all' | 'yes' | 'no';

const review = computed<Review>({
  get: () => {
    const parsed = ReviewStatusSchema.safeParse(route.query.review);

    return parsed.success ? parsed.data : 'all';
  },
  set: (value) => update({ review: value === 'all' ? undefined : value }),
});
const makeMatch = computed<Verdict>({
  get: () => (['yes', 'no'].includes(one(route.query.make_match)) ? (one(route.query.make_match) as Verdict) : 'all'),
  set: (value) => update({ make_match: value === 'all' ? undefined : value }),
});
const yearMatch = computed<Verdict>({
  get: () => (['yes', 'no'].includes(one(route.query.year_match)) ? (one(route.query.year_match) as Verdict) : 'all'),
  set: (value) => update({ year_match: value === 'all' ? undefined : value }),
});
const importId = computed<string>({
  get: () => (/^\d+$/.test(one(route.query.import)) ? one(route.query.import) : ''),
  set: (value) => update({ import: value || undefined }),
});

// The raw input drives the field; only the settled value reaches the URL and
// the query - a keystroke is not a request.
const makeInput = ref(one(route.query.make));
const settledMake = useDebounced(makeInput, 300);
watch(settledMake, (value) => update({ make: value.trim() || undefined }));

function update(patch: LocationQueryRaw): void {
  const query: LocationQueryRaw = { ...route.query, ...patch };
  for (const key of Object.keys(query)) if (query[key] === undefined) delete query[key];
  void router.replace({ query });
}

const verdict = (value: Verdict): boolean | undefined => (value === 'all' ? undefined : value === 'yes');

const filters = computed<ImageFilters>(() => ({
  make: one(route.query.make) || undefined,
  review_status: review.value === 'all' ? undefined : review.value,
  make_confirmed: verdict(makeMatch.value),
  year_confirmed: verdict(yearMatch.value),
  csv_import_id: importId.value ? Number(importId.value) : undefined,
}));

// Phones get the grid first; the filters fold away behind a button.
const filtersOpen = ref(false);

const activeFilterCount = computed(() => Object.values(filters.value).filter((value) => value !== undefined).length);

function clearFilters(): void {
  makeInput.value = '';
  void router.replace({ query: {} });
}

const images = useImages(filters);
const canExport = computed(() => can('exports:read'));
const count = useImageCount(filters, canExport);

const imports = useImports(() => can('imports:read'));
const importOptions = computed(() => [
  { value: '', label: 'All images' },
  ...(imports.data.value?.pages.flatMap((page) =>
    page.data.map((csvImport) => ({ value: String(csvImport.id), label: csvImport.original_filename })),
  ) ?? []),
]);

const exporter = useExport(filters);
const pendingFormat = computed<ExportFormat | null>(() =>
  exporter.isPending.value ? (exporter.variables.value ?? null) : null,
);

async function runExport(format: ExportFormat): Promise<void> {
  try {
    const { link, opened } = await exporter.mutateAsync(format);
    const what = `${format.toUpperCase()} export of ${link.count.toLocaleString('en')} ${link.count === 1 ? 'image' : 'images'}`;

    showToast(opened ? `Your ${what} opened in a new tab.` : `Your ${what} is ready.`, 'success', {
      action: { label: opened ? 'Open it again' : 'Open the download', href: link.url },
    });
  } catch (caught) {
    showToast(errorMessage(caught, 'The export could not be started.'), 'error');
  }
}

const REVIEW_OPTIONS: { value: Review; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'pending', label: 'Pending' },
  { value: 'approved', label: 'Approved' },
  { value: 'rejected', label: 'Rejected' },
];
const VERDICT_OPTIONS: { value: Verdict; label: string }[] = [
  { value: 'all', label: 'Any' },
  { value: 'yes', label: 'Matches' },
  { value: 'no', label: 'Does not match' },
];
</script>

<template>
  <div>
    <PageHeader title="Library" description="Every image the pipeline has found, with the machine's checks and your verdicts." />

    <button
      type="button"
      class="focus-ring mb-3 flex h-10 w-full items-center justify-between rounded-control border border-line-strong bg-raised px-4 text-body font-semibold text-ink md:hidden"
      :aria-expanded="filtersOpen"
      aria-controls="library-filters"
      @click="filtersOpen = !filtersOpen"
    >
      <span>Filters<span v-if="activeFilterCount" class="ml-1 text-accent-text">({{ activeFilterCount }})</span></span>
      <Icon name="chevron" :size="18" class="transition-transform" :class="filtersOpen ? 'rotate-180' : ''" />
    </button>

    <section
      id="library-filters"
      aria-label="Filters"
      class="mb-6 rounded-surface border border-line bg-raised p-4 sm:p-5 md:block"
      :class="filtersOpen ? 'block' : 'hidden'"
    >
      <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]">
        <TextField
          v-model="makeInput"
          label="Make"
          placeholder="e.g. Toyota"
          hint="Exact match: Toyota, not Toy."
          autocomplete="off"
          type="search"
        />
        <SelectField v-if="can('imports:read')" v-model="importId" label="CSV import" :options="importOptions" />
      </div>
      <div class="mt-4 flex flex-wrap gap-x-8 gap-y-4">
        <ChipGroup v-model="review" label="Your verdict" :options="REVIEW_OPTIONS" />
        <ChipGroup v-model="makeMatch" label="Make check" :options="VERDICT_OPTIONS" />
        <ChipGroup v-model="yearMatch" label="Year check" :options="VERDICT_OPTIONS" />
      </div>
      <div class="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
        <ExportPanel v-if="canExport" :count="count.data.value" :pending="pendingFormat" @export="runExport" />
        <button
          v-if="activeFilterCount > 0"
          type="button"
          class="focus-ring rounded-control text-meta font-semibold text-accent-text hover:underline"
          @click="clearFilters"
        >
          Clear {{ activeFilterCount === 1 ? 'filter' : `${activeFilterCount} filters` }}
        </button>
      </div>
    </section>

    <ImageGrid
      :pages="images.data.value?.pages"
      :is-pending="images.isPending.value"
      :is-error="images.isError.value"
      :error="images.error.value"
      :has-next-page="images.hasNextPage.value"
      :is-fetching-next-page="images.isFetchingNextPage.value"
      :fetch-next-page="images.fetchNextPage"
      :refetch="images.refetch"
      :empty-title="activeFilterCount > 0 ? 'No images match these filters' : 'The library is empty'"
      :empty-hint="
        activeFilterCount > 0
          ? 'Loosen a filter, or check the make is spelled exactly.'
          : 'Run a search or a CSV import and the images it finds appear here.'
      "
    />
  </div>
</template>
