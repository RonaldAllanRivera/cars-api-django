<script setup lang="ts">
import { computed, ref } from 'vue';
import { RouterLink, useRouter } from 'vue-router';

import { ApiValidationError, errorMessage } from '@/api/client';
import { useImports, useUploadImport } from '@/api/composables/useImports';
import { usePluginDownload } from '@/api/composables/usePluginDownload';
import type { Import } from '@/api/schemas';
import { useAuth } from '@/auth/auth';
import CsvDropzone from '@/components/CsvDropzone.vue';
import EmptyState from '@/components/EmptyState.vue';
import ErrorBanner from '@/components/ErrorBanner.vue';
import Icon from '@/components/Icon.vue';
import LoadMore from '@/components/LoadMore.vue';
import PageHeader from '@/components/PageHeader.vue';
import SkeletonBlock from '@/components/SkeletonBlock.vue';
import WordPressPluginCard from '@/components/WordPressPluginCard.vue';
import { useDocumentTitle } from '@/composables/useDocumentTitle';
import { showToast } from '@/composables/useToast';
import { plural, timeAgo } from '@/format/time';

useDocumentTitle('Pipeline');

const router = useRouter();
const { can } = useAuth();
const imports = useImports();
const upload = useUploadImport();
const uploadError = ref<string | null>(null);
const pluginDownload = usePluginDownload();
const blockedPluginUrl = ref<string | null>(null);
const pluginError = ref<string | null>(null);

async function downloadPlugin(): Promise<void> {
  blockedPluginUrl.value = null;
  pluginError.value = null;

  try {
    const { link, opened } = await pluginDownload.mutateAsync();
    if (opened) {
      showToast(`Downloading ${link.filename}.`);
    } else {
      blockedPluginUrl.value = link.url;
    }
  } catch (caught) {
    pluginError.value = errorMessage(caught, 'The plugin could not be downloaded.');
  }
}

function importMeta(csvImport: Import): string {
  return [
    plural(csvImport.unique_combos ?? csvImport.searches_count ?? 0, 'query', 'queries'),
    csvImport.duplicates_skipped ? `${csvImport.duplicates_skipped} duplicates skipped` : null,
    csvImport.importer_name ? `uploaded by ${csvImport.importer_name}` : null,
  ]
    .filter(Boolean)
    .join(', ');
}

const list = computed(() => imports.data.value?.pages.flatMap((page) => page.data) ?? []);

async function onUpload(file: File): Promise<void> {
  uploadError.value = null;

  try {
    const created = await upload.mutateAsync(file);
    showToast(`Imported ${created.original_filename}: ${plural(created.unique_combos ?? 0, 'query', 'queries')} queued.`);
    await router.push({ name: 'import', params: { id: created.id } });
  } catch (caught) {
    // The server's rejections are written for people ("Missing required
    // columns: Model."), so they are shown as they are.
    uploadError.value =
      caught instanceof ApiValidationError
        ? (caught.first('csv_file') ?? caught.message)
        : errorMessage(caught, 'The CSV could not be imported.');
  }
}
</script>

<template>
  <div>
    <PageHeader
      title="Pipeline"
      description="Import a CSV of vehicles, then run its searches in paced batches you can pause and resume."
    />

    <div class="grid items-start gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,22rem)] xl:gap-12">
      <section aria-labelledby="imports-heading" class="order-2 min-w-0 lg:order-1">
        <h2 id="imports-heading" class="mb-4 text-section font-semibold text-ink">Imports</h2>

        <ErrorBanner v-if="imports.isError.value" :message="errorMessage(imports.error.value)" :retry="() => imports.refetch()" />
        <div v-else-if="imports.isPending.value" class="flex flex-col gap-2" aria-label="Loading imports">
          <SkeletonBlock v-for="n in 4" :key="n" class="h-[4.5rem]" />
        </div>
        <EmptyState
          v-else-if="list.length === 0"
          title="No imports yet"
          :hint="can('imports:write') ? 'Upload a CSV of makes, models and years to queue its searches.' : 'Imports appear here once someone uploads a CSV.'"
          icon="file"
        />
        <template v-else>
          <ul class="flex flex-col gap-2">
            <li v-for="csvImport in list" :key="csvImport.id">
              <RouterLink
                :to="{ name: 'import', params: { id: csvImport.id } }"
                class="focus-ring group flex items-center gap-4 rounded-surface border border-line bg-raised px-4 py-3.5 transition-colors hover:border-line-strong"
              >
                <span class="grid size-10 shrink-0 place-items-center rounded-control bg-sunken text-ink-2 group-hover:text-accent-text">
                  <Icon name="file" />
                </span>
                <div class="min-w-0 flex-1">
                  <p class="truncate text-body font-semibold text-ink group-hover:text-accent-text">{{ csvImport.original_filename }}</p>
                  <p class="text-meta text-ink-3">{{ importMeta(csvImport) }}</p>
                </div>
                <span v-if="csvImport.created_at" class="hidden text-meta whitespace-nowrap text-ink-3 sm:block">
                  {{ timeAgo(csvImport.created_at) }}
                </span>
                <Icon name="arrowRight" :size="18" class="text-ink-3" />
              </RouterLink>
            </li>
          </ul>
          <LoadMore
            :has-next-page="imports.hasNextPage.value"
            :is-fetching-next-page="imports.isFetchingNextPage.value"
            :fetch-next-page="imports.fetchNextPage"
          />
        </template>
      </section>

      <section
        v-if="can('imports:write')"
        aria-labelledby="upload-heading"
        class="order-1 rounded-surface border border-line bg-raised p-5 lg:sticky lg:top-10 lg:order-2"
      >
        <h2 id="upload-heading" class="text-section font-semibold text-ink">Import a CSV</h2>
        <p class="mt-1 mb-4 text-meta text-ink-2">
          Rows are de-duplicated by make, model and year. Importing only queues the searches; running them is a separate,
          paced crawl you start from the import.
        </p>
        <ErrorBanner v-if="uploadError" :message="uploadError" class="mb-3" />
        <CsvDropzone :pending="upload.isPending.value" @upload="onUpload" />
      </section>

      <WordPressPluginCard
        v-if="can('blog:write')"
        class="order-3 lg:col-start-2"
        :pending="pluginDownload.isPending.value"
        :blocked-url="blockedPluginUrl"
        :error="pluginError"
        @download="downloadPlugin"
      />
    </div>
  </div>
</template>
