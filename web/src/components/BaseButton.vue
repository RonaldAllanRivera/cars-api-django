<script setup lang="ts">
import { computed } from 'vue';

import Icon from './Icon.vue';
import type { IconName } from './Icon.vue';

const props = withDefaults(
  defineProps<{
    variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
    size?: 'sm' | 'md' | 'lg';
    type?: 'button' | 'submit';
    pending?: boolean;
    disabled?: boolean;
    icon?: IconName;
    block?: boolean;
  }>(),
  { variant: 'primary', size: 'md', type: 'button', pending: false, disabled: false, block: false },
);

const VARIANTS = {
  primary:
    'bg-accent text-accent-fg hover:bg-accent-text disabled:bg-sunken disabled:text-ink-3 disabled:hover:bg-sunken',
  secondary:
    'bg-sunken text-ink border border-line-strong hover:border-ink-3 disabled:text-ink-3 disabled:hover:border-line-strong',
  ghost: 'text-ink-2 hover:text-ink hover:bg-sunken/60 disabled:text-ink-3',
  danger:
    'bg-danger/12 text-danger-text border border-danger/35 hover:bg-danger/20 disabled:opacity-50',
} as const;

const SIZES = {
  sm: 'h-8 px-3 text-meta gap-1.5',
  md: 'h-10 px-4 text-body gap-2',
  lg: 'h-12 px-5 text-body gap-2',
} as const;

const classes = computed(() => [
  'focus-ring inline-flex items-center justify-center rounded-control font-semibold whitespace-nowrap transition-colors disabled:cursor-not-allowed',
  VARIANTS[props.variant],
  SIZES[props.size],
  props.block ? 'w-full' : '',
]);
</script>

<template>
  <button :type="type" :class="classes" :disabled="disabled || pending" :aria-busy="pending || undefined">
    <span
      v-if="pending"
      class="size-4 animate-spin rounded-full border-2 border-current border-r-transparent"
      aria-hidden="true"
    />
    <Icon v-else-if="icon" :name="icon" :size="size === 'sm' ? 16 : 18" />
    <slot />
  </button>
</template>
