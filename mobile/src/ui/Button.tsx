import { ActivityIndicator, Pressable, Text } from 'react-native';

import { color } from '@/theme/tokens';

export type ButtonVariant = 'primary' | 'secondary' | 'danger-subtle' | 'ghost';

interface Props {
  label: string;
  onPress: () => void;
  variant?: ButtonVariant;
  size?: 'md' | 'lg';
  pending?: boolean;
  disabled?: boolean;
  /** flexGrow, so a row can weight Approve against Reject. */
  flex?: number;
}

/*
 * `danger-subtle` rather than a filled red: Filament tints destructive actions
 * and fills primary ones, so a filled Reject would carry the same weight as
 * Approve. The asymmetry is the design, not an oversight.
 */
const SHELL: Record<ButtonVariant, string> = {
  primary: 'bg-accent',
  secondary: 'bg-surface-sunken border border-border-strong',
  'danger-subtle': 'bg-danger/10 border border-danger/30',
  ghost: 'bg-transparent',
};

const LABEL: Record<ButtonVariant, string> = {
  primary: 'text-accent-fg',
  secondary: 'text-text',
  'danger-subtle': 'text-danger-text',
  ghost: 'text-accent-text',
};

/** The spinner has to contrast with the shell it sits on, not with the page. */
const SPINNER: Record<ButtonVariant, string> = {
  primary: color.accentFg,
  secondary: color.text,
  'danger-subtle': color.dangerText,
  ghost: color.accentText,
};

export function Button({
  label,
  onPress,
  variant = 'primary',
  size = 'md',
  pending = false,
  disabled = false,
  flex,
}: Props) {
  const inert = pending || disabled;

  return (
    <Pressable
      accessibilityRole="button"
      // Named explicitly because the visible label is replaced by a spinner
      // while pending, leaving nothing else for assistive tech to read.
      accessibilityLabel={label}
      accessibilityState={{ disabled: inert, busy: pending }}
      disabled={inert}
      onPress={onPress}
      style={flex === undefined ? undefined : { flexGrow: flex, flexBasis: 0 }}
      className={`items-center justify-center rounded-control ${SHELL[variant]} ${
        size === 'lg' ? 'px-6 py-4' : 'px-4 py-3'
      } ${inert ? 'opacity-60' : 'active:opacity-80'}`}
    >
      {pending ? (
        <ActivityIndicator color={SPINNER[variant]} />
      ) : (
        <Text className={`text-body font-semibold ${LABEL[variant]}`}>{label}</Text>
      )}
    </Pressable>
  );
}
