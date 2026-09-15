import { Link, router } from 'expo-router';
import { Pressable, Text, View } from 'react-native';

import { useImports } from '@/api/hooks/useImports';
import { useCan } from '@/auth/useCan';
import type { Import } from '@/api/schemas';
import { InfiniteGrid } from '@/ui/InfiniteGrid';
import { PageTitle } from '@/ui/PageTitle';
import { Screen } from '@/ui/Screen';

export default function ImportsList() {
  const query = useImports();
  // The web build cannot upload - imports:write stays off localStorage tokens,
  // and CSVs are uploaded from the admin panel. Offering the action there would
  // lead to a screen whose only outcome is a 403.
  const canUpload = useCan('imports:write');

  return (
    <Screen>
      <PageTitle title="Pipeline - Cars Images" />

      <InfiniteGrid
        query={query}
        keyExtractor={(csvImport) => String(csvImport.id)}
        emptyTitle="No CSV imports yet"
        emptyHint={
          canUpload
            ? 'Upload a CSV of make, model and year to queue up searches.'
            : 'CSVs are uploaded from the admin panel. Imports appear here once they exist.'
        }
        emptyAction={
          canUpload
            ? { label: 'Upload a CSV', onPress: () => router.push('/(app)/pipeline/upload') }
            : undefined
        }
        renderItem={(csvImport: Import) => (
          <Link
            href={{ pathname: '/(app)/pipeline/[id]', params: { id: csvImport.id } }}
            asChild
          >
            <Pressable className="mb-2 rounded-surface bg-surface-raised p-3 active:opacity-80">
              <Text className="text-body font-medium text-text" numberOfLines={1}>
                {csvImport.original_filename}
              </Text>
              <View className="mt-1 flex-row items-center gap-2">
                <Text className="text-meta text-text-secondary">
                  {csvImport.unique_combos ?? 0} queries
                </Text>
                {csvImport.duplicates_skipped ? (
                  <Text className="text-meta text-text-muted">
                    {csvImport.duplicates_skipped} duplicates skipped
                  </Text>
                ) : null}
              </View>
              {csvImport.importer_name ? (
                <Text className="mt-1 text-micro text-text-muted">
                  Uploaded by {csvImport.importer_name}
                </Text>
              ) : null}
            </Pressable>
          </Link>
        )}
      />
    </Screen>
  );
}
