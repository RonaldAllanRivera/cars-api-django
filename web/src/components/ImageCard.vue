<script setup lang="ts">
import { computed } from 'vue';
import { RouterLink } from 'vue-router';

import type { Image } from '@/api/schemas';
import { byline } from '@/format/imageTitle';
import { vehicleName } from '@/format/labels';

import CarImage from './CarImage.vue';
import StatusBadge from './StatusBadge.vue';
import VerdictBadge from './VerdictBadge.vue';

const props = defineProps<{ image: Image }>();

const name = computed(() => vehicleName(props.image));
const credit = computed(() => byline(props.image.attribution, props.image.title));
</script>

<template>
  <RouterLink
    :to="{ name: 'image', params: { id: image.id } }"
    class="group focus-ring flex flex-col overflow-hidden rounded-surface border border-line bg-raised transition-colors hover:border-line-strong"
  >
    <div class="relative aspect-[4/3]">
      <CarImage :src="image.thumbnail_url ?? image.source_url" :alt="name" />
      <div class="absolute bottom-2 left-2 flex gap-1">
        <VerdictBadge kind="make" :value="image.make_confirmed" />
        <VerdictBadge kind="year" :value="image.year_confirmed" />
      </div>
    </div>
    <div class="flex flex-1 flex-col gap-1 p-3">
      <div class="flex items-start justify-between gap-2">
        <p class="min-w-0 truncate text-body font-semibold text-ink group-hover:text-accent-text">{{ name }}</p>
        <StatusBadge :status="image.review_status" class="shrink-0" />
      </div>
      <p v-if="credit" class="truncate text-meta text-ink-3">{{ credit }}</p>
    </div>
  </RouterLink>
</template>
