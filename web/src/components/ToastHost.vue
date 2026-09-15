<script setup lang="ts">
import { useToasts } from '@/composables/useToast';

import Icon from './Icon.vue';

const { toasts, dismiss } = useToasts();

const TONE = {
  success: 'text-success-text',
  error: 'text-danger-text',
  info: 'text-info-text',
} as const;
const ICON = { success: 'check', error: 'alert', info: 'clock' } as const;
</script>

<template>
  <div
    class="pointer-events-none fixed inset-x-4 bottom-20 z-50 flex flex-col items-stretch gap-2 sm:inset-x-auto sm:right-6 sm:bottom-6 sm:w-96"
    aria-live="polite"
    aria-relevant="additions"
  >
    <TransitionGroup
      enter-from-class="translate-y-2 opacity-0"
      enter-active-class="transition duration-200 ease-out"
      leave-active-class="transition duration-150 ease-in"
      leave-to-class="opacity-0"
    >
      <div
        v-for="toast in toasts"
        :key="toast.id"
        :role="toast.tone === 'error' ? 'alert' : 'status'"
        class="pointer-events-auto flex items-start gap-3 rounded-surface border border-line-strong bg-raised px-4 py-3 shadow-[0_12px_32px_-12px_rgb(0_0_0/0.8)]"
      >
        <Icon :name="ICON[toast.tone]" :class="TONE[toast.tone]" class="mt-0.5 shrink-0" />
        <div class="min-w-0 flex-1">
          <p class="text-body text-ink">{{ toast.message }}</p>
          <a
            v-if="toast.action"
            :href="toast.action.href"
            target="_blank"
            rel="noopener noreferrer"
            class="focus-ring mt-1 inline-flex items-center gap-1 rounded-control text-meta font-semibold text-accent-text hover:underline"
          >
            {{ toast.action.label }}
            <Icon name="external" :size="14" />
          </a>
        </div>
        <button
          type="button"
          class="focus-ring -mr-1 rounded-control p-1 text-ink-3 hover:text-ink"
          aria-label="Dismiss notification"
          @click="dismiss(toast.id)"
        >
          <Icon name="x" :size="16" />
        </button>
      </div>
    </TransitionGroup>
  </div>
</template>
