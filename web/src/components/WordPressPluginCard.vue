<script setup lang="ts">
import BaseButton from './BaseButton.vue';

/**
 * Presentational. Offers the WordPress plugin; when the browser blocked the
 * download tab, `blockedUrl` is shown as a link the admin can open instead.
 */
defineProps<{ pending: boolean; blockedUrl: string | null; error: string | null }>();
const emit = defineEmits<{ download: [] }>();
</script>

<template>
  <section aria-labelledby="wordpress-plugin-heading" class="rounded-surface border border-line bg-raised p-5">
    <h2 id="wordpress-plugin-heading" class="text-section font-semibold text-ink">WordPress plugin</h2>
    <p class="mt-1 mb-4 text-meta text-ink-2">
      Install <span class="font-semibold text-ink">Cars Images Publisher</span> on your WordPress site so this app can
      publish SEO-ready drafts to it. In WordPress: Plugins, Add New, Upload Plugin.
    </p>
    <BaseButton variant="secondary" size="sm" icon="download" :pending="pending" :disabled="pending" @click="emit('download')">
      Download plugin
    </BaseButton>
    <p v-if="blockedUrl" class="mt-3 text-meta text-ink-2" role="status">
      Your browser blocked the download.
      <a :href="blockedUrl" class="focus-ring font-semibold text-accent-text underline" rel="noopener">Download the zip</a>
      within the next few minutes.
    </p>
    <p v-if="error" class="mt-3 text-meta text-danger" role="alert">{{ error }}</p>
  </section>
</template>
