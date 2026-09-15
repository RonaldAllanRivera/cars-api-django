import { useQuery } from '@tanstack/react-query';

import { apiRequest } from '../client';
import type { ImageFilters } from '../queryKeys';
import { queryKeys } from '../queryKeys';
import { ImageCountSchema } from '../schemas';

/**
 * How many images match the filters.
 *
 * Its own request because the grid cannot say: GET /images is cursor-paginated
 * and cursor pagination computes no total. Advisory only - it labels the export
 * button, and the server recounts at mint and again at download.
 */
export function useImageCount(filters: ImageFilters = {}, { enabled = true }: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: queryKeys.imageCount(filters),
    // A hook cannot be called conditionally, so a screen that only sometimes
    // needs the count disables the request rather than skipping the call.
    enabled,
    queryFn: async () =>
      (await apiRequest('/images/count', { query: { ...filters }, schema: ImageCountSchema })).count,
  });
}
