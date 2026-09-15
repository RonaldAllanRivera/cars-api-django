// Ambient types the rest of the toolchain does not supply on a clean
// checkout, before any Expo CLI command has run:
//
// - `jest`: TypeScript 6's automatic `@types/*` inclusion does not pick up
//   `@types/jest` here, so `describe`/`it`/`expect` are otherwise unresolved
//   in test files.
// - `node`: same automatic-inclusion gap, this time for `@types/node`, so
//   `global` (used to stub `global.fetch` in tests) is otherwise unresolved.
// - `*.css`: `expo/types` (referenced by the auto-generated, gitignored
//   `expo-env.d.ts`) declares this module, but that file only exists once
//   the Expo CLI has run at least once (`expo start` / `expo export`). A
//   fresh checkout runs `typecheck` before either of those, so
//   `_layout.tsx`'s side-effect import of `global.css` has nothing to
//   resolve against yet.
/// <reference types="jest" />
/// <reference types="node" />
declare module '*.css';
