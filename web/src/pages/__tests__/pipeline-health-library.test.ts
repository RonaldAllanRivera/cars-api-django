import { beforeEach, describe, expect, it, vi } from 'vitest';

import { setSessionForTests } from '@/auth/auth';
import { mockApi } from '@/test/http';
import { mountAt, waitFor } from '@/test/mount';

import errors from '../../api/__fixtures__/errors.json';
import health from '../../api/__fixtures__/health.json';
import images from '../../api/__fixtures__/images.json';
import csvImport from '../../api/__fixtures__/import.json';
import imports from '../../api/__fixtures__/imports.json';
import me from '../../api/__fixtures__/me.json';
import searches from '../../api/__fixtures__/searches.json';

beforeEach(() => setSessionForTests(me.data));

describe('import page', () => {
  it('shows coverage, filters queries by a tile and runs the import to the end', async () => {
    let chunks = 0;
    const api = mockApi({
      'GET /imports/1': { body: csvImport },
      'GET /searches': { body: searches },
      'GET /images/count': { body: { count: 0 } },
      'POST /searches/run-chunk': () => {
        chunks += 1;

        return {
          body: {
            outcomes: [{ id: 2, make: 'Honda', model: 'Civic', from_year: 1997, outcome: 'completed' }],
            ran_seconds: 1.2,
            remaining: 0,
            blocked: null,
          },
        };
      },
    });
    const { wrapper } = await mountAt('/pipeline/1');

    await waitFor(() => expect(wrapper.text()).toContain('queries.csv'));
    expect(api.calls('GET /searches')[0]?.url.searchParams.get('csv_import_id')).toBe('1');

    const notRun = wrapper.findAll('button[aria-pressed]').find((button) => button.text().includes('not run yet'));
    await notRun?.trigger('click');
    await waitFor(() => expect(api.calls('GET /searches').at(-1)?.url.searchParams.get('coverage')).toBe('not_run'));

    const run = wrapper.findAll('button').find((button) => button.text() === 'Run 1 query');
    await run?.trigger('click');

    await waitFor(() => expect(wrapper.text()).toContain('Run complete'));
    expect(chunks).toBe(1);
    expect(wrapper.get('[role="progressbar"]').attributes('aria-valuenow')).toBe('100');
  });
});

describe('health page', () => {
  it('shows the summary, the bars and an expandable log that filters by context', async () => {
    const api = mockApi({
      'GET /health/summary': { body: health },
      'GET /errors': { body: errors },
      'GET /images/count': { body: { count: 0 } },
    });
    const { wrapper } = await mountAt('/health');

    await waitFor(() => expect(wrapper.text()).toContain('Errors, last 24 hours'));
    await waitFor(() => expect(wrapper.text()).toContain('The search run failed.'));
    expect(wrapper.text()).toContain('RuntimeException: Connection timed out');

    const bar = wrapper.findAll('button[aria-pressed]').find((button) => button.text().includes('Search run'));
    await bar?.trigger('click');

    await waitFor(() => expect(api.calls('GET /errors').at(-1)?.url.searchParams.get('context')).toBe('search_run'));
  });

  it('does not claim an empty log while the log is failing to load', async () => {
    mockApi({
      'GET /health/summary': { body: health },
      'GET /errors': { status: 500, body: { message: 'Server Error' } },
      'GET /images/count': { body: { count: 0 } },
    });
    const { wrapper } = await mountAt('/health');

    await waitFor(() => expect(wrapper.text()).toContain('Server Error'));
    expect(wrapper.text()).not.toContain('Nothing logged');
  });
});

describe('library page', () => {
  it('turns filters into API params and URL state, and exports into a new tab', async () => {
    const tab = { closed: false, opener: {}, location: { href: '' }, close: vi.fn() };
    vi.spyOn(window, 'open').mockReturnValue(tab as unknown as Window);

    const api = mockApi({
      'GET /images': { body: images },
      'GET /images/count': { body: { count: 12 } },
      'GET /imports': { body: imports },
      'POST /exports': {
        body: { url: 'https://api.test/exports/signed', expires_at: '2026-01-15T10:00:00+00:00', count: 12, format: 'csv' },
      },
    });
    const { wrapper, router } = await mountAt('/library?review=pending&make_match=yes');

    await waitFor(() => expect(api.calls('GET /images')).toHaveLength(1));
    const params = api.calls('GET /images')[0]!.url.searchParams;
    expect(params.get('review_status')).toBe('pending');
    expect(params.get('make_confirmed')).toBe('true');
    expect(params.has('year_confirmed')).toBe(false);

    const noYear = wrapper
      .findAll('fieldset')
      .find((fieldset) => fieldset.text().startsWith('Year check'))
      ?.findAll('input')
      .find((input) => (input.element as HTMLInputElement).value === 'no');
    await noYear?.setValue();

    await waitFor(() => expect(router.currentRoute.value.query.year_match).toBe('no'));
    await waitFor(() => expect(api.calls('GET /images').at(-1)?.url.searchParams.get('year_confirmed')).toBe('false'));

    await waitFor(() => expect(wrapper.text()).toContain('12 images match'));
    const csv = wrapper.findAll('button').find((button) => button.text() === 'Export CSV');
    await csv?.trigger('click');

    await waitFor(() => expect(tab.location.href).toBe('https://api.test/exports/signed'));
    expect(api.calls('POST /exports')[0]?.body).toEqual({
      format: 'csv',
      review_status: 'pending',
      make_confirmed: true,
      year_confirmed: false,
    });
    expect(tab.opener).toBeNull();
  });
});
