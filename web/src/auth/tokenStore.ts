import { TokenAbilitySchema } from '@/api/schemas';
import type { TokenAbility } from '@/api/schemas';

export const TOKEN_KEY = 'cars-images.token';
export const ABILITIES_KEY = 'cars-images.abilities';

/**
 * localStorage, guarded on every call: a private-mode browser can throw on
 * access rather than return empty. A missing token means "signed out", which
 * is recoverable; an exception at boot is not.
 */
export const tokenStore = {
  get(): string | null {
    try {
      return window.localStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },

  set(token: string, abilities: readonly TokenAbility[]): void {
    try {
      window.localStorage.setItem(TOKEN_KEY, token);
      window.localStorage.setItem(ABILITIES_KEY, JSON.stringify(abilities));
    } catch {
      // Storage unavailable: the session still works for this page load.
    }
  },

  /** What the server granted at login - it intersects, so this can be fewer than requested. */
  abilities(): TokenAbility[] | null {
    try {
      const raw = window.localStorage.getItem(ABILITIES_KEY);
      if (!raw) return null;

      const parsed = TokenAbilitySchema.array().safeParse(JSON.parse(raw));

      return parsed.success ? parsed.data : null;
    } catch {
      return null;
    }
  },

  clear(): void {
    try {
      window.localStorage.removeItem(TOKEN_KEY);
      window.localStorage.removeItem(ABILITIES_KEY);
    } catch {
      // Nothing to do - the in-memory token is cleared by the auth store.
    }
  },
};
