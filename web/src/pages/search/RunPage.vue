<script setup lang="ts">
import { computed } from 'vue';
import { RouterLink } from 'vue-router';

import { errorMessage } from '@/api/client';
import { useSearchImages } from '@/api/composables/useImages';
import { useSearch } from '@/api/composables/useSearches';
import ErrorBanner from '@/components/ErrorBanner.vue';
import ImageGrid from '@/components/ImageGrid.vue';
import PageHeader from '@/components/PageHeader.vue';
import SkeletonBlock from '@/components/SkeletonBlock.vue';
import StatusBadge from '@/components/StatusBadge.vue';
import { useDocumentTitle } from '@/composables/useDocumentTitle';
import { yearRange } from '@/format/labels';
import { formatDateTime, plural } from '@/format/time';

const props = defineProps<{ id: number }>();

const search = useSearch(() => props.id);
const images = useSearchImages(() => props.id);

const title = computed(() =>
  search.data.value ? `${search.data.value.make} ${search.data.value.model ?? ''}`.trim() : 'Run',
);
useDocumentTitle(title);

const back = computed(() =>
  search.data.value?.csv_import_id
    ? { to: { name: 'import', params: { id: search.data.value.csv_import_id } }, label: 'Import' }
    : { to: { name: 'search' }, label: 'Search' },
);
</script>

<template>
  <div>
    <div v-if="search.isPending.value" class="mb-8 space-y-3" aria-label="Loading run">
      <SkeletonBlock class="h-4 w-20 rounded" />
      <SkeletonBlock class="h-9 w-72 rounded" />
      <SkeletonBlock class="h-5 w-48 rounded" />
    </div>

    <template v-else-if="search.isError.value">
      <PageHeader title="Run" :back="{ to: { name: 'search' }, label: 'Search' }" />
      <ErrorBanner :message="errorMessage(search.error.value, 'This run could not be loaded.')" :retry="() => search.refetch()" />
    </template>

    <PageHeader v-else-if="search.data.value" :title="title" :back="back">
      <template #meta>
        <div class="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-meta text-ink-2">
          <StatusBadge :status="search.data.value.status" />
          <span class="tabular-nums">{{ yearRange(search.data.value) }}</span>
          <span>{{ plural(search.data.value.images_count ?? 0, 'image') }}</span>
          <span v-if="search.data.value.color">Colour: {{ search.data.value.color }}</span>
          <span v-if="search.data.value.transmission">Transmission: {{ search.data.value.transmission }}</span>
          <span v-if="search.data.value.commons_category">Category: {{ search.data.value.commons_category }}</span>
          <span v-if="search.data.value.created_at" class="text-ink-3">{{ formatDateTime(search.data.value.created_at) }}</span>
        </div>
        <p v-if="search.data.value.status === 'failed'" class="mt-3 text-body text-danger-text">
          This run failed. The reason is in the
          <RouterLink :to="{ name: 'health' }" class="font-semibold underline underline-offset-4">error log</RouterLink>.
        </p>
      </template>
    </PageHeader>

    <ImageGrid
      v-if="!search.isError.value"
      :pages="images.data.value?.pages"
      :is-pending="images.isPending.value"
      :is-error="images.isError.value"
      :error="images.error.value"
      :has-next-page="images.hasNextPage.value"
      :is-fetching-next-page="images.isFetchingNextPage.value"
      :fetch-next-page="images.fetchNextPage"
      :refetch="images.refetch"
      :empty-title="search.data.value?.status === 'pending' ? 'This run has not started yet' : 'This run found no images'"
      empty-hint="Wikimedia Commons had nothing that matched. A broader model or year range may help."
    />
  </div>
</template>
