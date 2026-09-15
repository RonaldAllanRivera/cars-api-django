import { useEffect, useState } from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';

import { useExport } from '@/api/hooks/useExport';
import { useImageCount } from '@/api/hooks/useImageCount';
import { useImages } from '@/api/hooks/useImages';
import { useImports } from '@/api/hooks/useImports';
import type { ImageFilters } from '@/api/queryKeys';
import type { ReviewStatus } from '@/api/schemas';
import { useCan } from '@/auth/useCan';
import { ErrorBanner } from '@/ui/ErrorBanner';
import { ExportPanel } from '@/ui/ExportPanel';
import { Field } from '@/ui/Field';
import { ImageCard } from '@/ui/ImageCard';
import { InfiniteGrid } from '@/ui/InfiniteGrid';
import { PageTitle } from '@/ui/PageTitle';
import { Screen } from '@/ui/Screen';

/**
 * Mirrors config('cars-images.bulk_download_max_images'). The server enforces
 * the real value at mint and again at download, so a drifted constant here only
 * mislabels the button - it can never let an oversized ZIP through.
 */
const ZIP_CAP = 100;

const STATUSES: (ReviewStatus | 'all')[] = ['all', 'pending', 'approved', 'rejected'];

/** A verdict filter: unset, matched, or not matched. Never "unknown". */
type Verdict = 'all' | 'matched' | 'not matched';
const VERDICTS: Verdict[] = ['all', 'matched', 'not matched'];

/** The same wording VerdictBadge uses, so a filter and its badge agree. */
function verdictFilter(verdict: Verdict): boolean | undefined {
  if (verdict === 'all') return undefined;

  return verdict === 'matched';
}

function Chips<T extends string>({
  label,
  options,
  value,
  onChange,
  display = (option) => option,
}: {
  label: string;
  options: T[];
  value: T;
  onChange: (option: T) => void;
  display?: (option: T) => string;
}) {
  return (
    <View className="mb-3 gap-1">
      <Text className="text-meta font-medium text-text-secondary">{label}</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false}>
        <View className="flex-row gap-2">
          {options.map((option) => (
            <Pressable
              key={option}
              accessibilityRole="button"
              accessibilityState={{ selected: value === option }}
              className={`rounded-pill px-3 py-1 ${
                value === option ? 'bg-accent' : 'bg-surface-sunken'
              }`}
              onPress={() => onChange(option)}
            >
              <Text
                className={`text-micro ${
                  value === option ? 'text-accent-fg' : 'text-text-secondary'
                }`}
              >
                {display(option)}
              </Text>
            </Pressable>
          ))}
        </View>
      </ScrollView>
    </View>
  );
}

export default function ImageGrid() {
  const [make, setMake] = useState('');
  const [debouncedMake, setDebouncedMake] = useState('');
  const [status, setStatus] = useState<ReviewStatus | 'all'>('all');
  const [makeMatch, setMakeMatch] = useState<Verdict>('all');
  const [yearMatch, setYearMatch] = useState<Verdict>('all');
  const [importId, setImportId] = useState<string>('all');

  // The raw input drives the field; only the settled value drives the query.
  // Without this every keystroke is a new query key with no cached data, so
  // the list tears down to a skeleton and refetches once per character - and
  // every authenticated route shares one rate-limit bucket per user, so the
  // burst can throttle endpoints this screen never touches.
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedMake(make), 300);

    return () => clearTimeout(timer);
  }, [make]);

  const filters: ImageFilters = {
    make: debouncedMake.trim() || undefined,
    review_status: status === 'all' ? undefined : status,
    make_confirmed: verdictFilter(makeMatch),
    year_confirmed: verdictFilter(yearMatch),
    csv_import_id: importId === 'all' ? undefined : Number(importId),
  };

  const query = useImages(filters);
  const imports = useImports();
  const canExport = useCan('exports:read');
  // Disabled rather than skipped - hooks cannot be conditional. The web build
  // shows no export panel, so it spends no request on a count it cannot use.
  const count = useImageCount(filters, { enabled: canExport });
  const exporter = useExport(filters);

  const importOptions = [
    'all',
    ...(imports.data?.pages.flatMap((page) => page.data.map((csvImport) => String(csvImport.id))) ?? []),
  ];
  const importNames = new Map(
    imports.data?.pages.flatMap((page) => page.data.map((csvImport) => [String(csvImport.id), csvImport.original_filename] as const)) ?? [],
  );

  return (
    <Screen>
      <PageTitle title="Library - Cars Images" />
      {/* An exact match, not a search: ListImagesRequest::apply() does
          `where('make', ...)`, so "Toy" - and every other prefix - matches
          nothing. The hint has to say so, or the screen reads as broken. */}
      <View className="mb-3">
        <Field
          label="Make"
          hint="An exact match - 'Toyota', not 'Toy'."
          placeholder="e.g. Toyota"
          value={make}
          onChangeText={setMake}
        />
      </View>

      <Chips label="Review" options={STATUSES} value={status} onChange={setStatus} />
      <Chips label="Make match" options={VERDICTS} value={makeMatch} onChange={setMakeMatch} />
      <Chips label="Year match" options={VERDICTS} value={yearMatch} onChange={setYearMatch} />
      {importOptions.length > 1 ? (
        <Chips
          label="CSV import"
          options={importOptions}
          value={importId}
          onChange={setImportId}
          display={(option) => (option === 'all' ? 'all' : (importNames.get(option) ?? option))}
        />
      ) : null}

      {canExport ? (
        <>
          {exporter.isError ? (
            <ErrorBanner
              message={exporter.error instanceof Error ? exporter.error.message : 'The export could not be started.'}
            />
          ) : null}
          <ExportPanel
            count={count.data}
            zipCap={ZIP_CAP}
            pending={exporter.isPending ? (exporter.variables ?? null) : null}
            onExport={(format) => exporter.mutate(format)}
          />
        </>
      ) : null}

      <InfiniteGrid
        query={query}
        numColumns={2}
        keyExtractor={(image) => String(image.id)}
        renderItem={(image) => (
          <ImageCard
            image={image}
            href={{ pathname: '/(app)/library/[id]', params: { id: image.id } }}
          />
        )}
        emptyTitle="No images match"
        emptyHint="Loosen a filter, or check the make is spelled exactly - 'Toyota', not 'Toy'."
      />
    </Screen>
  );
}
