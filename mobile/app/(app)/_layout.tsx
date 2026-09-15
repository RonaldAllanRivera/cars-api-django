import Ionicons from '@expo/vector-icons/Ionicons';
import { Redirect, Tabs } from 'expo-router';
import { ActivityIndicator, View } from 'react-native';
import type { ColorValue } from 'react-native';

import { useAuth } from '@/auth/AuthContext';
import { color } from '@/theme/tokens';
import { PageTitle } from '@/ui/PageTitle';

/*
 * Icon names track the panel's own $navigationIcon declarations, so the two
 * clients share one vocabulary: Results is heroicon-o-photo, the error log is
 * a chart, and so on. Ionicons is the family Expo ships; the outline/filled
 * pair is what gives the tab bar its selected state.
 */
const ICON = {
  search: 'search',
  library: 'images',
  pipeline: 'layers',
  review: 'checkmark-circle',
  health: 'pulse',
} as const;

function TabIcon({
  name,
  color: tint,
  focused,
}: {
  name: keyof typeof ICON;
  // ColorValue, not string: react-navigation hands the icon whatever the
  // tabBarActiveTintColor is, and that may be an OpaqueColorValue from
  // PlatformColor. Ionicons accepts the same union, so widening here is
  // truer than casting at the call site.
  color: ColorValue;
  focused: boolean;
}) {
  return (
    <Ionicons
      testID="tab-icon"
      name={focused ? ICON[name] : (`${ICON[name]}-outline` as const)}
      size={24}
      color={tint}
    />
  );
}

export default function AppLayout() {
  const { status } = useAuth();

  if (status === 'loading') {
    return (
      <View className="flex-1 items-center justify-center bg-surface">
        {/* The static export renders this branch for every route behind the
            guard - whether there is a session is only knowable in the
            browser - so without a title here those pages ship a blank tab.
            Each screen's own <PageTitle> replaces it once it mounts. */}
        <PageTitle title="Cars Images" />
        <ActivityIndicator color={color.accentText} />
      </View>
    );
  }

  if (status === 'anonymous') {
    return <Redirect href="/login" />;
  }

  return (
    <Tabs
      screenOptions={{
        headerStyle: { backgroundColor: color.surfaceRaised },
        headerTintColor: color.text,
        tabBarStyle: { backgroundColor: color.surfaceRaised, borderTopColor: color.border },
        tabBarActiveTintColor: color.accentText,
        tabBarInactiveTintColor: color.textSecondary,
      }}
    >
      {/* headerShown: false - this tab nests a Stack, which owns the header. */}
      <Tabs.Screen
        name="search"
        options={{
          title: 'Search',
          headerShown: false,
          tabBarIcon: (props) => <TabIcon name="search" {...props} />,
        }}
      />
      {/* headerShown: false - this tab nests a Stack, which owns the header. */}
      <Tabs.Screen
        name="library"
        options={{
          title: 'Library',
          headerShown: false,
          tabBarIcon: (props) => <TabIcon name="library" {...props} />,
        }}
      />
      {/* headerShown: false - this tab nests a Stack, which owns the header. */}
      <Tabs.Screen
        name="pipeline"
        options={{
          title: 'Pipeline',
          headerShown: false,
          tabBarIcon: (props) => <TabIcon name="pipeline" {...props} />,
        }}
      />
      <Tabs.Screen
        name="review"
        options={{
          title: 'Review',
          tabBarIcon: (props) => <TabIcon name="review" {...props} />,
        }}
      />
      <Tabs.Screen
        name="health"
        options={{
          title: 'Health',
          tabBarIcon: (props) => <TabIcon name="health" {...props} />,
        }}
      />
    </Tabs>
  );
}
