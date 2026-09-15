import { useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useRef, useState } from 'react';

import { apiRequest } from '../client';
import { queryKeys } from '../queryKeys';
import { RunChunkResponseSchema } from '../schemas';
import type { RunChunkResponse, RunOutcome } from '../schemas';

export type RunStatus = 'idle' | 'running' | 'paused' | 'blocked' | 'finished';

type Blocked = RunChunkResponse['blocked'];

/**
 * Drives a bulk run from the client, one chunk at a time.
 *
 * No polling interval. A chunk request already occupies up to ten seconds
 * server-side, so the next goes out when the previous returns - Livewire needs
 * a timer because the *server* drives its loop; here the client does.
 *
 * Nothing is queued locally. Each request re-selects from the database, so the
 * hook only tracks what to display: the server's `remaining` is authoritative.
 *
 * A run stops when the app is backgrounded, because an Expo app's JS timers
 * are suspended rather than throttled. That is deliberate, and it is why
 * resuming has to be cheap: `coverage.not_run` is the remaining work, and
 * starting again picks up exactly there.
 */
export function useBulkRun(csvImportId: number) {
  const queryClient = useQueryClient();

  const [status, setStatus] = useState<RunStatus>('idle');
  const [processed, setProcessed] = useState(0);
  const [failed, setFailed] = useState(0);
  const [total, setTotal] = useState(0);
  const [remaining, setRemaining] = useState(0);
  const [lastOutcomes, setLastOutcomes] = useState<RunOutcome[]>([]);
  const [blocked, setBlocked] = useState<Blocked>(null);
  const [elapsed, setElapsed] = useState(0);

  // A ref as well as state: the loop below reads it after an await, where a
  // captured state value would be the one from before the request went out.
  const statusRef = useRef<RunStatus>('idle');
  const inFlight = useRef(false);

  const setRunStatus = useCallback((next: RunStatus) => {
    statusRef.current = next;
    setStatus(next);
  }, []);

  const start = useCallback(
    (notYetRun: number) => {
      // The total comes from coverage, so the bar has a denominator before the
      // first chunk returns rather than jumping once it does.
      setTotal(notYetRun);
      setRemaining(notYetRun);
      setProcessed(0);
      setFailed(0);
      setElapsed(0);
      setBlocked(null);
      setLastOutcomes([]);
      setRunStatus(notYetRun > 0 ? 'running' : 'finished');
    },
    [setRunStatus],
  );

  const pause = useCallback(() => setRunStatus('paused'), [setRunStatus]);
  const resume = useCallback(() => setRunStatus('running'), [setRunStatus]);

  useEffect(() => {
    if (status !== 'running' || inFlight.current) return;

    let cancelled = false;

    const runChunk = async () => {
      inFlight.current = true;

      try {
        const chunk = await apiRequest('/searches/run-chunk', {
          method: 'POST',
          body: { csv_import_id: csvImportId },
          schema: RunChunkResponseSchema,
        });

        if (cancelled) return;

        setLastOutcomes(chunk.outcomes);
        setProcessed((n) => n + chunk.outcomes.filter((o) => o.outcome === 'completed').length);
        setFailed((n) => n + chunk.outcomes.filter((o) => o.outcome === 'failed').length);
        setRemaining(chunk.remaining);
        setElapsed((s) => s + chunk.ran_seconds);

        if (chunk.blocked) {
          // Not a retry case. Asking again inside the window is how a short
          // block becomes a long one.
          setBlocked(chunk.blocked);
          setRunStatus('blocked');
        } else if (chunk.remaining === 0) {
          setRunStatus('finished');
        } else if (statusRef.current === 'paused') {
          // Pause landed while this chunk was in flight. The work it did is
          // real and counted; nothing new goes out.
          setRunStatus('paused');
        }
      } catch {
        // A failed request is not a failed run: stop, and let the user decide.
        // The rows are unchanged, so starting again resumes from the same place.
        if (!cancelled) setRunStatus('paused');
      } finally {
        inFlight.current = false;
      }
    };

    void runChunk();

    return () => {
      cancelled = true;
    };
    // `remaining` is in the deps so a completed chunk retriggers the effect;
    // that is the loop.
  }, [status, remaining, csvImportId, setRunStatus]);

  // Coverage and the query list are both stale once a run stops.
  useEffect(() => {
    if (status !== 'finished' && status !== 'blocked') return;

    void queryClient.invalidateQueries({ queryKey: queryKeys.import(csvImportId) });
    void queryClient.invalidateQueries({ queryKey: ['searches'] });
  }, [status, csvImportId, queryClient]);

  /**
   * From this run's observed pace, as ListSearchQueries::runSecondsRemaining()
   * does - falling back to the configured courtesy pause plus a second of work
   * until enough has run to measure, so the first estimate is not wild.
   */
  const done = processed + failed;
  const perQuery = done > 0 && elapsed > 0 ? elapsed / done : 2;
  const secondsRemaining = Math.ceil(remaining * perQuery);

  return {
    status,
    processed,
    failed,
    total,
    remaining,
    secondsRemaining,
    lastOutcomes,
    blocked,
    start,
    pause,
    resume,
  };
}
