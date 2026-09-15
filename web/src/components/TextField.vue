<script setup lang="ts">
import { useId } from 'vue';

defineOptions({ inheritAttrs: false });

withDefaults(
  defineProps<{
    label: string;
    hint?: string;
    error?: string | null;
    optional?: boolean;
  }>(),
  { hint: undefined, error: null, optional: false },
);

const model = defineModel<string>({ default: '' });
const id = useId();
</script>

<template>
  <div class="flex flex-col gap-1.5">
    <label :for="id" class="text-meta font-medium text-ink-2">
      {{ label }}
      <span v-if="optional" class="font-normal text-ink-3">(optional)</span>
    </label>
    <input
      :id="id"
      v-model="model"
      v-bind="$attrs"
      :aria-invalid="error ? 'true' : undefined"
      :aria-describedby="error || hint ? `${id}-note` : undefined"
      class="h-10 w-full rounded-control border bg-sunken px-3 text-body text-ink placeholder:text-ink-3/60 transition-colors focus:outline-none focus-visible:outline-2 focus-visible:outline-offset-0 focus-visible:outline-accent-text"
      :class="error ? 'border-danger/70' : 'border-line-strong hover:border-ink-3'"
    />
    <p v-if="error" :id="`${id}-note`" class="text-meta text-danger-text">{{ error }}</p>
    <p v-else-if="hint" :id="`${id}-note`" class="text-meta text-ink-3">{{ hint }}</p>
  </div>
</template>
