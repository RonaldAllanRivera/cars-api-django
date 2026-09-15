<script setup lang="ts">
import { ref, useId } from 'vue';

import BaseButton from './BaseButton.vue';
import Icon from './Icon.vue';

defineProps<{ pending: boolean }>();
const emit = defineEmits<{ upload: [file: File] }>();

const file = ref<File | null>(null);
const dragging = ref(false);
const localError = ref<string | null>(null);
const input = ref<HTMLInputElement | null>(null);
const id = useId();

/** Loose on purpose: a CSV from a mail client or Drive arrives under many types. The server decides. */
function looksLikeCsv(candidate: File): boolean {
  return /\.(csv|txt)$/i.test(candidate.name) || /csv|text\/plain|ms-excel/.test(candidate.type);
}

function choose(candidate: File | undefined): void {
  localError.value = null;
  if (!candidate) return;

  if (!looksLikeCsv(candidate)) {
    localError.value = `${candidate.name} is not a CSV file.`;

    return;
  }

  file.value = candidate;
}

function onDrop(event: DragEvent): void {
  dragging.value = false;
  choose(event.dataTransfer?.files[0]);
}

function onPick(event: Event): void {
  choose((event.target as HTMLInputElement).files?.[0]);
}

function clear(): void {
  file.value = null;
  if (input.value) input.value.value = '';
}

function submit(): void {
  if (file.value) emit('upload', file.value);
}

defineExpose({ clear });
</script>

<template>
  <div class="flex flex-col gap-3">
    <label
      :for="id"
      class="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-surface border-2 border-dashed px-6 py-8 text-center transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-accent-text"
      :class="dragging ? 'border-accent bg-accent/10' : 'border-line-strong hover:border-ink-3'"
      @dragover.prevent="dragging = true"
      @dragenter.prevent="dragging = true"
      @dragleave.prevent="dragging = false"
      @drop.prevent="onDrop"
    >
      <Icon name="upload" :size="26" :class="dragging ? 'text-accent-text' : 'text-ink-3'" />
      <span class="text-body font-semibold text-ink">
        {{ file ? file.name : 'Drop a CSV here, or choose a file' }}
      </span>
      <span class="text-meta text-ink-3">
        {{ file ? `${(file.size / 1024).toFixed(1)} KB` : 'Columns: Make, Model, Year' }}
      </span>
      <input
        :id="id"
        ref="input"
        type="file"
        accept=".csv,text/csv,text/plain,application/vnd.ms-excel"
        class="sr-only"
        @change="onPick"
      />
    </label>
    <p v-if="localError" role="alert" class="text-meta text-danger-text">{{ localError }}</p>
    <div class="flex flex-wrap items-center gap-2">
      <BaseButton icon="upload" :disabled="!file" :pending="pending" @click="submit">Import CSV</BaseButton>
      <BaseButton v-if="file && !pending" variant="ghost" @click="clear">Clear</BaseButton>
      <p v-if="pending" class="text-meta text-ink-3">Parsing and queueing. Large files take a moment.</p>
    </div>
  </div>
</template>
