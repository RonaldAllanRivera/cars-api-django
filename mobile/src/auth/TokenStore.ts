import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

export const TOKEN_KEY = 'cars-images.token';

export interface TokenStore {
  get(): Promise<string | null>;
  set(token: string): Promise<void>;
  clear(): Promise<void>;
}

/**
 * The web build has no SecureStore equivalent, so the token lives in
 * localStorage. Scoped token abilities are the mitigation for that: a
 * stolen web token can do only what the API let it do.
 *
 * Every call is guarded because a browser in private mode can throw on
 * access rather than returning empty. A missing token means "signed out",
 * which is a recoverable state; a thrown error at module load is not.
 */
export const webTokenStore: TokenStore = {
  async get() {
    try {
      return window.localStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },
  async set(token) {
    try {
      window.localStorage.setItem(TOKEN_KEY, token);
    } catch {
      // Storage unavailable: the session still works for this page load.
    }
  },
  async clear() {
    try {
      window.localStorage.removeItem(TOKEN_KEY);
    } catch {
      // Nothing to do - the in-memory token is cleared by AuthContext.
    }
  },
};

export const nativeTokenStore: TokenStore = {
  get: () => SecureStore.getItemAsync(TOKEN_KEY),
  set: (token) => SecureStore.setItemAsync(TOKEN_KEY, token),
  clear: () => SecureStore.deleteItemAsync(TOKEN_KEY),
};

export const tokenStore: TokenStore = Platform.OS === 'web' ? webTokenStore : nativeTokenStore;
