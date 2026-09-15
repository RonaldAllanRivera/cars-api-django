import { Text, TextInput, View } from 'react-native';
import type { TextInputProps } from 'react-native';

import { color } from '@/theme/tokens';

interface Props extends Omit<TextInputProps, 'className' | 'placeholderTextColor'> {
  label: string;
  value: string;
  onChangeText: (text: string) => void;
  hint?: string;
  error?: string;
}

/**
 * A labelled text input.
 *
 * Filament labels every field above its control; the app used the placeholder
 * as the label, which disappears on the first keystroke and takes the only
 * description of the box with it.
 */
export function Field({ label, value, onChangeText, hint, error, ...rest }: Props) {
  return (
    <View className="gap-1">
      <Text className="text-meta font-medium text-text-secondary">{label}</Text>
      <TextInput
        // The label is a sibling <Text>, not a <label for>, so the accessible
        // name has to be set explicitly or the control is announced unnamed.
        accessibilityLabel={label}
        value={value}
        onChangeText={onChangeText}
        placeholderTextColor={color.textMuted}
        className={`rounded-control bg-surface-sunken px-4 py-3 text-body text-text ${
          error ? 'border border-danger/50' : ''
        }`}
        {...rest}
      />
      {/* One line of small print, not two: the error is the one that needs
          reading, so it replaces the hint rather than stacking under it. */}
      {error ? (
        <Text className="text-meta text-danger-text">{error}</Text>
      ) : hint ? (
        <Text className="text-meta text-text-muted">{hint}</Text>
      ) : null}
    </View>
  );
}
