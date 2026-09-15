import { Stack } from 'expo-router';

import { color } from '@/theme/tokens';

/**
 * Without this layout expo-router flattens `library/` into the parent Tabs
 * navigator and `[id]` becomes a tab of its own. A nested Stack collapses the
 * directory into the single `library` tab the Tabs layout declares, and gives
 * the detail screen a back button.
 */
export default function LibraryLayout() {
  return (
    <Stack
      screenOptions={{
        headerStyle: { backgroundColor: color.surfaceRaised },
        headerTintColor: color.text,
        contentStyle: { backgroundColor: color.surface },
      }}
    >
      <Stack.Screen name="index" options={{ title: 'Library' }} />
      <Stack.Screen name="[id]" options={{ title: 'Image' }} />
    </Stack>
  );
}
