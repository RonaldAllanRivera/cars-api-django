<script setup lang="ts">
import Icon from './Icon.vue';
import type { IconName } from './Icon.vue';

defineProps<{ title: string; hint?: string; icon?: IconName }>();
</script>

<template>
  <div class="flex flex-col items-start gap-2 rounded-surface border border-dashed border-line-strong px-6 py-10 sm:items-center sm:text-center">
    <Icon v-if="icon" :name="icon" :size="28" class="mb-1 text-ink-3" />
    <p class="text-section font-semibold text-ink">{{ title }}</p>
    <p v-if="hint" class="max-w-prose text-body text-ink-2">{{ hint }}</p>
    <div v-if="$slots.default" class="mt-2"><slot /></div>
  </div>
</template>
