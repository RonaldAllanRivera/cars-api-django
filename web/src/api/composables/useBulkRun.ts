import { useQueryClient } from '@tanstack/vue-query';
import { computed, onScopeDispose, ref, shallowRef, toValue } from 'vue';
import type { MaybeRefOrGetter } from 'vue';

import { apiRequest, errorMessage } from '../client';
import { queryKeys } from '../queryKeys';
import { RunChunkResponseSchema } from '../schemas';
import type { RunChunkResponse, RunOutcome } from '../schemas';

export type RunStatus = 'idle' | 'running' | 'paused' | 'blocked' | 'finished';

export interface FeedEntry extends RunOutcome {
  /** Unique per feed row: the same search can fail in one chunk and run in a later one. */
  key: string;
}

/** Enough to see what just happened without growing without bound on a long run. */
const FEED_LIMIT = 60;

/**
 * Drives a bulk run from the browser, one chunk at a time.
 *
 * No polling interval: a chunk already occupies up to ten seconds server-side,
 * so the next goes out when the previous returns. Nothing is queued locally -
 * each request re-selects from the database, and the server's `remaining` is
 * authoritative - so pausing, reloading or resuming tomorrow all pick up
 * exactly where the rows are.
 */
export function useBulkRun(csvImportId: MaybeRefOrGetter<number>) {
  const queryClient = useQueryClient();

  const status = ref<RunStatus>('idle');
  const processed = ref(0);
  const failed = ref(0);
  const total = ref(0);
  const remaining = ref(0);
  const elapsed = ref(0);
  const feed = shallowRef<FeedEntry[]>([]);
  const blocked = shallowRef<RunChunkResponse['blocked']>(null);
  const blockedAt = ref<number | null>(null);
  const lastError = ref<string | null>(null);

  let inFlight = false;
  let disposed = false;
  let sequence = 0;

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.import(toValue(csvImportId)) });
    void queryClient.invalidateQueries({ queryKey: ['searches'] });
    void queryClient.invalidateQueries({ queryKey: queryKeys.health() });
  };

  async function loop(): Promise<void> {
    // One loop at a time. A resume that lands while a chunk is still in flight
    // needs no loop of its own: the running one sees the status and carries on.
    if (inFlight) return;
    inFlight = true;

    try {
      while (status.value === 'running' && !disposed) {
        const chunk = await apiRequest('/searches/run-chunk', {
          method: 'POST',
          body: { csv_import_id: toValue(csvImportId) },
          schema: RunChunkResponseSchema,
        });

        if (disposed) return;

        const entries = chunk.outcomes.map((outcome) => ({ ...outcome, key: `${sequence++}` }));
        feed.value = [...entries.reverse(), ...feed.value].slice(0, FEED_LIMIT);
        processed.value += chunk.outcomes.filter((o) => o.outcome === 'completed').length;
        failed.value += chunk.outcomes.filter((o) => o.outcome === 'failed').length;
        remaining.value = chunk.remaining;
        elapsed.value += chunk.ran_seconds;
        // A run that meets rows added since it started grows its denominator
        // rather than overflowing the bar.
        total.value = Math.max(total.value, processed.value + failed.value + chunk.remaining);

        // Coverage tiles follow the run chunk by chunk rather than jumping at the end.
        void queryClient.invalidateQueries({ queryKey: queryKeys.import(toValue(csvImportId)) });

        if (chunk.blocked) {
          // Not a retry case: asking again inside the window is how a short
          // block becomes a long one.
          blocked.value = chunk.blocked;
          blockedAt.value = Date.now();
          status.value = 'blocked';
          invalidate();
        } else if (chunk.remaining === 0) {
          status.value = 'finished';
          invalidate();
        }
        // A pause that landed mid-chunk has already set status; the loop exits.
      }
    } catch (error) {
      // A failed request is not a failed run: stop and let the user decide. The
      // rows are unchanged, so resuming continues from the same place.
      if (!disposed) {
        lastError.value = errorMessage(error, 'The run stopped because a request failed.');
        status.value = 'paused';
      }
    } finally {
      inFlight = false;
    }
  }

  function start(notYetRun: number): void {
    // The total comes from coverage, so the bar has a denominator before the
    // first chunk returns rather than jumping once it does.
    total.value = notYetRun;
    remaining.value = notYetRun;
    processed.value = 0;
    failed.value = 0;
    elapsed.value = 0;
    feed.value = [];
    blocked.value = null;
    blockedAt.value = null;
    lastError.value = null;
    status.value = notYetRun > 0 ? 'running' : 'finished';
    void loop();
  }

  function pause(): void {
    if (status.value !== 'running') return;
    status.value = 'paused';
    invalidate();
  }

  function resume(): void {
    if (status.value !== 'paused' && status.value !== 'blocked') return;
    blocked.value = null;
    blockedAt.value = null;
    lastError.value = null;
    status.value = 'running';
    void loop();
  }

  onScopeDispose(() => {
    disposed = true;
  });

  const done = computed(() => processed.value + failed.value);
  const percent = computed(() =>
    total.value > 0 ? Math.min(100, Math.round((100 * done.value) / total.value)) : 0,
  );
  /** From this run's observed pace, falling back to two seconds a query until measured. */
  const secondsRemaining = computed(() => {
    const perQuery = done.value > 0 && elapsed.value > 0 ? elapsed.value / done.value : 2;

    return Math.ceil(remaining.value * perQuery);
  });

  return {
    status,
    processed,
    failed,
    total,
    remaining,
    done,
    percent,
    secondsRemaining,
    feed,
    blocked,
    blockedAt,
    lastError,
    start,
    pause,
    resume,
  };
}

export type BulkRun = ReturnType<typeof useBulkRun>;
