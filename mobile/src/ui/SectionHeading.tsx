import { Pressable, Text, View } from 'react-native';

/**
 * A section label, in sentence case.
 *
 * Not the tracked-out capitals the health screen used: all-caps eyebrows are
 * absent from Filament and are a generic template signature, so removing them
 * is simultaneously more faithful to the panel and less templated.
 */
export function SectionHeading({
  title,
  action,
}: {
  title: string;
  action?: { label: string; onPress: () => void };
}) {
  return (
    <View className="mb-2 flex-row items-center justify-between">
      <Text className="text-section text-text">{title}</Text>
      {action ? (
        <Pressable
          accessibilityRole="button"
          onPress={action.onPress}
          className="active:opacity-80"
        >
          <Text className="text-meta font-medium text-accent-text">{action.label}</Text>
        </Pressable>
      ) : null}
    </View>
  );
}
