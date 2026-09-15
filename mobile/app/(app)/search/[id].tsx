import { useLocalSearchParams } from 'expo-router';

import { ImageDetailScreen } from '@/screens/ImageDetailScreen';

/*
 * Two shells over one screen, this one and library/[id].tsx.
 *
 * Each tab owns its own stack, so a card in the Library tab must push onto the
 * Library stack and a run's image onto the Search stack - otherwise the back
 * gesture returns the user to the wrong tab.
 */
export default function SearchImageDetailRoute() {
  const { id } = useLocalSearchParams<{ id: string }>();

  return <ImageDetailScreen id={Number(id)} />;
}
