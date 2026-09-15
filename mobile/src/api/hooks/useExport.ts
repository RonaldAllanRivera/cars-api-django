import { useMutation } from '@tanstack/react-query';
import * as Linking from 'expo-linking';

import { apiRequest } from '../client';
import type { ImageFilters } from '../queryKeys';
import { ExportLinkSchema } from '../schemas';
import type { ExportFormat } from '@/ui/ExportPanel';

/**
 * Mint a signed export link, then hand it to the system browser.
 *
 * The browser owns the download rather than the app: a ZIP can take a minute
 * or two to build, and React Query's retry would restart a hundred Wikimedia
 * fetches, where the browser simply shows download progress.
 */
export function useExport(filters: ImageFilters) {
  return useMutation({
    mutationFn: async (format: ExportFormat) => {
      const link = await apiRequest('/exports', {
        method: 'POST',
        body: { format, ...filters },
        schema: ExportLinkSchema,
      });

      await Linking.openURL(link.url);

      return link;
    },
  });
}
