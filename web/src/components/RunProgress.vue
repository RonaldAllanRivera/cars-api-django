<script setup lang="ts">
import { computed, onScopeDispose, ref, watch } from 'vue';
import type { UnwrapNestedRefs } from 'vue';

import type { BulkRun } from '@/api/composables/useBulkRun';
import { humanSeconds, plural } from '@/format/time';

import BaseButton from './BaseButton.vue';
import Icon from './Icon.vue';

/**
 * Presentational. The run itself lives in useBulkRun, where the behaviour
 * worth testing is.
 */
const props = defineProps<{ run: UnwrapNestedRefs<BulkRun> }>();

const now = ref(Date.now());
let ticker: ReturnType<typeof setInterval> | undefined;

// A live countdown only while there is a window to count down.
watch(
  () => props.run.status === 'blocked' && props.run.blocked?.retry_after_seconds != null,
  (counting) => {
    clearInterval(ticker);
    if (!counting) return;
    now.value = Date.now();
    ticker = setInterval(() => (now.value = Date.now()), 1000);
  },
  { immediate: true },
);
onScopeDispose(() => clearInterval(ticker));

const waitLeft = computed(() => {
  const { blocked, blockedAt } = props.run;
  if (!blocked?.retry_after_seconds || blockedAt === null) return 0;

  return Math.max(0, Math.ceil((blockedAt + blocked.retry_after_seconds * 1000 - now.value) / 1000));
});

const isBlocked = computed(() => props.run.status === 'blocked');

const headline = computed(() => {
  switch (props.run.status) {
    case 'running':
      return 'Running';
    case 'paused':
      return 'Paused';
    case 'blocked':
      return 'Stopped by Wikimedia';
    case 'finished':
      return 'Run complete';
    default:
      return '';
  }
});

// Announced once per chunk, not per second: often enough to follow, rarely
// enough not to talk over everything else.
const announcement = computed(() => {
  const { status, done, total } = props.run;
  if (status === 'idle') return '';
  if (status === 'blocked') return `Run stopped: Wikimedia is rate-limiting. ${done} of ${total} done.`;

  return `${headline.value}. ${done} of ${total} queries done.`;
});
</script>

<template>
  <section
    v-if="run.status !== 'idle'"
    aria-labelledby="run-progress-heading"
    class="overflow-hidden rounded-surface border"
    :class="isBlocked ? 'border-danger/40 bg-danger/[0.06]' : 'border-line-strong bg-raised'"
  >
    <p class="sr-only" aria-live="polite" aria-atomic="true">{{ announcement }}</p>

    <div class="flex flex-col gap-5 p-5">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id="run-progress-heading" class="flex items-center gap-2 text-meta font-semibold" :class="isBlocked ? 'text-danger-text' : 'text-ink-2'">
            <span
              v-if="run.status === 'running'"
              class="size-2 animate-pulse rounded-full bg-accent"
              aria-hidden="true"
            />
            {{ headline }}
          </h2>
          <p class="mt-1 type-display text-figure leading-none text-ink">
            {{ run.done }}<span class="text-ink-3"> / {{ run.total }}</span>
          </p>
        </div>

        <div class="flex items-center gap-2">
          <p v-if="run.status === 'running'" class="text-meta text-ink-2">
            about {{ humanSeconds(run.secondsRemaining) }} left
          </p>
          <BaseButton v-if="run.status === 'running'" variant="secondary" icon="pause" @click="run.pause()">
            Pause
          </BaseButton>
          <BaseButton v-else-if="run.status === 'paused'" icon="play" @click="run.resume()">Resume</BaseButton>
          <BaseButton
            v-else-if="isBlocked"
            :variant="waitLeft > 0 ? 'secondary' : 'primary'"
            :disabled="waitLeft > 0"
            icon="play"
            @click="run.resume()"
          >
            {{ waitLeft > 0 ? `Resume in ${humanSeconds(waitLeft)}` : 'Resume' }}
          </BaseButton>
        </div>
      </div>

      <div>
        <div
          role="progressbar"
          aria-label="Queries run"
          :aria-valuenow="run.percent"
          aria-valuemin="0"
          aria-valuemax="100"
          :aria-valuetext="`${run.done} of ${run.total} queries`"
          class="relative h-2.5 overflow-hidden rounded-full bg-sunken"
        >
          <div
            class="h-full rounded-full transition-[width] duration-700 ease-out"
            :class="isBlocked ? 'bg-danger' : run.status === 'finished' ? 'bg-success' : 'bg-accent'"
            :style="{ width: `${run.percent}%` }"
          />
          <!-- Quarter marks, so progress can be judged at a glance. -->
          <div class="pointer-events-none absolute inset-0 flex justify-evenly" aria-hidden="true">
            <span v-for="n in 3" :key="n" class="h-full w-px bg-surface/60" />
          </div>
        </div>
        <dl class="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-meta">
          <div class="flex gap-1.5"><dt class="text-ink-3">Completed</dt><dd class="font-semibold text-ink tabular-nums">{{ run.processed }}</dd></div>
          <div class="flex gap-1.5">
            <dt class="text-ink-3">Failed</dt>
            <dd class="font-semibold tabular-nums" :class="run.failed > 0 ? 'text-danger-text' : 'text-ink'">{{ run.failed }}</dd>
          </div>
          <div class="flex gap-1.5"><dt class="text-ink-3">Remaining</dt><dd class="font-semibold text-ink tabular-nums">{{ run.remaining }}</dd></div>
        </dl>
      </div>

      <p v-if="isBlocked" class="text-body text-danger-text">
        Wikimedia is rate-limiting this server (HTTP {{ run.blocked?.status }}).
        {{
          run.blocked?.retry_after_seconds
            ? `It asked for ${humanSeconds(run.blocked.retry_after_seconds)} before the next request.`
            : 'It did not say for how long, so wait a few minutes.'
        }}
        Resuming picks up where this left off.
      </p>
      <p v-else-if="run.lastError" class="text-body text-danger-text">
        {{ run.lastError }} Nothing was lost; resume to continue.
      </p>
      <p v-else-if="run.failed > 0" class="text-meta text-ink-2">
        {{ plural(run.failed, 'query', 'queries') }} failed. They stay runnable and are picked up by the next run.
      </p>
      <p v-else-if="run.status === 'running'" class="text-meta text-ink-3">
        Keep this tab open while the run is going. Pause finishes the current batch first.
      </p>
    </div>

    <div v-if="run.feed.length > 0" class="border-t border-line">
      <h3 class="px-5 pt-3 text-meta font-medium text-ink-2">Latest results</h3>
      <ol class="max-h-64 overflow-y-auto px-5 pt-2 pb-4" aria-label="Latest results">
        <TransitionGroup enter-from-class="opacity-0 -translate-y-1" enter-active-class="transition duration-300">
          <li v-for="entry in run.feed" :key="entry.key" class="flex items-center gap-2.5 border-b border-line/60 py-1.5 text-meta last:border-0">
            <Icon
              :name="entry.outcome === 'completed' ? 'check' : 'x'"
              :size="16"
              :class="entry.outcome === 'completed' ? 'text-success-text' : 'text-danger-text'"
            />
            <span class="min-w-0 flex-1 truncate text-ink">{{ entry.make }} {{ entry.model ?? '' }}</span>
            <span class="text-ink-3 tabular-nums">{{ entry.from_year }}</span>
            <span class="sr-only">{{ entry.outcome }}</span>
          </li>
        </TransitionGroup>
      </ol>
    </div>
  </section>
</template>
