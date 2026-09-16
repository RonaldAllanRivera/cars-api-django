<script setup lang="ts">
import { computed } from 'vue';

import type { ErrorContext } from '@/api/schemas';
import { contextLabel } from '@/format/labels';

/**
 * Horizontal bars, sorted by count. A ranked comparison of five categories is
 * what bars are for; the value sits at the end of each so nothing needs a legend.
 */
const props = defineProps<{ counts: Partial<Record<ErrorContext, number>>; selected?: ErrorContext | null }>();
const emit = defineEmits<{ select: [context: ErrorContext | null] }>();

const rows = computed(() => {
  const entries = (Object.entries(props.counts) as [ErrorContext, number][]).sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...entries.map(([, count]) => count));

  return entries.map(([context, count]) => ({
    context,
    count,
    label: contextLabel(context),
    width: count === 0 ? 0 : Math.max(2, (100 * count) / max),
  }));
});
</script>

<template>
  <ul class="flex flex-col gap-1">
    <li v-for="row in rows" :key="row.context">
      <button
        type="button"
        class="focus-ring group grid w-full grid-cols-[minmax(7rem,9rem)_1fr_2.5rem] items-center gap-3 rounded-control px-2 py-1.5 text-left hover:bg-sunken/60"
        :aria-pressed="selected === row.context"
        :aria-label="`${row.label}: ${row.count} errors. ${selected === row.context ? 'Showing only these in the log' : 'Filter the log to these'}`"
        @click="emit('select', selected === row.context ? null : row.context)"
      >
        <span class="truncate text-meta" :class="selected === row.context ? 'font-semibold text-accent-text' : 'text-ink-2 group-hover:text-ink'">
          {{ row.label }}
        </span>
        <span class="h-2 overflow-hidden rounded-full bg-sunken" aria-hidden="true">
          <span
            class="block h-full rounded-full transition-[width] duration-500"
            :class="row.count === 0 ? '' : selected === row.context ? 'bg-accent' : 'bg-danger/80'"
            :style="{ width: `${row.width}%` }"
          />
        </span>
        <span class="text-right text-meta font-semibold tabular-nums" :class="row.count === 0 ? 'text-ink-3' : 'text-ink'">
          {{ row.count }}
        </span>
      </button>
    </li>
  </ul>
</template>
