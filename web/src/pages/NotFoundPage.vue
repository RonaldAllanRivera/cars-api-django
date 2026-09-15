<script setup lang="ts">
import { RouterLink } from 'vue-router';

import { useDocumentTitle } from '@/composables/useDocumentTitle';

useDocumentTitle('Not found');
</script>

<template>
  <main class="flex min-h-dvh flex-col items-start justify-center gap-4 px-6 sm:items-center sm:text-center">
    <p class="type-display text-[5rem] leading-none text-line-strong">404</p>
    <h1 class="type-display text-title text-ink">This page does not exist</h1>
    <p class="text-body text-ink-2">The link may be out of date.</p>
    <RouterLink to="/search" class="focus-ring rounded-control font-semibold text-accent-text hover:underline">
      Go to Search
    </RouterLink>
  </main>
</template>
