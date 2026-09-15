<script setup lang="ts">
defineProps<{ label: string; value: number | string; tone?: 'default' | 'danger' | 'success' | 'info'; detail?: string }>();

const TONE = {
  default: 'text-ink',
  danger: 'text-danger-text',
  success: 'text-success-text',
  info: 'text-info-text',
} as const;
</script>

<template>
  <div class="flex flex-col justify-between gap-3 rounded-surface border border-line bg-raised p-4">
    <p class="text-meta font-medium text-ink-2">{{ label }}</p>
    <div>
      <p class="type-figure text-figure" :class="TONE[tone ?? 'default']">{{ value }}</p>
      <p v-if="detail" class="mt-1 text-meta text-ink-3">{{ detail }}</p>
    </div>
  </div>
</template>
