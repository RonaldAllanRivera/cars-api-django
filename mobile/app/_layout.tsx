import '../global.css';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useState } from 'react';

import { ApiError } from '@/api/client';
import { AuthProvider } from '@/auth/AuthContext';

export default function RootLayout() {
  // Created in state so Fast Refresh does not discard the cache on every edit.
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            // A 4xx will not become a 2xx by being asked again, and retrying
            // one is not free: a dead token fires three 401s, each of which
            // signs the user out; a 422 or a contract-drift ApiError makes
            // the user wait through three identical failures; and a 429 is
            // hit twice more against a bucket every authenticated route
            // shares. Everything else - a 5xx, a dropped connection - still
            // gets its two retries.
            retry: (count, error) =>
              !(error instanceof ApiError && error.status >= 400 && error.status < 500) &&
              count < 2,
            staleTime: 30_000,
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <StatusBar style="auto" />
        {/* Page titles live in each screen's <PageTitle>, not in a `title`
            option here: expo-router disables react-navigation's document
            title, so a navigation title would set nothing on the web. */}
        <Stack screenOptions={{ headerShown: false }} />
      </AuthProvider>
    </QueryClientProvider>
  );
}
