import { beforeEach, describe, expect, it } from 'vitest';

import { setSessionForTests } from '@/auth/auth';
import { mockApi } from '@/test/http';
import { mountAt, waitFor } from '@/test/mount';

import me from '../../api/__fixtures__/me.json';
import searchCreate from '../../api/__fixtures__/search-create.json';
import searches from '../../api/__fixtures__/searches.json';
import validationError from '../../api/__fixtures__/validation-error.json';

const baseRoutes = {
  'GET /searches': { body: searches },
  'GET /images/count': { body: { count: 0 } },
};

function field(wrapper: Awaited<ReturnType<typeof mountAt>>['wrapper'], label: string) {
  const labelEl = wrapper.findAll('label').find((candidate) => candidate.text().startsWith(label));
  if (!labelEl) throw new Error(`No field labelled ${label}`);

  return wrapper.get(`#${CSS.escape(labelEl.attributes('for') ?? '')}`);
}

describe('search page', () => {
  beforeEach(() => setSessionForTests(me.data));

  it('lists recent ad-hoc runs and filters them by status', async () => {
    const api = mockApi(baseRoutes);
    const { wrapper } = await mountAt('/search');

    await waitFor(() => expect(wrapper.text()).toContain('Toyota RAV4'));
    expect(api.calls('GET /searches')[0]?.url.searchParams.get('source')).toBe('adhoc');

    const failed = wrapper.findAll('input[type="radio"]').find((input) => (input.element as HTMLInputElement).value === 'failed');
    await failed?.setValue();

    await waitFor(() => expect(api.calls('GET /searches').at(-1)?.url.searchParams.get('status')).toBe('failed'));
  });

  it('requires a make and a year before sending', async () => {
    const api = mockApi(baseRoutes);
    const { wrapper } = await mountAt('/search');

    await wrapper.get('form').trigger('submit');

    expect(wrapper.text()).toContain('Enter a make, for example Toyota.');
    expect(wrapper.text()).toMatch(/Enter a year between 1886 and \d{4}\./);
    expect(api.calls('POST /searches')).toHaveLength(0);
  });

  it('refuses a year span over the cap without a round trip', async () => {
    const api = mockApi(baseRoutes);
    const { wrapper } = await mountAt('/search');

    await field(wrapper, 'Make').setValue('Toyota');
    await field(wrapper, 'From year').setValue('1990');
    await field(wrapper, 'To year').setValue('1995');
    await wrapper.get('form').trigger('submit');

    expect(wrapper.text()).toContain('A search covers at most 4 years (1990–1993)');
    expect(field(wrapper, 'To year').attributes('aria-invalid')).toBe('true');
    expect(api.calls('POST /searches')).toHaveLength(0);
  });

  it('shows a 422 under the field it names', async () => {
    mockApi({ ...baseRoutes, 'POST /searches': { status: 422, body: validationError } });
    const { wrapper } = await mountAt('/search');

    await field(wrapper, 'Make').setValue('Toyota');
    await field(wrapper, 'From year').setValue('1997');
    await wrapper.get('form').trigger('submit');

    await waitFor(() => expect(wrapper.text()).toContain(validationError.errors.to_year[0]));
  });

  it('stays on the form with a link to the run when Wikimedia blocks it', async () => {
    const api = mockApi({
      ...baseRoutes,
      'POST /searches': {
        status: 503,
        body: { ...searchCreate, message: 'Wikimedia is rate-limiting this server.', retry_after_seconds: 90 },
      },
    });
    const { wrapper, router } = await mountAt('/search');

    await field(wrapper, 'Make').setValue(' Honda ');
    await field(wrapper, 'Model').setValue('CR-V');
    await field(wrapper, 'From year').setValue('1997');
    await wrapper.get('form').trigger('submit');

    await waitFor(() => expect(wrapper.text()).toContain('Wikimedia is rate-limiting this server. Try again in 1m 30s.'));
    expect(router.currentRoute.value.name).toBe('search');
    expect(wrapper.get('a[href="/search/runs/3"]').text()).toBe('View the run');
    expect(api.calls('POST /searches')[0]?.body).toEqual({
      make: 'Honda',
      model: 'CR-V',
      from_year: 1997,
      to_year: 1997,
      images_per_year: 5,
    });
  });

  it('opens the run once a search completes', async () => {
    mockApi({
      ...baseRoutes,
      'POST /searches': { status: 201, body: searchCreate },
      'GET /searches/3': { body: { data: searchCreate.data } },
      'GET /searches/3/images': { body: { ...searches, data: searchCreate.data.images } },
    });
    const { wrapper, router } = await mountAt('/search');

    await field(wrapper, 'Make').setValue('Honda');
    await field(wrapper, 'From year').setValue('1997');
    await wrapper.get('form').trigger('submit');

    await waitFor(() => expect(router.currentRoute.value.fullPath).toBe('/search/runs/3'));
    await waitFor(() => expect(wrapper.text()).toContain('Search complete: 1 image found.'));
    await waitFor(() => expect(wrapper.find('img[alt="Honda CR-V 1997"]').exists()).toBe(true));
  });
});
