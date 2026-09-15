<script setup lang="ts">
import { computed } from 'vue';
import { RouterLink } from 'vue-router';

import type { Search } from '@/api/schemas';
import { yearRange } from '@/format/labels';
import { plural, timeAgo } from '@/format/time';

import StatusBadge from './StatusBadge.vue';

const props = defineProps<{ search: Search; showWhen?: boolean }>();

const meta = computed(() =>
  [
    plural(props.search.images_count ?? 0, 'image'),
    props.showWhen ? timeAgo(props.search.created_at) : null,
  ]
    .filter(Boolean)
    .join(', '),
);
</script>

<template>
  <RouterLink
    :to="{ name: 'run', params: { id: search.id } }"
    class="focus-ring group flex items-center gap-3 rounded-control px-3 py-2.5 hover:bg-sunken/60"
  >
    <div class="min-w-0 flex-1">
      <p class="truncate text-body font-medium text-ink group-hover:text-accent-text">
        {{ search.make }} {{ search.model ?? '' }}
        <span class="font-normal text-ink-2 tabular-nums">{{ yearRange(search) }}</span>
      </p>
      <p class="text-meta text-ink-3">{{ meta }}</p>
    </div>
    <StatusBadge :status="search.status" />
  </RouterLink>
</template>
