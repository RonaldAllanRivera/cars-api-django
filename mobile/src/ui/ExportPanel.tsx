import { Text, View } from 'react-native';

import { Button } from './Button';

export type ExportFormat = 'csv' | 'zip';

interface Props {
  /** Undefined while the count is still loading. */
  count: number | undefined;
  zipCap: number;
  /** The format currently being minted, if any. */
  pending: ExportFormat | null;
  onExport: (format: ExportFormat) => void;
}

/**
 * Exports what the Library is showing.
 *
 * Presentational. The count is advisory - the server recounts at mint and again
 * at download - so this only decides what to *offer*; it never decides what is
 * allowed.
 */
export function ExportPanel({ count, zipCap, pending, onExport }: Props) {
  // Rendering "0 images match" before the count arrives would briefly tell the
  // user there is nothing to export.
  if (count === undefined) return null;

  const empty = count === 0;
  const zipTooLarge = count > zipCap;
  const busy = pending !== null;

  return (
    <View className="mb-4 gap-3 rounded-surface border border-border-strong bg-surface-raised p-3">
      <Text className="text-section text-text">
        {count} {count === 1 ? 'image matches' : 'images match'}
      </Text>

      <View className="flex-row gap-2">
        <Button
          label="Export CSV"
          variant="secondary"
          flex={1}
          pending={pending === 'csv'}
          disabled={empty || busy}
          onPress={() => onExport('csv')}
        />
        {/* Disabled over the cap rather than left pressable for the server to
            refuse: the reason belongs beside the button before it is pressed. */}
        <Button
          label="Export ZIP"
          variant="secondary"
          flex={1}
          pending={pending === 'zip'}
          disabled={empty || zipTooLarge || busy}
          onPress={() => onExport('zip')}
        />
      </View>

      {zipTooLarge ? (
        <Text className="text-meta text-danger-text">
          A ZIP is limited to {zipCap} images. Narrow the filter to export one — the CSV has no
          limit.
        </Text>
      ) : (
        // Not buried: the download leaves the app, and a ZIP of this many images
        // is fetched from Wikimedia and resized before it starts.
        <Text className="text-meta text-text-muted">
          Exports open in your browser. A ZIP can take a minute or two to start.
        </Text>
      )}
    </View>
  );
}
