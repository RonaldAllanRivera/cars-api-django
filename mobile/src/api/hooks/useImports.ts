import { useInfiniteQuery, useQuery } from '@tanstack/react-query';

import { apiRequest } from '../client';
import { queryKeys } from '../queryKeys';
import { cursorPage, ImportSchema, single } from '../schemas';

const importPage = cursorPage(ImportSchema);
const oneImport = single(ImportSchema);

export function useImports() {
  return useInfiniteQuery({
    queryKey: queryKeys.imports(),
    initialPageParam: null as string | null,
    queryFn: ({ pageParam }) =>
      apiRequest('/imports', {
        query: { cursor: pageParam ?? undefined },
        schema: importPage,
      }),
    getNextPageParam: (lastPage) => lastPage.meta.next_cursor,
  });
}

/** Only this endpoint carries coverage; the list deliberately omits it. */
export function useImport(id: number) {
  return useQuery({
    queryKey: queryKeys.import(id),
    queryFn: async () => (await apiRequest(`/imports/${id}`, { schema: oneImport })).data,
  });
}
