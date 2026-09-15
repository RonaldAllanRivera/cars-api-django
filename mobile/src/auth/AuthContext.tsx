import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { Platform } from 'react-native';

import { ApiError, apiRequest, configureApiClient } from '../api/client';
import { LoginResponseSchema, single, UserSchema } from '../api/schemas';
import type { User } from '../api/schemas';
import { tokenStore } from './TokenStore';

type Status = 'loading' | 'authenticated' | 'anonymous';

interface AuthValue {
  status: Status;
  user: User | null;
  signIn: (email: string, password: string, deviceName: string) => Promise<void>;
  signOut: () => Promise<void>;
}

/**
 * What each build asks for at login.
 *
 * The server's TokenAbilities::defaultScope() is frozen as a compatibility
 * floor for clients that predate scoping; every current client declares what
 * it needs, so the ability set can grow without the login response changing
 * for anyone - and without the committed login fixture churning.
 *
 * imports:read reaches the web build because a Pipeline tab that 403s on the
 * public demo is worse than no tab at all. imports:write does not: it is the
 * verb that seeds hundreds of queries, and the web build keeps its token in
 * localStorage where any XSS on the origin can read it.
 *
 * search:run also reaches web, amending P2. It advances rows that already
 * exist and cannot create work - inventing a search needs search:write or
 * imports:write - so its ceiling is "searches you already queued, run at a
 * time you did not choose" rather than an unbounded crawl.
 *
 * The server intersects rather than widens, so nothing here can grant more
 * than the account already has.
 */
export const REQUESTED_ABILITIES = {
  web: [
    'search:read',
    'search:write',
    'review:write',
    'errors:read',
    'imports:read',
    'search:run',
  ],
  native: [
    'search:read',
    'search:write',
    'review:write',
    'errors:read',
    'imports:read',
    'search:run',
    'imports:write',
    // Exports happen on the phone, after the CSV was uploaded in the panel. The
    // web build never exports, so this stays off localStorage tokens.
    'exports:read',
  ],
} as const;

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Status>('loading');
  const [user, setUser] = useState<User | null>(null);

  // A ref, not state: the client reads the token synchronously on every
  // request, and a stale closure would send the previous token.
  const tokenRef = useRef<string | null>(null);

  const signOut = useCallback(async () => {
    if (tokenRef.current) {
      // Best effort. If the revoke fails the local token still goes - the
      // alternative is a signed-in shell holding a token the server may
      // already have forgotten.
      await apiRequest('/auth/logout', { method: 'POST' }).catch(() => undefined);
    }

    tokenRef.current = null;
    await tokenStore.clear();
    setUser(null);
    setStatus('anonymous');
  }, []);

  // Configured once, before the restore below can fire a request.
  useEffect(() => {
    configureApiClient({
      getToken: () => tokenRef.current,
      onUnauthorized: () => {
        void signOut();
      },
    });
  }, [signOut]);

  useEffect(() => {
    let cancelled = false;

    const restore = async () => {
      const stored = await tokenStore.get();

      if (!stored) {
        if (!cancelled) setStatus('anonymous');

        return;
      }

      tokenRef.current = stored;

      try {
        const me = await apiRequest('/auth/me', { schema: single(UserSchema) });

        if (cancelled) return;

        setUser(me.data);
        setStatus('authenticated');
      } catch (caught) {
        if (cancelled) return;

        // Only a 401 means the token is dead. Offline, a 500, or a CORS
        // origin the server does not allow all land here too, and throwing
        // the token away for those signs the user out permanently for a
        // transient failure - which on native defeats the point of storing
        // it in SecureStore at all. Keep it and stay anonymous for now.
        if (caught instanceof ApiError && caught.status === 401) {
          tokenRef.current = null;
          await tokenStore.clear();
        }

        setStatus('anonymous');
      }
    };

    void restore();

    return () => {
      cancelled = true;
    };
  }, []);

  const signIn = useCallback(async (email: string, password: string, deviceName: string) => {
    const result = await apiRequest('/auth/login', {
      method: 'POST',
      body: {
        email,
        password,
        device_name: deviceName,
        abilities: [...(Platform.OS === 'web' ? REQUESTED_ABILITIES.web : REQUESTED_ABILITIES.native)],
      },
      schema: LoginResponseSchema,
    });

    tokenRef.current = result.token;
    await tokenStore.set(result.token);
    setUser(result.user);
    setStatus('authenticated');
  }, []);

  const value = useMemo<AuthValue>(
    () => ({ status, user, signIn, signOut }),
    [status, user, signIn, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext);

  if (!value) {
    throw new Error('useAuth must be used inside an AuthProvider.');
  }

  return value;
}
