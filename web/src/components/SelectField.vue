<script setup lang="ts" generic="T extends string">
import { useId } from 'vue';

import Icon from './Icon.vue';

defineProps<{
  label: string;
  options: readonly { value: T; label: string }[];
  hint?: string;
  error?: string | null;
}>();

const model = defineModel<T>({ required: true });
const id = useId();
</script>

<template>
  <div class="flex flex-col gap-1.5">
    <label :for="id" class="text-meta font-medium text-ink-2">{{ label }}</label>
    <div class="relative">
      <select
        :id="id"
        v-model="model"
        :aria-describedby="error || hint ? `${id}-note` : undefined"
        class="h-10 w-full appearance-none rounded-control border border-line-strong bg-sunken pr-9 pl-3 text-body text-ink transition-colors hover:border-ink-3 focus:outline-none focus-visible:outline-2 focus-visible:outline-offset-0 focus-visible:outline-accent-text"
      >
        <option v-for="option in options" :key="option.value" :value="option.value">
          {{ option.label }}
        </option>
      </select>
      <Icon name="chevron" :size="16" class="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 text-ink-3" />
    </div>
    <p v-if="error" :id="`${id}-note`" class="text-meta text-danger-text">{{ error }}</p>
    <p v-else-if="hint" :id="`${id}-note`" class="text-meta text-ink-3">{{ hint }}</p>
  </div>
</template>
