import { Image } from 'expo-image';
import { ScrollView, Text, View } from 'react-native';

import { useImage } from '@/api/hooks/useImages';
import { cleanTitle } from '@/format/imageTitle';
import { ErrorBanner } from '@/ui/ErrorBanner';
import { PageTitle } from '@/ui/PageTitle';
import { Screen } from '@/ui/Screen';
import { Skeleton } from '@/ui/Skeleton';
import { StatusBadge } from '@/ui/StatusBadge';
import { VerdictBadge } from '@/ui/VerdictBadge';

/**
 * One screen, two routes.
 *
 * Takes `id` as a prop rather than reading useLocalSearchParams itself, so
 * both route shells can mount it - and so a test can, which a screen calling
 * router hooks cannot be.
 */
function Row({ label, value }: { label: string; value: string | null }) {
  if (!value) return null;

  return (
    <View className="border-b border-border py-2">
      <Text className="text-meta text-text-secondary">{label}</Text>
      <Text className="text-body text-text">{value}</Text>
    </View>
  );
}

export function ImageDetailScreen({ id }: { id: number }) {
  const query = useImage(id);

  if (query.isLoading) {
    return (
      <Screen>
        <PageTitle title="Image - Cars Images" />
        <Skeleton aspectRatio={4 / 3} />
      </Screen>
    );
  }

  if (query.isError || !query.data) {
    return (
      <Screen>
        <PageTitle title="Image - Cars Images" />
        <ErrorBanner message={query.error instanceof Error ? query.error.message : 'Not found.'} />
      </Screen>
    );
  }

  const image = query.data;

  return (
    <Screen>
      <PageTitle title="Image - Cars Images" />
      <ScrollView>
        <Image
          source={image.source_url}
          style={{ width: '100%', aspectRatio: 4 / 3, borderRadius: 12 }}
          contentFit="contain"
          transition={150}
          cachePolicy="disk"
        />

        <Text className="mt-3 text-section text-text">
          {[image.make, image.model, image.year].filter(Boolean).join(' ')}
        </Text>

        <View className="mt-2 flex-row flex-wrap gap-2">
          <StatusBadge status={image.review_status} />
          <StatusBadge status={image.download_status} />
        </View>

        {/* The machine's two verdicts, beside the human's above. Read-only:
            nothing in this client ever writes make_confirmed or
            year_confirmed - they are the relevance checker's answer, and
            review_status is separate precisely so the two stay comparable. */}
        <View className="mt-2 flex-row flex-wrap gap-2">
          <VerdictBadge kind="make" value={image.make_confirmed} />
          <VerdictBadge kind="year" value={image.year_confirmed} />
        </View>

        <View className="mt-4">
          <Row label="Title" value={cleanTitle(image.title)} />
          <Row label="Description" value={image.description} />
          <Row label="Licence" value={image.license} />
          <Row label="Attribution" value={image.attribution} />
          <Row
            label="Dimensions"
            value={image.width && image.height ? `${image.width} × ${image.height}` : null}
          />
          <Row label="Source" value={image.source_url} />
        </View>
      </ScrollView>
    </Screen>
  );
}
