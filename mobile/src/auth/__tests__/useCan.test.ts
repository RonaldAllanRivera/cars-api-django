import { REQUESTED_ABILITIES } from '../AuthContext';
import { canWith } from '../useCan';

describe('canWith', () => {
  it('grants an ability the scope requests', () => {
    expect(canWith(REQUESTED_ABILITIES.native, 'exports:read')).toBe(true);
    expect(canWith(REQUESTED_ABILITIES.native, 'imports:write')).toBe(true);
  });

  it('refuses an ability the scope does not request', () => {
    // Tested through the pure function with the web scope, because this
    // jest-expo config pins Platform.OS to ios - so useCan by itself could only
    // ever be observed granting, never refusing.
    expect(canWith(REQUESTED_ABILITIES.web, 'exports:read')).toBe(false);
    expect(canWith(REQUESTED_ABILITIES.web, 'imports:write')).toBe(false);
  });

  it('still grants the web build what it does request', () => {
    expect(canWith(REQUESTED_ABILITIES.web, 'search:run')).toBe(true);
    expect(canWith(REQUESTED_ABILITIES.web, 'imports:read')).toBe(true);
  });
});
