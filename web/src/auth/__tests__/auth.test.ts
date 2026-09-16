import { describe, expect, it } from 'vitest';

import { apiRequest } from '@/api/client';
import { mockApi } from '@/test/http';

import login from '../../api/__fixtures__/login.json';
import me from '../../api/__fixtures__/me.json';
import { can, onSignedOut, REQUESTED_ABILITIES, restoreSession, signIn, signOut, useAuth } from '../auth';
import { ABILITIES_KEY, TOKEN_KEY } from '../tokenStore';

describe('auth', () => {
  it('asks for all nine abilities and stores the token under cars-images.token', async () => {
    const api = mockApi({ 'POST /auth/login': { body: login } });

    await signIn('fixtures@example.test', 'secret');

    expect(api.requests[0]?.body).toEqual({
      email: 'fixtures@example.test',
      password: 'secret',
      device_name: 'web',
      abilities: [
        'search:read',
        'search:write',
        'review:write',
        'errors:read',
        'imports:read',
        'imports:write',
        'search:run',
        'exports:read',
        // The server grants it to staff accounts only.
        'blog:write',
      ],
    });
    expect(REQUESTED_ABILITIES).toHaveLength(9);
    expect(window.localStorage.getItem(TOKEN_KEY)).toBe(login.token);
    expect(useAuth().state.status).toBe('authenticated');
  });

  it('checks abilities against what the server granted, not what was asked for', async () => {
    mockApi({ 'POST /auth/login': { body: login } });

    await signIn('fixtures@example.test', 'secret');

    expect(can('search:read')).toBe(true);
    expect(can('exports:read')).toBe(false);
    expect(JSON.parse(window.localStorage.getItem(ABILITIES_KEY) ?? '[]')).toEqual(login.abilities);
  });

  it('restores a stored session with /auth/me and sends the token', async () => {
    window.localStorage.setItem(TOKEN_KEY, 'stored-token');
    const api = mockApi({ 'GET /auth/me': { body: me } });

    await restoreSession();

    expect(api.requests[0]?.headers.Authorization).toBe('Bearer stored-token');
    expect(useAuth().state.user?.name).toBe('Fixture User');
    expect(useAuth().state.status).toBe('authenticated');
  });

  it('boots anonymous without calling the API when nothing is stored', async () => {
    const api = mockApi({});

    await restoreSession();

    expect(api.requests).toHaveLength(0);
    expect(useAuth().state.status).toBe('anonymous');
  });

  it('forgets a token the server rejects', async () => {
    window.localStorage.setItem(TOKEN_KEY, 'dead-token');
    mockApi({ 'GET /auth/me': { status: 401, body: { message: 'Unauthenticated.' } } });

    await restoreSession();

    expect(window.localStorage.getItem(TOKEN_KEY)).toBeNull();
    expect(useAuth().state.status).toBe('anonymous');
  });

  it('keeps a token through an outage, so a flaky boot is not a permanent sign-out', async () => {
    window.localStorage.setItem(TOKEN_KEY, 'good-token');
    mockApi({ 'GET /auth/me': { status: 500, body: { message: 'Server Error' } } });

    await restoreSession();

    expect(window.localStorage.getItem(TOKEN_KEY)).toBe('good-token');
    expect(useAuth().state.status).toBe('anonymous');
    expect(useAuth().state.bootError).toBe('Server Error');
  });

  it('signs out on any 401 and tells listeners', async () => {
    mockApi({ 'POST /auth/login': { body: login }, 'GET /images': { status: 401, body: {} } });
    await signIn('fixtures@example.test', 'secret');
    let told = 0;
    onSignedOut(() => (told += 1));

    await apiRequest('/images').catch(() => undefined);

    expect(useAuth().state.status).toBe('anonymous');
    expect(window.localStorage.getItem(TOKEN_KEY)).toBeNull();
    expect(told).toBe(1);
  });

  it('revokes the token on sign out, and still signs out if that fails', async () => {
    const api = mockApi({ 'POST /auth/login': { body: login }, 'POST /auth/logout': { status: 500, body: {} } });
    await signIn('fixtures@example.test', 'secret');

    await signOut();

    expect(api.calls('POST /auth/logout')).toHaveLength(1);
    expect(api.calls('POST /auth/logout')[0]?.headers.Authorization).toBe(`Bearer ${login.token}`);
    expect(useAuth().state.status).toBe('anonymous');
  });
});
