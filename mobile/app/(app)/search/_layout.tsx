import { Stack } from 'expo-router';

import { color } from '@/theme/tokens';

/**
 * Without this layout expo-router flattens `search/` into the parent Tabs
 * navigator, so every screen below becomes a tab of its own. A nested Stack
 * collapses the directory into the single `search` tab the Tabs layout
 * declares, and gives the detail screens a back button.
 *
 * The Stack owns the header here and the Tabs layout hides its own for this
 * tab: only the inner navigator knows which screen is showing, so only it can
 * title the screen and offer the back affordance.
 *
 * `runs/` lives under this tab rather than being one of its own. A run is what
 * the form on `index` produces, so it belongs in the same stack - and the
 * panel makes the same split, between CarSearchResource (ad hoc, here) and
 * SearchQueryResource (CSV-derived, which P3 gives its own tab).
 */
export default function SearchLayout() {
  return (
    <Stack
      screenOptions={{
        headerStyle: { backgroundColor: color.surfaceRaised },
        headerTintColor: color.text,
        contentStyle: { backgroundColor: color.surface },
      }}
    >
      <Stack.Screen name="index" options={{ title: 'Search' }} />
      <Stack.Screen name="runs/index" options={{ title: 'Runs' }} />
      <Stack.Screen name="runs/[id]" options={{ title: 'Run' }} />
      <Stack.Screen name="[id]" options={{ title: 'Image' }} />
    </Stack>
  );
}
