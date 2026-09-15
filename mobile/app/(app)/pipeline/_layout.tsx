import { Stack } from 'expo-router';

import { color } from '@/theme/tokens';

/**
 * Without this layout expo-router flattens `pipeline/` into the parent Tabs
 * navigator and every screen below becomes a tab of its own.
 */
export default function PipelineLayout() {
  return (
    <Stack
      screenOptions={{
        headerStyle: { backgroundColor: color.surfaceRaised },
        headerTintColor: color.text,
        contentStyle: { backgroundColor: color.surface },
      }}
    >
      <Stack.Screen name="index" options={{ title: 'Pipeline' }} />
      <Stack.Screen name="[id]" options={{ title: 'Import' }} />
      <Stack.Screen name="upload" options={{ title: 'Upload CSV' }} />
    </Stack>
  );
}
