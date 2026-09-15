import { Platform } from 'react-native';

import type { TokenAbility } from '@/api/schemas';
import { REQUESTED_ABILITIES } from './AuthContext';

/**
 * Pure, so refusal can be tested: this jest-expo config pins Platform.OS to
 * ios, which means useCan by itself could only ever be observed granting.
 */
export function canWith(scope: readonly string[], ability: TokenAbility): boolean {
  return scope.includes(ability);
}

/**
 * Whether this build's token carries an ability.
 *
 * A capability check, not a platform check. `Platform.OS === 'web'` would work
 * today and encode the wrong rule - "this is a browser" rather than "this token
 * cannot export" - and would rot silently the moment the ability split changes.
 *
 * Reads what the build requested, which equals what was granted while every
 * requested ability is valid: the server intersects the request with
 * TokenAbilities::all(). The rigorous version would persist the login
 * response's `abilities` and read that; it is deferred until requested and
 * granted can actually differ.
 */
export function useCan(ability: TokenAbility): boolean {
  return canWith(
    Platform.OS === 'web' ? REQUESTED_ABILITIES.web : REQUESTED_ABILITIES.native,
    ability,
  );
}
