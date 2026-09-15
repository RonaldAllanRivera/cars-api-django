<script setup lang="ts">
import { computed } from 'vue';

import { errorMessage } from '@/api/client';
import type { CursorPage, Image } from '@/api/schemas';

import EmptyState from './EmptyState.vue';
import ErrorBanner from './ErrorBanner.vue';
import ImageCard from './ImageCard.vue';
import LoadMore from './LoadMore.vue';
import SkeletonBlock from './SkeletonBlock.vue';

const props = defineProps<{
  pages: CursorPage<Image>[] | undefined;
  isPending: boolean;
  isError: boolean;
  error: unknown;
  hasNextPage: boolean;
  isFetchingNextPage: boolean;
  fetchNextPage: () => unknown;
  refetch: () => unknown;
  emptyTitle: string;
  emptyHint?: string;
}>();

const images = computed(() => props.pages?.flatMap((page) => page.data) ?? []);
</script>

<template>
  <div>
    <!-- A failed fetch must not fall through to "nothing matched". -->
    <ErrorBanner v-if="isError && images.length === 0" :message="errorMessage(error)" :retry="refetch" />

    <ul
      v-else-if="isPending"
      class="grid grid-cols-[repeat(auto-fill,minmax(min(100%,15rem),1fr))] gap-4"
      aria-label="Loading images"
    >
      <li v-for="n in 8" :key="n" class="overflow-hidden rounded-surface border border-line bg-raised">
        <SkeletonBlock class="aspect-[4/3] rounded-none" />
        <div class="space-y-2 p-3">
          <SkeletonBlock class="h-4 w-2/3 rounded" />
          <SkeletonBlock class="h-3 w-1/2 rounded" />
        </div>
      </li>
    </ul>

    <EmptyState v-else-if="images.length === 0" :title="emptyTitle" :hint="emptyHint" icon="images">
      <slot name="empty" />
    </EmptyState>

    <template v-else>
      <ul class="grid grid-cols-[repeat(auto-fill,minmax(min(100%,15rem),1fr))] gap-4">
        <li v-for="image in images" :key="image.id" class="flex">
          <ImageCard :image="image" class="w-full" />
        </li>
      </ul>
      <LoadMore :has-next-page="hasNextPage" :is-fetching-next-page="isFetchingNextPage" :fetch-next-page="fetchNextPage" />
    </template>
  </div>
</template>
