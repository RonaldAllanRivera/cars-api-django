<script setup lang="ts">
import { computed } from 'vue';

/**
 * Keyed by search, review and download statuses - they never collide. No
 * status is amber: amber means "you can do this", a badge means "this happened".
 */
const props = defineProps<{ status: string }>();

const NEUTRAL = 'bg-sunken text-ink-2';
const TONES: Record<string, string> = {
  completed: 'bg-success/15 text-success-text',
  approved: 'bg-success/15 text-success-text',
  downloaded: 'bg-success/15 text-success-text',
  running: 'bg-info/15 text-info-text',
  downloading: 'bg-info/15 text-info-text',
  pending: NEUTRAL,
  not_downloaded: NEUTRAL,
  failed: 'bg-danger/15 text-danger-text',
  rejected: 'bg-danger/15 text-danger-text',
  error: 'bg-danger/15 text-danger-text',
  warning: 'bg-accent/10 text-ink-2',
};

const tone = computed(() => TONES[props.status] ?? NEUTRAL);
const label = computed(() => {
  const text = props.status.replace(/_/g, ' ');

  return text.charAt(0).toUpperCase() + text.slice(1);
});
</script>

<template>
  <span class="inline-flex h-6 items-center gap-1.5 rounded-full px-2.5 text-micro font-semibold whitespace-nowrap" :class="tone">
    <span v-if="status === 'running'" class="size-1.5 animate-pulse rounded-full bg-current" aria-hidden="true" />
    {{ label }}
  </span>
</template>
