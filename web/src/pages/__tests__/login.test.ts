import { describe, expect, it } from 'vitest';

import { mockApi } from '@/test/http';
import { mountAt, waitFor } from '@/test/mount';

import login from '../../api/__fixtures__/login.json';
import searches from '../../api/__fixtures__/searches.json';
import validationError from '../../api/__fixtures__/validation-error.json';

const empty = { ...searches, data: [] };

async function fillAndSubmit(wrapper: Awaited<ReturnType<typeof mountAt>>['wrapper']) {
  await wrapper.get('input[type="email"]').setValue('fixtures@example.test');
  await wrapper.get('input[type="password"]').setValue('wrong');
  await wrapper.get('form').trigger('submit');
}

describe('login page', () => {
  it('sends a signed-out visitor to login, remembering where they were going', async () => {
    mockApi({});

    const { router } = await mountAt('/library?review=pending');

    expect(router.currentRoute.value.name).toBe('login');
    expect(router.currentRoute.value.query.redirect).toBe('/library?review=pending');
  });

  it("shows the server's credential error above the form", async () => {
    mockApi({
      'POST /auth/login': {
        status: 422,
        body: { ...validationError, message: 'These credentials do not match our records.', errors: { email: ['These credentials do not match our records.'] } },
      },
    });
    const { wrapper } = await mountAt('/login');

    await fillAndSubmit(wrapper);

    await waitFor(() => expect(wrapper.get('[role="alert"]').text()).toBe('These credentials do not match our records.'));
  });

  it('explains a throttled login', async () => {
    mockApi({ 'POST /auth/login': { status: 429, body: { message: 'Too Many Attempts.' } } });
    const { wrapper } = await mountAt('/login');

    await fillAndSubmit(wrapper);

    await waitFor(() => expect(wrapper.get('[role="alert"]').text()).toContain('Too many requests'));
  });

  it('asks for both fields before sending anything', async () => {
    const api = mockApi({});
    const { wrapper } = await mountAt('/login');

    await wrapper.get('form').trigger('submit');

    expect(wrapper.text()).toContain('Enter your email address.');
    expect(wrapper.text()).toContain('Enter your password.');
    expect(api.requests).toHaveLength(0);
  });

  it('signs in and continues to the page that was asked for', async () => {
    mockApi({
      'POST /auth/login': { body: { ...login, abilities: ['search:read', 'search:write'] } },
      'GET /searches': { body: empty },
    });
    const { wrapper, router } = await mountAt('/search?x=1');

    expect(router.currentRoute.value.name).toBe('login');
    await fillAndSubmit(wrapper);

    await waitFor(() => expect(router.currentRoute.value.fullPath).toBe('/search?x=1'));
    await waitFor(() => expect(wrapper.text()).toContain('New search'));
  });

  it('ignores an off-site redirect', async () => {
    mockApi({ 'POST /auth/login': { body: login }, 'GET /searches': { body: empty } });
    const { wrapper, router } = await mountAt('/login?redirect=//evil.example');

    await fillAndSubmit(wrapper);

    await waitFor(() => expect(router.currentRoute.value.fullPath).toBe('/search'));
  });
});
