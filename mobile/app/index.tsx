import { Link } from 'expo-router';
import { ActivityIndicator, Text, View } from 'react-native';

import { useAuth } from '@/auth/AuthContext';
import { color } from '@/theme/tokens';
import { PageTitle } from '@/ui/PageTitle';

const BUTTON = 'mt-4 rounded-control bg-accent px-6 py-4 text-body font-semibold text-accent-fg';

export default function Landing() {
  const { status } = useAuth();

  return (
    <View className="flex-1 items-center justify-center gap-4 bg-surface p-6">
      <PageTitle title="Cars Images" />
      <Text className="text-center text-title text-text">Cars Images</Text>
      <Text className="max-w-md text-center text-body text-text-secondary">
        Search Wikimedia Commons for high-resolution car photography by make, model and year,
        review what comes back, and watch the harvest pipeline&apos;s health.
      </Text>

      {/* An already-signed-in visitor is offered the way through rather than
          redirected: this is the shareable URL, so it stays a landing page.
          Sending them to "Sign in" instead would mint a second Sanctum token
          for the same device name on every visit, which is precisely what
          naming tokens per device is meant to avoid. */}
      {status === 'loading' ? <ActivityIndicator className="mt-4" color={color.accentText} /> : null}

      {status === 'authenticated' ? (
        <Link href="/(app)/search" className={BUTTON}>
          Continue to the app
        </Link>
      ) : null}

      {status === 'anonymous' ? (
        <Link href="/login" className={BUTTON}>
          Sign in
        </Link>
      ) : null}
    </View>
  );
}
