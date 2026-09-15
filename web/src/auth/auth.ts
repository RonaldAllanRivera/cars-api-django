import { computed, reactive, readonly } from 'vue';

import { ApiError, apiRequest, configureApiClient } from '@/api/client';
import { queryClient } from '@/api/queryClient';
import { LoginResponseSchema, single, UserSchema } from '@/api/schemas';
import type { TokenAbility, User } from '@/api/schemas';

import { tokenStore } from './tokenStore';

export type AuthStatus = 'loading' | 'authenticated' | 'anonymous';

/**
 * Everything this client asks for at login. The server intersects the request
 * with what the account may hold, so this can never grant more than that - and
 * the granted list is what `can()` reads.
 */
export const REQUESTED_ABILITIES: readonly TokenAbility[] = [
  'search:read',
  'search:write',
  'review:write',
  'errors:read',
  'imports:read',
  'imports:write',
  'search:run',
  'exports:read',
];

/** Names the token so the server can list and revoke it per device. */
export const DEVICE_NAME = 'web';

const state = reactive({
  status: 'loading' as AuthStatus,
  user: null as User | null,
  abilities: [] as TokenAbility[],
  /** Set when a stored session could not be checked (offline, API down). */
  bootError: null as string | null,
});

// Plain module state, not reactive: the client reads it synchronously on every
// request and nothing renders from it.
let token: string | null = null;
let restoring: Promise<void> | null = null;
const signedOutListeners = new Set<() => void>();

function clearLocal(): void {
  const wasSignedIn = token !== null || state.status === 'authenticated';

  token = null;
  tokenStore.clear();
  state.user = null;
  state.abilities = [];
  state.status = 'anonymous';
  // Another user signing in on this tab must not see this one's cached pages.
  queryClient.clear();

  if (wasSignedIn) signedOutListeners.forEach((listener) => listener());
}

configureApiClient({
  getToken: () => token,
  // The token is already dead, so there is nothing to revoke remotely - and
  // calling logout with it would 401 straight back into this handler.
  onUnauthorized: () => clearLocal(),
});

/** Restores a stored session once; every later call shares the same promise. */
export function restoreSession(): Promise<void> {
  restoring ??= (async () => {
    const stored = tokenStore.get();

    if (!stored) {
      state.status = 'anonymous';

      return;
    }

    token = stored;

    try {
      const me = await apiRequest('/auth/me', { schema: single(UserSchema) });

      state.user = me.data;
      state.abilities = tokenStore.abilities() ?? [...REQUESTED_ABILITIES];
      state.status = 'authenticated';
    } catch (caught) {
      // Only a 401 means the token is dead, and the client has already cleared
      // it. Offline, a 500 or a CORS refusal leaves it in storage, so a flaky
      // boot is not a permanent sign-out: the next reload tries it again.
      if (!(caught instanceof ApiError && caught.status === 401)) {
        token = null;
        state.bootError =
          caught instanceof ApiError
            ? caught.message
            : 'The API could not be reached. Check your connection and reload.';
      }

      state.status = 'anonymous';
    }
  })();

  return restoring;
}

export async function signIn(email: string, password: string): Promise<void> {
  const result = await apiRequest('/auth/login', {
    method: 'POST',
    body: { email, password, device_name: DEVICE_NAME, abilities: [...REQUESTED_ABILITIES] },
    schema: LoginResponseSchema,
  });

  token = result.token;
  state.bootError = null;
  tokenStore.set(result.token, result.abilities);
  state.user = result.user;
  state.abilities = result.abilities;
  state.status = 'authenticated';
  restoring = Promise.resolve();
}

export async function signOut(): Promise<void> {
  if (token) {
    // Best effort: if the revoke fails the local token still goes.
    await apiRequest('/auth/logout', { method: 'POST' }).catch(() => undefined);
  }

  clearLocal();
}

export function onSignedOut(listener: () => void): () => void {
  signedOutListeners.add(listener);

  return () => signedOutListeners.delete(listener);
}

export function can(ability: TokenAbility): boolean {
  return state.abilities.includes(ability);
}

export function useAuth() {
  return {
    state: readonly(state),
    user: computed(() => state.user),
    isAuthenticated: computed(() => state.status === 'authenticated'),
    can,
    signIn,
    signOut,
  };
}

/** Test seam: puts the store back to a cold boot. */
export function resetAuthForTests(): void {
  token = null;
  restoring = null;
  state.status = 'loading';
  state.user = null;
  state.abilities = [];
  state.bootError = null;
  signedOutListeners.clear();
}

/** Test seam: a signed-in session without a network round trip. */
export function setSessionForTests(user: User, abilities: TokenAbility[] = [...REQUESTED_ABILITIES]): void {
  token = 'test-token';
  state.user = user;
  state.abilities = abilities;
  state.status = 'authenticated';
  restoring = Promise.resolve();
}
