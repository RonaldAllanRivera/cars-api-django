import * as DocumentPicker from 'expo-document-picker';
import { router } from 'expo-router';
import { useState } from 'react';
import { ScrollView, Text, View } from 'react-native';

import { ApiValidationError } from '@/api/client';
import { useUploadImport } from '@/api/hooks/useUploadImport';
import { useCan } from '@/auth/useCan';
import type { PickedCsv } from '@/api/hooks/useUploadImport';
import { Button } from '@/ui/Button';
import { ErrorBanner } from '@/ui/ErrorBanner';
import { PageTitle } from '@/ui/PageTitle';
import { Screen } from '@/ui/Screen';

/**
 * Accepted types, widened deliberately: a CSV picked from Files, Drive or a
 * mail attachment arrives under any of these, and the server applies the same
 * list. A wildcard is the last entry because some Android providers report no
 * type at all, and a picker that shows nothing selectable is worse than one that lets
 * the server reject a bad file. (The wildcard is written as a string below
 * rather than named here, because it would close this comment.)
 */
const CSV_TYPES = [
  'text/csv',
  'text/comma-separated-values',
  'application/csv',
  'application/vnd.ms-excel',
  'text/plain',
  '*/*',
];

export default function UploadCsv() {
  const upload = useUploadImport();
  const [file, setFile] = useState<PickedCsv | null>(null);
  const [error, setError] = useState<string | null>(null);
  const canUpload = useCan('imports:write');

  // After every hook, so this return cannot reorder them. The route stays
  // reachable by URL even with its entry point hidden, so the screen itself has
  // to say why there is no picker - hiding only the link would leave a URL that
  // opens straight into a guaranteed 403.
  if (!canUpload) {
    return (
      <Screen>
        <PageTitle title="Upload CSV - Cars Images" />
        <View className="gap-2">
          <Text className="text-section text-text">Uploads happen in the admin panel</Text>
          <Text className="text-body text-text-secondary">
            This build cannot upload CSVs. Upload from the admin panel on a computer; the
            import appears in the Pipeline tab once it exists.
          </Text>
        </View>
      </Screen>
    );
  }

  const pick = async () => {
    setError(null);

    const result = await DocumentPicker.getDocumentAsync({ type: CSV_TYPES, copyToCacheDirectory: true });

    if (result.canceled) return;

    const picked = result.assets[0];

    if (!picked) return;

    setFile({ uri: picked.uri, name: picked.name, mimeType: picked.mimeType });
  };

  const submit = async () => {
    if (!file) return;

    setError(null);

    try {
      const created = await upload.mutateAsync(file);

      router.replace({ pathname: '/(app)/pipeline/[id]', params: { id: created.id } });
    } catch (caught) {
      // The server's rejection messages are written for a human ("Missing
      // required columns: Model."), so they are shown verbatim rather than
      // replaced with something generic.
      setError(
        caught instanceof ApiValidationError
          ? (caught.first('csv_file') ?? caught.message)
          : caught instanceof Error
            ? caught.message
            : 'The CSV could not be imported.',
      );
    }
  };

  return (
    <Screen>
      <PageTitle title="Upload CSV - Cars Images" />
      <ScrollView contentContainerClassName="gap-4">
        <Text className="text-title text-text">Upload a CSV</Text>

        <Text className="text-body text-text-secondary">
          Columns Make, Model and Year. Rows are de-duplicated by all three, so the query count is
          the de-duplicated one.
        </Text>

        {/* The standing reminder the panel shows before an upload: a CSV that
            passes the row cap still commits the app to a long paced run
            against Wikimedia later. Saying so here is the point of decision. */}
        <View className="rounded-surface border border-accent/40 bg-accent/10 p-3">
          <Text className="text-meta text-accent-text">
            Importing only queues the searches. Running them is a separate, paced crawl against
            Wikimedia — plan for it to take a while, and to be resumable.
          </Text>
        </View>

        {error ? <ErrorBanner message={error} /> : null}

        <Button label={file ? 'Choose a different file' : 'Choose a CSV'} variant="secondary" onPress={() => void pick()} />

        {file ? (
          <View className="rounded-surface bg-surface-raised p-3">
            <Text className="text-body text-text" numberOfLines={1}>
              {file.name}
            </Text>
          </View>
        ) : null}

        <Button
          label="Import"
          onPress={() => void submit()}
          size="lg"
          disabled={!file}
          pending={upload.isPending}
        />

        {upload.isPending ? (
          <Text className="text-center text-meta text-text-muted">
            Parsing and queueing. Large files take a moment.
          </Text>
        ) : null}
      </ScrollView>
    </Screen>
  );
}
