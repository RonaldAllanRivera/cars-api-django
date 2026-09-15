<script setup lang="ts">
import type { ExportFormat } from '@/api/composables/useExport';
import { ZIP_CAP } from '@/config';

import BaseButton from './BaseButton.vue';

/**
 * Presentational. The count is advisory - the server recounts at mint and at
 * download - so this decides what to offer, never what is allowed.
 */
const props = withDefaults(
  defineProps<{ count: number | undefined; pending: ExportFormat | null; zipCap?: number }>(),
  { zipCap: ZIP_CAP },
);
const emit = defineEmits<{ export: [format: ExportFormat] }>();

const tooLargeForZip = () => (props.count ?? 0) > props.zipCap;
</script>

<template>
  <div class="flex flex-wrap items-center gap-x-4 gap-y-2">
    <p class="text-body text-ink-2" aria-live="polite">
      <template v-if="count === undefined"><span class="skeleton inline-block h-4 w-24 rounded align-middle" /></template>
      <template v-else>
        <span class="type-figure text-ink">{{ count.toLocaleString('en') }}</span>
        {{ count === 1 ? 'image matches' : 'images match' }}
      </template>
    </p>
    <div class="flex gap-2">
      <BaseButton
        variant="secondary"
        size="sm"
        icon="download"
        :pending="pending === 'csv'"
        :disabled="!count || pending !== null"
        @click="emit('export', 'csv')"
      >
        Export CSV
      </BaseButton>
      <BaseButton
        variant="secondary"
        size="sm"
        icon="download"
        :pending="pending === 'zip'"
        :disabled="!count || tooLargeForZip() || pending !== null"
        :title="tooLargeForZip() ? `A ZIP holds at most ${zipCap} images` : undefined"
        :aria-describedby="tooLargeForZip() ? 'zip-cap-note' : undefined"
        @click="emit('export', 'zip')"
      >
        Export ZIP
      </BaseButton>
    </div>
    <p v-if="tooLargeForZip()" id="zip-cap-note" class="basis-full text-meta text-ink-3">
      A ZIP holds at most {{ zipCap }} images. Narrow the filters to export one; the CSV has no limit.
    </p>
  </div>
</template>
