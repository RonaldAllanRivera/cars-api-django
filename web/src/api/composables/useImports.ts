import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/vue-query';
import { computed, toValue } from 'vue';
import type { MaybeRefOrGetter } from 'vue';

import { apiRequest } from '../client';
import { queryKeys } from '../queryKeys';
import { cursorPage, ImportSchema, single } from '../schemas';

const importPage = cursorPage(ImportSchema);
const oneImport = single(ImportSchema);

export function useImports(enabled: MaybeRefOrGetter<boolean> = true) {
  return useInfiniteQuery({
    queryKey: queryKeys.imports(),
    enabled: computed(() => toValue(enabled)),
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) =>
      apiRequest('/imports', { query: { cursor: pageParam }, schema: importPage, signal }),
    getNextPageParam: (lastPage) => lastPage.meta.next_cursor,
  });
}

/** Only the detail endpoint carries coverage; the list deliberately omits it. */
export function useImport(id: MaybeRefOrGetter<number>) {
  return useQuery({
    queryKey: computed(() => queryKeys.import(toValue(id))),
    queryFn: async ({ queryKey, signal }) =>
      (await apiRequest(`/imports/${queryKey[1]}`, { schema: oneImport, signal })).data,
  });
}

export function useUploadImport() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append('csv_file', file, file.name);

      return (await apiRequest('/imports', { method: 'POST', body: form, schema: oneImport })).data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.imports() }),
  });
}
