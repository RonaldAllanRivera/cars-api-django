import { Image } from 'expo-image';
import { Link } from 'expo-router';
import type { Href } from 'expo-router';
import { Pressable, Text, View } from 'react-native';

import type { Image as CarImage } from '@/api/schemas';
import { byline } from '@/format/imageTitle';
import { StatusBadge } from './StatusBadge';

const SHELL = 'mb-3 flex-1 overflow-hidden rounded-surface bg-surface-raised';

/**
 * Presentational. `href` is supplied by the screen rather than hardcoded here:
 * each tab owns its own stack, so a destination baked into this component
 * would push onto whichever stack it names and yank the user out of the tab
 * they were in. Omit it for a card that should not navigate.
 */
export function ImageCard({ image, href }: { image: CarImage; href?: Href }) {
  const name = [image.make, image.model, image.year].filter(Boolean).join(' ');
  const credit = byline(image.attribution, image.title);

  const body = (
    <>
      <Image
        source={image.thumbnail_url ?? image.source_url}
        style={{ width: '100%', aspectRatio: 4 / 3 }}
        contentFit="cover"
        transition={150}
        cachePolicy="disk"
        accessibilityLabel={name}
      />
      <View className="gap-1 p-3">
        <Text className="text-body font-medium text-text" numberOfLines={1}>
          {name}
        </Text>
        {credit ? (
          <Text className="text-meta text-text-muted" numberOfLines={1}>
            {credit}
          </Text>
        ) : null}
        <StatusBadge status={image.review_status} />
      </View>
    </>
  );

  if (!href) {
    return <View className={SHELL}>{body}</View>;
  }

  return (
    <Link href={href} asChild>
      <Pressable className={`${SHELL} active:opacity-80`}>{body}</Pressable>
    </Link>
  );
}
