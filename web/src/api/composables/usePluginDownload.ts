import { useMutation } from '@tanstack/vue-query';

import { apiRequest } from '../client';
import { PluginDownloadLinkSchema } from '../schemas';
import type { PluginDownloadLink } from '../schemas';

export interface PluginDownloadResult {
  link: PluginDownloadLink;
  /** False when the browser blocked the new tab; the caller offers the link instead. */
  opened: boolean;
}

/**
 * Mints a signed, single-use link to the WordPress plugin zip and hands it to a
 * new tab. The browser follows it without the bearer token, so the signature is
 * the credential. As with exports, the tab is opened inside the click, before
 * the request, because browsers only allow window.open there.
 */
export function usePluginDownload() {
  return useMutation({
    mutationFn: async (): Promise<PluginDownloadResult> => {
      const tab = typeof window.open === 'function' ? window.open('', '_blank') : null;

      try {
        const link = await apiRequest('/wordpress-plugin/download-link', {
          method: 'POST',
          schema: PluginDownloadLinkSchema,
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
