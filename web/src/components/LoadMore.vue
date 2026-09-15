<script setup lang="ts">
import { useInfiniteScroll } from '@/composables/useInfiniteScroll';

import BaseButton from './BaseButton.vue';

/**
 * The footer of every cursor list: scrolls itself into the next page when it
 * comes into view, and keeps a real button for keyboards, screen readers and
 * anyone who would rather decide.
 */
const props = withDefaults(
  defineProps<{
    hasNextPage: boolean;
    isFetchingNextPage: boolean;
    fetchNextPage: () => unknown;
    /** Load on scroll. Off where an unasked-for page would push content away (the error log). */
    auto?: boolean;
  }>(),
  // A missing boolean prop is cast to false, so the default must be explicit.
  { auto: true },
);

const load = () => {
  if (props.hasNextPage && !props.isFetchingNextPage) void props.fetchNextPage();
};

const sentinel = useInfiniteScroll(() => {
  if (props.auto) load();
});
</script>

<template>
  <div v-if="hasNextPage" ref="sentinel" class="mt-6 flex justify-center">
    <BaseButton variant="secondary" :pending="isFetchingNextPage" @click="load">Load more</BaseButton>
  </div>
</template>
