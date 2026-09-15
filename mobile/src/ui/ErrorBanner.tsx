import { Text, View } from 'react-native';

export function ErrorBanner({ message }: { message: string }) {
  return (
    // rounded-surface, not rounded-control: this is a surface carrying content,
    // and giving it a control's corner made it read as a disabled button.
    <View
      accessibilityRole="alert"
      className="mb-3 rounded-surface border border-danger/40 bg-danger/10 p-3"
    >
      <Text className="text-body text-danger-text">{message}</Text>
    </View>
  );
}
