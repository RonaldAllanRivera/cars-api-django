import { describe, expect, it } from 'vitest';

import { flush, mockApi } from '@/test/http';
import { waitFor, withSetup } from '@/test/mount';

import { useBulkRun } from '../useBulkRun';

const chunk = (over: Record<string, unknown> = {}) => ({
  outcomes: [{ id: 1, make: 'Honda', model: 'Civic', from_year: 1998, outcome: 'completed' }],
  ran_seconds: 1,
  remaining: 0,
  blocked: null,
  ...over,
});

/** Replies with each body in turn, repeating the last. */
function sequence(...bodies: unknown[]) {
  let index = 0;

  return () => ({ body: bodies[Math.min(index++, bodies.length - 1)] });
}

describe('useBulkRun', () => {
  it('keeps asking while the server reports work remaining', async () => {
    const api = mockApi({
      'POST /searches/run-chunk': sequence(chunk({ remaining: 2 }), chunk({ remaining: 1 }), chunk({ remaining: 0 })),
    });
    const { result: run } = withSetup(() => useBulkRun(12));

    run.start(3);

    await waitFor(() => expect(run.status.value).toBe('finished'));
    expect(api.calls('POST /searches/run-chunk')).toHaveLength(3);
    expect(api.requests[0]?.body).toEqual({ csv_import_id: 12 });
    expect(run.processed.value).toBe(3);
    expect(run.percent.value).toBe(100);
  });

  it('does not send anything for an import with no work', async () => {
    const api = mockApi({});
    const { result: run } = withSetup(() => useBulkRun(12));

    run.start(0);
    await flush();

    expect(run.status.value).toBe('finished');
    expect(api.requests).toHaveLength(0);
  });

  it('stops on a block rather than retrying inside the window', async () => {
    const api = mockApi({
      'POST /searches/run-chunk': { body: chunk({ remaining: 5, blocked: { status: 429, retry_after_seconds: 600 } }) },
    });
    const { result: run } = withSetup(() => useBulkRun(12));

    run.start(6);

    await waitFor(() => expect(run.status.value).toBe('blocked'));
    await flush();
    expect(api.calls('POST /searches/run-chunk')).toHaveLength(1);
    expect(run.blocked.value).toEqual({ status: 429, retry_after_seconds: 600 });
    expect(run.remaining.value).toBe(5);
  });

  it('resumes from a block and carries the counts on', async () => {
    mockApi({
      'POST /searches/run-chunk': sequence(
        chunk({ remaining: 1, blocked: { status: 429, retry_after_seconds: null } }),
        chunk({ remaining: 0 }),
      ),
    });
    const { result: run } = withSetup(() => useBulkRun(12));

    run.start(2);
    await waitFor(() => expect(run.status.value).toBe('blocked'));

    run.resume();

    await waitFor(() => expect(run.status.value).toBe('finished'));
    expect(run.processed.value).toBe(2);
    expect(run.blocked.value).toBeNull();
  });

  it('counts failures separately and lists the newest outcome first', async () => {
    mockApi({
      'POST /searches/run-chunk': {
        body: chunk({
          outcomes: [
            { id: 1, make: 'Audi', model: null, from_year: 1998, outcome: 'completed' },
            { id: 2, make: 'BMW', model: 'M3', from_year: 1999, outcome: 'failed' },
          ],
          remaining: 0,
        }),
      },
    });
    const { result: run } = withSetup(() => useBulkRun(12));

    run.start(2);

    await waitFor(() => expect(run.status.value).toBe('finished'));
    expect(run.processed.value).toBe(1);
    expect(run.failed.value).toBe(1);
    expect(run.feed.value.map((entry) => entry.make)).toEqual(['BMW', 'Audi']);
  });

  it('stops sending when paused, and continues when resumed', async () => {
    let release!: () => void;
    let calls = 0;
    mockApi({
      'POST /searches/run-chunk': async () => {
        calls += 1;
        // Hold the first chunk open so the pause lands while it is in flight.
        if (calls === 1) await new Promise<void>((resolve) => (release = resolve));

        return { body: chunk({ remaining: calls >= 3 ? 0 : 10 }) };
      },
    });
    const { result: run } = withSetup(() => useBulkRun(12));

    run.start(12);
    await waitFor(() => expect(calls).toBe(1));

    run.pause();
    expect(run.status.value).toBe('paused');
    release();

    // The in-flight chunk still counts - the server did the work - but no new one goes out.
    await waitFor(() => expect(run.processed.value).toBe(1));
    await new Promise((resolve) => setTimeout(resolve, 40));
    expect(calls).toBe(1);
    expect(run.status.value).toBe('paused');

    run.resume();

    await waitFor(() => expect(run.status.value).toBe('finished'));
    expect(calls).toBe(3);
  });

  it('pauses rather than failing when a request errors, keeping the reason', async () => {
    mockApi({ 'POST /searches/run-chunk': { status: 500, body: { message: 'Server Error' } } });
    const { result: run } = withSetup(() => useBulkRun(12));

    run.start(4);

    await waitFor(() => expect(run.status.value).toBe('paused'));
    expect(run.lastError.value).toBe('Server Error');
    expect(run.remaining.value).toBe(4);
  });

  it('grows the total instead of overflowing when rows appear mid-run', async () => {
    mockApi({ 'POST /searches/run-chunk': sequence(chunk({ remaining: 5 }), chunk({ remaining: 0 })) });
    const { result: run } = withSetup(() => useBulkRun(12));

    run.start(2);

    await waitFor(() => expect(run.status.value).toBe('finished'));
    expect(run.total.value).toBe(6);
    expect(run.percent.value).toBeLessThanOrEqual(100);
  });

  it('refreshes the coverage and query caches when a run stops', async () => {
    mockApi({ 'POST /searches/run-chunk': { body: chunk({ remaining: 0 }) } });
    const { result: run, queryClient } = withSetup(() => useBulkRun(12));
    queryClient.setQueryData(['imports', 12], { id: 12 });
    queryClient.setQueryData(['searches', { csv_import_id: 12 }], { pages: [] });

    run.start(1);

    await waitFor(() => expect(run.status.value).toBe('finished'));
    expect(queryClient.getQueryState(['imports', 12])?.isInvalidated).toBe(true);
    expect(queryClient.getQueryState(['searches', { csv_import_id: 12 }])?.isInvalidated).toBe(true);
  });
});
