import { Redirect, router } from 'expo-router';
import { useState } from 'react';
import { Platform, Text, View } from 'react-native';

import { ApiValidationError } from '@/api/client';
import { useAuth } from '@/auth/AuthContext';
import { Button } from '@/ui/Button';
import { ErrorBanner } from '@/ui/ErrorBanner';
import { Field } from '@/ui/Field';
import { PageTitle } from '@/ui/PageTitle';
import { Screen } from '@/ui/Screen';

/** Names the token so a lost device can be revoked without rotating the rest. */
const DEVICE_NAME = Platform.select({ web: 'web', android: 'android', ios: 'ios' }) ?? 'unknown';

export default function Login() {
  const { signIn, status } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // After every hook, so the early return cannot reorder them. A signed-in
  // visitor reaching this screen - from the landing page, or a bookmark -
  // would otherwise sign in again and mint a second Sanctum token under the
  // same device name, which is exactly what naming tokens per device is
  // meant to avoid.
  if (status === 'authenticated') {
    return <Redirect href="/(app)/search" />;
  }

  const submit = async () => {
    setBusy(true);
    setError(null);

    try {
      await signIn(email.trim(), password, DEVICE_NAME);
      router.replace('/(app)/search');
    } catch (caught) {
      setError(
        caught instanceof ApiValidationError
          ? (caught.first('email') ?? caught.message)
          : caught instanceof Error
            ? caught.message
            : 'Sign in failed.',
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <Screen>
      <PageTitle title="Sign in - Cars Images" />
      <View className="flex-1 justify-center gap-4">
        <Text className="text-title text-text">Sign in</Text>

        {error ? <ErrorBanner message={error} /> : null}

        <Field
          label="Email"
          value={email}
          onChangeText={setEmail}
          autoCapitalize="none"
          autoComplete="email"
          keyboardType="email-address"
        />

        <Field
          label="Password"
          value={password}
          onChangeText={setPassword}
          autoCapitalize="none"
          secureTextEntry
          onSubmitEditing={submit}
        />

        <Button label="Sign in" onPress={submit} pending={busy} size="lg" />

        <Text className="text-center text-meta text-text-muted">
          Credentials are issued on request. There is no demo account.
        </Text>
      </View>
    </Screen>
  );
}
