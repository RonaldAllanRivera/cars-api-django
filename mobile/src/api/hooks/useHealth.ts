import { useQuery } from '@tanstack/react-query';

import { apiRequest } from '../client';
import { queryKeys } from '../queryKeys';
import { HealthSummarySchema, single } from '../schemas';

const health = single(HealthSummarySchema);

export function useHealth() {
  return useQuery({
    queryKey: queryKeys.health(),
    queryFn: async () => (await apiRequest('/health/summary', { schema: health })).data,
    // "Is the pipeline broken now" goes stale fast.
    staleTime: 15_000,
  });
}
