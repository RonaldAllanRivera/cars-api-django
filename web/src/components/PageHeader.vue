<script setup lang="ts">
import { RouterLink } from 'vue-router';
import type { RouteLocationRaw } from 'vue-router';

import Icon from './Icon.vue';

defineProps<{ title: string; description?: string; back?: { to: RouteLocationRaw; label: string } }>();
</script>

<template>
  <header class="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
    <div class="min-w-0">
      <RouterLink
        v-if="back"
        :to="back.to"
        class="focus-ring mb-3 inline-flex items-center gap-1 rounded-control text-meta font-medium text-ink-2 hover:text-ink"
      >
        <Icon name="arrowLeft" :size="16" />
        {{ back.label }}
      </RouterLink>
      <h1 class="type-display text-[26px] leading-[32px] break-words text-ink sm:text-title">{{ title }}</h1>
      <p v-if="description" class="mt-2 max-w-[62ch] text-body text-ink-2">{{ description }}</p>
      <slot name="meta" />
    </div>
    <div v-if="$slots.actions" class="flex shrink-0 flex-wrap items-center gap-2">
      <slot name="actions" />
    </div>
  </header>
</template>
