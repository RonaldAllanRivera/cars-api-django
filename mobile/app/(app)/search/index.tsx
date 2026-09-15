import { router } from 'expo-router';
import { useState } from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';

import { ApiValidationError } from '@/api/client';
import {
  MAX_IMAGES_PER_YEAR,
  MAX_YEAR_SPAN,
  useCreateSearch,
} from '@/api/hooks/useCreateSearch';
import { Button } from '@/ui/Button';
import { ErrorBanner } from '@/ui/ErrorBanner';
import { Field } from '@/ui/Field';
import { PageTitle } from '@/ui/PageTitle';
import { Screen } from '@/ui/Screen';

export default function SearchForm() {
  const createSearch = useCreateSearch();
  const [make, setMake] = useState('');
  const [model, setModel] = useState('');
  const [fromYear, setFromYear] = useState('');
  const [toYear, setToYear] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  // The run behind a blocked/failed notice, so the banner can link to it
  // without navigating away from the message the user has to read.
  const [noticeRunId, setNoticeRunId] = useState<number | null>(null);

  const submit = async () => {
    setError(null);
    setNotice(null);
    setNoticeRunId(null);

    const from = Number(fromYear);
    const to = Number(toYear);

    if (!make.trim()) {
      setError('A make is required.');

      return;
    }

    if (!Number.isInteger(from) || !Number.isInteger(to) || from < 1900 || to < 1900) {
      setError('Enter both years as four-digit numbers.');

      return;
    }

    // Checked here as well as server-side: the search runs inline inside the
    // request, so a too-wide span is a limit worth showing before the wait.
    if (Math.abs(to - from) > MAX_YEAR_SPAN) {
      setError(
        `The year range may span at most ${MAX_YEAR_SPAN} years, because the search runs inside the request.`,
      );

      return;
    }

    try {
      const result = await createSearch.mutateAsync({
        make: make.trim(),
        model: model.trim() || undefined,
        from_year: from,
        to_year: to,
        images_per_year: MAX_IMAGES_PER_YEAR,
      });

      if (result.outcome === 'blocked' || result.outcome === 'failed') {
        setNotice(
          result.outcome === 'blocked'
            ? `${result.message ?? 'Wikimedia is rate-limiting this server.'}${
                result.retryAfterSeconds ? ` Try again in ${result.retryAfterSeconds}s.` : ''
              }`
            : (result.message ?? 'The search failed. The reason is in the error log.'),
        );

        // Every outcome produced a real run row, so the user keeps a link to
        // it - but navigating now would cover the notice before it is read,
        // and the run screen only knows the row is `failed`, not that
        // Wikimedia is throttling or for how long. So: stay, and offer the
        // link.
        setNoticeRunId(result.search.id);

        return;
      }

      router.push({ pathname: '/(app)/search/runs/[id]', params: { id: result.search.id } });
    } catch (caught) {
      setError(
        caught instanceof ApiValidationError
          ? (caught.first('to_year') ?? caught.first('make') ?? caught.message)
          : caught instanceof Error
            ? caught.message
            : 'The search could not be started.',
      );
    }
  };

  return (
    <Screen>
      <PageTitle title="New search - Cars Images" />
      <ScrollView contentContainerClassName="gap-3">
        <Text className="text-title text-text">New search</Text>
        <Text className="text-meta text-text-secondary">
          Runs immediately against Wikimedia Commons. Up to {MAX_YEAR_SPAN + 1} years,{' '}
          {MAX_IMAGES_PER_YEAR} images per year.
        </Text>

        {error ? <ErrorBanner message={error} /> : null}
        {notice ? (
          <View className="rounded-surface border border-accent/40 bg-accent/10 p-3">
            <Text className="text-body text-accent-text">{notice}</Text>
            {noticeRunId !== null ? (
              <Pressable
                className="mt-2 self-start"
                onPress={() =>
                  router.push({ pathname: '/(app)/search/runs/[id]', params: { id: noticeRunId } })
                }
              >
                <Text className="text-meta font-semibold text-accent-text">View the run</Text>
              </Pressable>
            ) : null}
          </View>
        ) : null}

        <Field label="Make" placeholder="e.g. Toyota" value={make} onChangeText={setMake} />
        <Field
          label="Model"
          hint="Optional. Narrows the search to one model."
          value={model}
          onChangeText={setModel}
        />
        <View className="flex-row gap-3">
          <View className="flex-1">
            <Field
              label="From year"
              keyboardType="number-pad"
              value={fromYear}
              onChangeText={setFromYear}
            />
          </View>
          <View className="flex-1">
            <Field
              label="To year"
              keyboardType="number-pad"
              value={toYear}
              onChangeText={setToYear}
            />
          </View>
        </View>

        <Button
          label="Run search"
          onPress={submit}
          pending={createSearch.isPending}
          size="lg"
        />

        {createSearch.isPending ? (
          <Text className="text-center text-meta text-text-muted">
            This runs inline and can take several seconds.
          </Text>
        ) : null}

        {/* The "Browse all images" link that used to sit here is gone: the
            grid is the Library tab now, rather than a footnote at the bottom
            of a form. */}
        <Pressable
          className="mt-2 items-center py-2"
          onPress={() => router.push('/(app)/search/runs')}
        >
          <Text className="text-meta font-medium text-accent-text">See recent runs</Text>
        </Pressable>
      </ScrollView>
    </Screen>
  );
}
