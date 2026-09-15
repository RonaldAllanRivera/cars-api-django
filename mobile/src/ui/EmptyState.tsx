import type { ReactNode } from 'react';
import { Text, View } from 'react-native';

import { Button } from './Button';

/**
 * An empty screen is an invitation to act, not a dead end.
 *
 * Filament gives its empty states a heading, a description, an icon and an
 * action; this is the same four, with the action optional because some empty
 * states really are terminal ("every image has a verdict").
 */
export function EmptyState({
  title,
  hint,
  icon,
  action,
}: {
  title: string;
  hint?: string;
  icon?: ReactNode;
  action?: { label: string; onPress: () => void };
}) {
  return (
    <View className="items-center gap-2 p-8">
      {icon}
      <Text className="text-section text-text">{title}</Text>
      {hint ? <Text className="text-center text-meta text-text-secondary">{hint}</Text> : null}
      {action ? (
        <View className="mt-2">
          <Button label={action.label} onPress={action.onPress} variant="secondary" />
        </View>
      ) : null}
    </View>
  );
}
