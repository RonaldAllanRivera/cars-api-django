import { useMutation } from '@tanstack/vue-query';
import { toValue } from 'vue';
import type { MaybeRefOrGetter } from 'vue';

import { apiRequest } from '../client';
import { compact } from '../queryKeys';
import type { ImageFilters } from '../queryKeys';
import { ExportLinkSchema } from '../schemas';
import type { ExportLink } from '../schemas';

export type ExportFormat = 'csv' | 'zip';

export interface ExportResult {
  link: ExportLink;
  /** False when the browser blocked the new tab; the caller offers the link instead. */
  opened: boolean;
}

/**
 * Mints a signed export link and hands it to a new tab, which owns the
 * download: a ZIP can take a minute to build, and a retry from here would
 * restart every Wikimedia fetch behind it.
 *
 * The tab is opened synchronously, before the request, because browsers only
 * allow window.open inside the click that caused it. It is pointed at the link
 * once it exists, or closed if minting fails.
 */
export function useExport(filters: MaybeRefOrGetter<ImageFilters>) {
  return useMutation({
    mutationFn: async (format: ExportFormat): Promise<ExportResult> => {
      const tab = typeof window.open === 'function' ? window.open('', '_blank') : null;

      try {
        const link = await apiRequest('/exports', {
          method: 'POST',
          body: { format, ...compact(toValue(filters)) },
          schema: ExportLinkSchema,
        });

        if (tab && !tab.closed) {
          tab.opener = null;
          tab.location.href = link.url;

          return { link, opened: true };
        }

        return { link, opened: false };
      } catch (error) {
        tab?.close();
        throw error;
      }
    },
  });
}
