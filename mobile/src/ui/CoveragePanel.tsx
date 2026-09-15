import { Pressable, Text, View } from 'react-native';

import type { Coverage } from '@/api/schemas';

/** The three slices the API can actually filter a query list by. */
export type CoverageFilter = 'not_run' | 'no_images' | 'with_images';

interface Props {
  coverage: Coverage | null;
  selected: CoverageFilter | null;
  onSelect: (filter: CoverageFilter | null) => void;
}

/**
 * How much of an import has actually been searched.
 *
 * The images list can only show images that exist, so a run that stopped early
 * and a run that finished having found little look identical. These counts are
 * what separates them.
 *
 * Three of the six are tappable, because three is how many the API can filter
 * by. `total`, `searched` and `failed` are shown but inert: a tappable tile
 * would promise a list that cannot be fetched.
 */
const TAPPABLE: { key: CoverageFilter; label: (n: number) => string }[] = [
  { key: 'not_run', label: (n) => `${n} not run yet` },
  { key: 'no_images', label: (n) => `${n} ran and found nothing` },
  { key: 'with_images', label: (n) => `${n} found images` },
];

function Tile({
  value,
  caption,
  label,
  onPress,
  active,
}: {
  value: number;
  caption: string;
  label: string;
  onPress?: () => void;
  active?: boolean;
}) {
  const body = (
    <>
      <Text className={`text-title ${active ? 'text-accent-fg' : 'text-text'}`}>{value}</Text>
      <Text className={`text-meta ${active ? 'text-accent-fg' : 'text-text-secondary'}`}>
        {caption}
      </Text>
    </>
  );

  const shell = `min-w-[88px] flex-1 rounded-surface p-3 ${
    active ? 'bg-accent' : 'bg-surface-raised'
  }`;

  if (!onPress) {
    // No accessibilityRole: an inert tile announced as a button promises an
    // action that does not exist.
    return (
      <View accessibilityLabel={label} className={shell}>
        {body}
      </View>
    );
  }

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ selected: active }}
      onPress={onPress}
      className={`${shell} active:opacity-80`}
    >
      {body}
    </Pressable>
  );
}

export function CoveragePanel({ coverage, selected, onSelect }: Props) {
  if (coverage === null) return null;

  return (
    <View className="mb-6 gap-2">
      <View className="flex-row gap-2">
        <Tile value={coverage.total} caption="queries" label={`${coverage.total} queries`} />
        <Tile
          value={coverage.searched}
          caption="searched"
          label={`${coverage.searched} searched`}
        />
        <Tile value={coverage.failed} caption="failed" label={`${coverage.failed} failed`} />
      </View>

      <View className="flex-row flex-wrap gap-2">
        {TAPPABLE.map(({ key, label }) => (
          <Tile
            key={key}
            value={coverage[key]}
            caption={label(coverage[key]).replace(`${coverage[key]} `, '')}
            label={label(coverage[key])}
            active={selected === key}
            // Tapping the active slice clears it. Without that the only way
            // back to the full list is a back-and-forward, and the tile looks
            // stuck on.
            onPress={() => onSelect(selected === key ? null : key)}
          />
        ))}
      </View>
    </View>
  );
}
