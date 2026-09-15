import type { ReactNode } from 'react';
import { Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

/**
 * `title` is the in-body heading for screens that want one - a scrolling
 * dashboard whose heading should scroll away, say. It is NOT a second copy of
 * the navigator title: a screen is titled once, by its navigator, and every
 * screen here previously repeated that title immediately below the header.
 */
export function Screen({ children, title }: { children: ReactNode; title?: string }) {
  return (
    <SafeAreaView className="flex-1 bg-surface">
      <View className="flex-1 p-4">
        {title ? <Text className="mb-4 text-title text-text">{title}</Text> : null}
        {children}
      </View>
    </SafeAreaView>
  );
}
