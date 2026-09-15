<script setup lang="ts">
import { ref, watch } from 'vue';

import Icon from './Icon.vue';

/**
 * An <img> that fades in once decoded and admits when it cannot load - a
 * Wikimedia file can be deleted after the API recorded it, and a broken-image
 * glyph in a grid of photographs reads as a bug in this app.
 */
const props = withDefaults(
  defineProps<{
    src: string;
    alt: string;
    fit?: 'cover' | 'contain';
    eager?: boolean;
    /** A smaller copy - usually the cached thumbnail - shown while a full-size original loads. */
    placeholder?: string | null;
  }>(),
  { fit: 'cover', eager: false, placeholder: null },
);

const loaded = ref(false);
const failed = ref(false);

watch(
  () => props.src,
  () => {
    loaded.value = false;
    failed.value = false;
  },
);
</script>

<template>
  <div class="relative h-full w-full overflow-hidden bg-sunken">
    <img
      v-if="!loaded && !failed && placeholder && placeholder !== src"
      :src="placeholder"
      alt=""
      aria-hidden="true"
      referrerpolicy="no-referrer"
      class="absolute inset-0 h-full w-full"
      :class="fit === 'cover' ? 'object-cover' : 'object-contain'"
    />
    <div v-else-if="!loaded && !failed" class="skeleton absolute inset-0" aria-hidden="true" />
    <div v-if="failed" class="absolute inset-0 flex flex-col items-center justify-center gap-1 text-ink-3">
      <Icon name="images" :size="24" />
      <span class="text-micro">Image unavailable</span>
    </div>
    <img
      v-else
      :src="src"
      :alt="alt"
      :loading="eager ? 'eager' : 'lazy'"
      decoding="async"
      referrerpolicy="no-referrer"
      class="h-full w-full transition-opacity duration-300"
      :class="[fit === 'cover' ? 'object-cover' : 'object-contain', loaded ? 'opacity-100' : 'opacity-0']"
      @load="loaded = true"
      @error="failed = true"
    />
  </div>
</template>
