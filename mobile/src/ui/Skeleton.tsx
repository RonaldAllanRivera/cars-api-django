import { View } from 'react-native';

/**
 * A placeholder shaped like the content it stands in for.
 *
 * Static, not shimmering. The design spends its motion budget in exactly one
 * place - the review card leaving when a verdict lands - and a shimmer here
 * would be decoration competing with it.
 */
export function Skeleton({
  height,
  aspectRatio,
  className = '',
}: {
  height?: number;
  aspectRatio?: number;
  className?: string;
}) {
  return (
    <View
      testID="skeleton"
      // A screen reader announcing six empty boxes is worse than silence; the
      // SkeletonGrid's progressbar role is what should be announced instead.
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
      style={{ height, aspectRatio }}
      className={`rounded-surface bg-surface-raised ${className}`}
    />
  );
}

export function SkeletonGrid({
  count,
  numColumns = 1,
  aspectRatio = 4 / 3,
}: {
  count: number;
  numColumns?: number;
  aspectRatio?: number;
}) {
  return (
    <View
      accessibilityRole="progressbar"
      accessibilityLabel="Loading"
      className="flex-row flex-wrap gap-2"
    >
      {Array.from({ length: count }, (_, index) => (
        <Skeleton
          key={index}
          aspectRatio={aspectRatio}
          className={numColumns > 1 ? 'min-w-[45%] flex-1' : 'w-full'}
        />
      ))}
    </View>
  );
}
