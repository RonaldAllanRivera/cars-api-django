import { useLocalSearchParams } from 'expo-router';

import { ImageDetailScreen } from '@/screens/ImageDetailScreen';

/*
 * The Library tab's copy of the image detail. See search/[id].tsx for why
 * there are two shells over one screen.
 */
export default function LibraryImageDetailRoute() {
  const { id } = useLocalSearchParams<{ id: string }>();

  return <ImageDetailScreen id={Number(id)} />;
}
