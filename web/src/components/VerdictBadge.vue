<script setup lang="ts">
import { computed } from 'vue';

/**
 * The relevance checker's verdict, read-only beside the human's. null is not
 * false: it means the checker never reached a conclusion.
 */
const props = defineProps<{ kind: 'make' | 'year'; value: boolean | null }>();

const verdict = computed(() =>
  props.value === null ? 'unknown' : props.value ? 'matches' : 'does not match',
);
const tone = computed(() =>
  props.value === null
    ? 'bg-surface/80 text-ink-2'
    : props.value
      ? 'bg-surface/80 text-success-text'
      : 'bg-surface/80 text-danger-text',
);
const symbol = computed(() => (props.value === null ? '?' : props.value ? '✓' : '✕'));
</script>

<template>
  <span
    class="inline-flex h-6 items-center gap-1 rounded-full px-2 text-micro font-semibold whitespace-nowrap ring-1 ring-white/5 backdrop-blur-sm"
    :class="tone"
    :title="`The ${kind} ${verdict === 'unknown' ? 'could not be checked' : verdict}`"
  >
    <span aria-hidden="true">{{ symbol }}</span>
    <span class="text-ink/90">{{ kind === 'make' ? 'Make' : 'Year' }}</span>
    <span class="sr-only">{{ verdict }}</span>
  </span>
</template>
