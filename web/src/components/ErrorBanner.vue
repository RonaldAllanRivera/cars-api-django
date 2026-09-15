<script setup lang="ts">
import Icon from './Icon.vue';

defineProps<{ message: string; retry?: () => void }>();
</script>

<template>
  <div role="alert" class="flex items-start gap-3 rounded-surface border border-danger/35 bg-danger/10 px-4 py-3 text-danger-text">
    <Icon name="alert" class="mt-0.5 shrink-0" />
    <p class="min-w-0 flex-1 text-body break-words">{{ message }}</p>
    <button
      v-if="retry"
      type="button"
      class="focus-ring shrink-0 rounded-control px-2 py-0.5 text-meta font-semibold text-danger-text underline-offset-4 hover:underline"
      @click="retry()"
    >
      Try again
    </button>
  </div>
</template>
