module.exports = {
  preset: 'jest-expo',
  setupFilesAfterEnv: ['<rootDir>/jest.setup.js'],
  // Metro honours the tsconfig `paths` entry on its own; Jest does not, so
  // the @/ alias has to be repeated here or every test importing it fails to
  // resolve.
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/src/$1',
  },
  transformIgnorePatterns: [
    // The brief's base allowlist plus `standard-navigation`: expo-router 57
    // depends on it directly, and it ships ESM that jest-expo's own
    // allowlist (written before that dependency existed) does not cover.
    'node_modules/(?!((jest-)?react-native|@react-native(-community)?|expo(nent)?|@expo(nent)?/.*|@expo-google-fonts/.*|react-navigation|@react-navigation/.*|@unimodules/.*|unimodules|sentry-expo|native-base|react-native-svg|nativewind|react-native-css-interop|standard-navigation))',
  ],
};
