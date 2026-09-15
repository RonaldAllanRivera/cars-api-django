import { Pressable, Text, View } from 'react-native';

export function StatTile({
  label,
  value,
  onPress,
}: {
  label: string;
  value: number | string;
  onPress?: () => void;
}) {
  const body = (
    <>
      <Text className="text-title text-text">{value}</Text>
      <Text className="text-meta text-text-secondary">{label}</Text>
    </>
  );

  const shell = 'min-w-[88px] flex-1 rounded-surface bg-surface-raised p-3';

  if (!onPress) {
    return <View className={shell}>{body}</View>;
  }

  return (
    <Pressable
      accessibilityRole="button"
      // The number alone would be announced as a bare digit; the pair is what
      // makes a tappable tile mean anything out of context.
      accessibilityLabel={`${label}: ${value}`}
      onPress={onPress}
      className={`${shell} active:opacity-80`}
    >
      {body}
    </Pressable>
  );
}
