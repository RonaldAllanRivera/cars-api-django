// The web TokenStore path reads localStorage; jsdom provides it, but the
// native path's SecureStore must be mocked or every suite touching auth
// tries to reach a native module that does not exist under Jest.
//
// This jest-expo config resolves Platform.OS to 'ios' for every test file
// (there is no multi-project split - see the jest.config.js comment on the
// @/ alias), so the platform-selected `tokenStore` always resolves to
// `nativeTokenStore` here, even under a `@jest-environment jsdom` file. The
// fake below is a real in-memory store, not a call-recording stub: auth
// flows that round-trip a token through `tokenStore.set()` then
// `tokenStore.get()` (AuthContext's restore-on-mount and sign-in/out) need
// the second call to see what the first one wrote.
jest.mock('expo-secure-store', () => {
  const store = new Map();

  return {
    getItemAsync: jest.fn(async (key) => store.get(key) ?? null),
    setItemAsync: jest.fn(async (key, value) => {
      store.set(key, value);
    }),
    deleteItemAsync: jest.fn(async (key) => {
      store.delete(key);
    }),
  };
});
