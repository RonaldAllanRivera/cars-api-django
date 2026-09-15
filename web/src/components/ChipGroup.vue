<script setup lang="ts" generic="T extends string">
import { useId } from 'vue';

/**
 * A single-choice filter. Radio semantics under the chip look: one value is
 * always selected, arrow keys move between options, and screen readers announce
 * "3 of 4" rather than a row of unrelated toggle buttons.
 */
defineProps<{
  label: string;
  options: readonly { value: T; label: string }[];
  hideLabel?: boolean;
}>();

const model = defineModel<T>({ required: true });
const name = useId();
</script>

<template>
  <fieldset class="min-w-0">
    <legend :class="hideLabel ? 'sr-only' : 'mb-1.5 text-meta font-medium text-ink-2'">{{ label }}</legend>
    <div class="flex flex-wrap gap-1.5">
      <label
        v-for="option in options"
        :key="option.value"
        class="relative inline-flex h-8 cursor-pointer items-center rounded-full border px-3 text-meta font-medium transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-accent-text"
        :class="
          model === option.value
            ? 'border-accent bg-accent text-accent-fg'
            : 'border-line-strong bg-sunken/60 text-ink-2 hover:border-ink-3 hover:text-ink'
        "
      >
        <input v-model="model" type="radio" :name="name" :value="option.value" class="sr-only" />
        {{ option.label }}
      </label>
    </div>
  </fieldset>
</template>
