module.exports = {
  extends: 'expo',
  ignorePatterns: ['dist/', 'node_modules/', '.expo/'],
  overrides: [
    {
      // The "expo" config declares only RN/browser globals, not jest's -
      // without this, jest.setup.js's `jest.mock(...)` and every
      // describe/it/expect in a test file trip no-undef.
      files: ['jest.setup.js', '**/__tests__/**/*', '*.test.*'],
      env: { jest: true },
    },
  ],
};
