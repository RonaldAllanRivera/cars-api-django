import { act, renderHook, waitFor } from '@testing-library/react-native';
import type { ReactNode } from 'react';

import * as client from '../../api/client';
import { AuthProvider, REQUESTED_ABILITIES, useAuth } from '../AuthContext';
import { tokenStore } from '../TokenStore';

const wrapper = ({ children }: { children: ReactNode }) => <AuthProvider>{children}</AuthProvider>;

describe('useAuth', () => {
  beforeEach(async () => {
    jest.restoreAllMocks();
    await tokenStore.clear();
  });

  it('starts anonymous when nothing is stored', async () => {
    const { result } = renderHook(() => useAuth(), { wrapper });

    await waitFor(() => expect(result.current.status).toBe('anonymous'));
    expect(result.current.user).toBeNull();
  });

  it('restores a stored token and confirms it against /auth/me', async () => {
    await tokenStore.set('stored-token');
    jest
      .spyOn(client, 'apiRequest')
      .mockResolvedValueOnce({ data: { id: 7, name: 'Ada', email: 'ada@example.test' } });

    const { result } = renderHook(() => useAuth(), { wrapper });

    await waitFor(() => expect(result.current.status).toBe('authenticated'));
    expect(result.current.user?.id).toBe(7);
  });

  it('discards a stored token the API rejects', async () => {
    await tokenStore.set('revoked-token');
    jest
      .spyOn(client, 'apiRequest')
      .mockRejectedValueOnce(new client.ApiError(401, 'Your session has expired.'));

    const { result } = renderHook(() => useAuth(), { wrapper });

    await waitFor(() => expect(result.current.status).toBe('anonymous'));
    expect(await tokenStore.get()).toBeNull();
  });

  it('keeps a stored token when the check fails for any reason but a 401', async () => {
    await tokenStore.set('stored-token');
    jest
      .spyOn(client, 'apiRequest')
      .mockRejectedValueOnce(new TypeError('Network request failed'));

    const { result } = renderHook(() => useAuth(), { wrapper });

    await waitFor(() => expect(result.current.status).toBe('anonymous'));

    // Offline, a 500, or a CORS origin the server does not allow all land in
    // the same catch. Throwing the token away for those signs the user out
    // permanently for a transient failure - which on native defeats the
    // point of storing it in SecureStore at all.
    expect(await tokenStore.get()).toBe('stored-token');
  });

  it('stores the token on a successful sign-in', async () => {
    jest.spyOn(client, 'apiRequest').mockResolvedValueOnce({
      token: 'fresh-token',
      token_type: 'Bearer',
      abilities: ['search:read', 'search:write', 'review:write', 'errors:read'],
      user: { id: 7, name: 'Ada', email: 'ada@example.test' },
    });

    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.status).toBe('anonymous'));

    await act(async () => {
      await result.current.signIn('ada@example.test', 'password', 'test-device');
    });

    expect(result.current.status).toBe('authenticated');
    expect(await tokenStore.get()).toBe('fresh-token');
  });

  it('clears the token on sign-out even if the API call fails', async () => {
    await tokenStore.set('stored-token');
    jest
      .spyOn(client, 'apiRequest')
      .mockResolvedValueOnce({ data: { id: 7, name: 'Ada', email: 'ada@example.test' } })
      .mockRejectedValueOnce(new client.ApiError(500, 'Server error'));

    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.status).toBe('authenticated'));

    await act(async () => {
      await result.current.signOut();
    });

    // A failed revoke must not strand the user in a signed-in shell with a
    // token the server has already forgotten.
    expect(result.current.status).toBe('anonymous');
    expect(await tokenStore.get()).toBeNull();
  });
});

describe('the abilities each build asks for', () => {
  it('asks for imports:read but never imports:write on web', () => {
    // The Pipeline tab has to work on the public demo, so imports:read reaches
    // localStorage. imports:write seeds hundreds of queries and does not.
    expect(REQUESTED_ABILITIES.web).toContain('imports:read');
    expect(REQUESTED_ABILITIES.web).not.toContain('imports:write');
  });

  it('asks for the upload ability on native', () => {
    expect(REQUESTED_ABILITIES.native).toContain('imports:write');
  });

  it('asks for search:run on both builds', () => {
    // Amended from P2, which withheld it from web. search:run advances rows
    // that already exist and cannot create work - inventing a search needs
    // search:write or imports:write - so it does not belong with the latter.
    for (const scope of Object.values(REQUESTED_ABILITIES)) {
      expect(scope).toContain('search:run');
    }
  });

  it('asks for exports:read on native only', () => {
    // P4 gives exports:read its screen. Exports happen on the phone, after the
    // CSV was uploaded in the panel, so the web build never needs it and it
    // stays off localStorage tokens.
    //
    // Asserted here because no backend test can catch its absence:
    // actingAsApiUser() grants every ability, so the whole backend suite
    // passes while the export panel is dead on the one build meant to have it.
    expect(REQUESTED_ABILITIES.native).toContain('exports:read');
    expect(REQUESTED_ABILITIES.web).not.toContain('exports:read');
  });

  it('keeps the four the server issues by default', () => {
    // Narrowing below defaultScope() would silently break screens that work
    // today - the server intersects, it does not widen.
    for (const scope of Object.values(REQUESTED_ABILITIES)) {
      for (const ability of ['search:read', 'search:write', 'review:write', 'errors:read']) {
        expect(scope).toContain(ability);
      }
    }
  });
});
