/**
 * @jest-environment jsdom
 */
import * as SecureStore from 'expo-secure-store';

import { nativeTokenStore, TOKEN_KEY, webTokenStore } from '../TokenStore';

describe('webTokenStore', () => {
  beforeEach(() => window.localStorage.clear());

  it('round-trips a token', async () => {
    await webTokenStore.set('abc123');

    expect(await webTokenStore.get()).toBe('abc123');
  });

  it('returns null when nothing is stored', async () => {
    expect(await webTokenStore.get()).toBeNull();
  });

  it('clears the token', async () => {
    await webTokenStore.set('abc123');
    await webTokenStore.clear();

    expect(await webTokenStore.get()).toBeNull();
  });

  it('survives storage being unavailable', async () => {
    // Safari in private mode throws on setItem rather than returning.
    const spy = jest.spyOn(window.localStorage.__proto__, 'setItem').mockImplementation(() => {
      throw new Error('QuotaExceededError');
    });

    await expect(webTokenStore.set('abc123')).resolves.toBeUndefined();

    spy.mockRestore();
  });
});

describe('nativeTokenStore', () => {
  beforeEach(() => jest.clearAllMocks());

  it('reads through SecureStore', async () => {
    jest.mocked(SecureStore.getItemAsync).mockResolvedValueOnce('abc123');

    expect(await nativeTokenStore.get()).toBe('abc123');
    expect(SecureStore.getItemAsync).toHaveBeenCalledWith(TOKEN_KEY);
  });

  it('writes through SecureStore', async () => {
    await nativeTokenStore.set('abc123');

    expect(SecureStore.setItemAsync).toHaveBeenCalledWith(TOKEN_KEY, 'abc123');
  });

  it('clears through SecureStore', async () => {
    await nativeTokenStore.clear();

    expect(SecureStore.deleteItemAsync).toHaveBeenCalledWith(TOKEN_KEY);
  });
});
