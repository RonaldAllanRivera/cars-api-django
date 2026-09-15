import { useMutation, useQueryClient } from '@tanstack/react-query';

import { apiRequest } from '../client';
import { queryKeys } from '../queryKeys';
import { ImportSchema, single } from '../schemas';

export interface PickedCsv {
  uri: string;
  name: string;
  mimeType?: string;
}

const oneImport = single(ImportSchema);

/**
 * Uploads a CSV as multipart.
 *
 * The file is described by uri/name/type rather than read into memory: on
 * native there is no File object to hand to FormData, and React Native's
 * fetch understands this shape and streams from the uri.
 */
export function useUploadImport() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (file: PickedCsv) => {
      const form = new FormData();

      // The cast is unavoidable: RN's FormData accepts this object shape at
      // runtime, but the DOM lib's type only admits string | Blob.
      form.append('csv_file', {
        uri: file.uri,
        name: file.name,
        type: file.mimeType ?? 'text/csv',
      } as unknown as Blob);

      return (await apiRequest('/imports', { method: 'POST', body: form, schema: oneImport })).data;
    },
    // The list gains a row and every coverage count behind it is now stale.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.imports() }),
  });
}
