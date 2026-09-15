import { Image } from 'expo-image';
import { Text, View } from 'react-native';

import type { Image as CarImage } from '@/api/schemas';
import { byline } from '@/format/imageTitle';
import { Button } from './Button';
import { VerdictBadge } from './VerdictBadge';

/**
 * The review queue's card - the one interaction the admin panel cannot do at
 * all, and so the one place this design spends its boldness.
 *
 * Presentational on purpose: no hooks, no router, no mutation. That is what
 * makes it mountable in a test, which the screen around it is not.
 *
 * Approve is the primary action and Reject is tinted, so the constructive
 * verdict carries the weight. Approve being amber while the resulting badge is
 * emerald is deliberate: amber is the primary-ACTION colour and emerald is the
 * approved-STATE colour, exactly as the panel's amber "Create" button yields a
 * green "completed" badge. Colouring the button emerald would collapse action
 * and state into one hue and leave the app with no primary colour at all.
 */
export function ReviewCard({
  image,
  onApprove,
  onReject,
  pending = false,
}: {
  image: CarImage;
  onApprove: () => void;
  onReject: () => void;
  pending?: boolean;
}) {
  const name = [image.year, image.make, image.model].filter(Boolean).join(' ');
  const credit = byline(image.attribution, image.title);

  return (
    <View className="mb-3 overflow-hidden rounded-surface bg-surface-raised">
      <View>
        <Image
          source={image.thumbnail_url ?? image.source_url}
          style={{ width: '100%', aspectRatio: 4 / 3 }}
          contentFit="cover"
          transition={150}
          cachePolicy="disk"
          accessibilityLabel={name}
        />
        {/* Over the image rather than under the title: the verdict is about
            what is in the picture, and reading it next to the picture is the
            comparison the reviewer is being asked to make. */}
        <View className="absolute bottom-2 left-2 flex-row gap-1">
          <VerdictBadge kind="make" value={image.make_confirmed} />
          <VerdictBadge kind="year" value={image.year_confirmed} />
        </View>
      </View>

      <View className="gap-3 p-3">
        <View className="gap-1">
          <Text className="text-section text-text" numberOfLines={1}>
            {name}
          </Text>
          {credit ? (
            <Text className="text-meta text-text-muted" numberOfLines={1}>
              {credit}
            </Text>
          ) : null}
        </View>

        {/* 2:1. Both lock while either is in flight - a second tap would fire
            a second mutation for one image, and the losing verdict would race
            the optimistic cache update of the winning one. */}
        <View className="flex-row gap-2">
          <Button label="Approve" onPress={onApprove} pending={pending} flex={2} />
          <Button
            label="Reject"
            onPress={onReject}
            variant="danger-subtle"
            disabled={pending}
            flex={1}
          />
        </View>
      </View>
    </View>
  );
}
