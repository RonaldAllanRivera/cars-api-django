import { useMutation, useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';

import { apiRequestRaw } from '../client';
import { queryKeys } from '../queryKeys';
import { SearchSchema } from '../schemas';
import type { Search } from '../schemas';

/**
 * Mirrors config/cars-images.php. The form enforces these before the round
 * trip so the user sees the limit rather than a 422.
 */
export const MAX_YEAR_SPAN = 3;
export const MAX_IMAGES_PER_YEAR = 5;

export interface CreateSearchInput {
  make: string;
  model?: string;
  from_year: number;
  to_year: number;
  color?: string;
  transmission?: string;
  transparent_background?: boolean;
  images_per_year?: number;
}

export type CreateSearchOutcome = 'created' | 'existing' | 'blocked' | 'failed';

export interface CreateSearchResult {
  search: Search;
  outcome: CreateSearchOutcome;
  message?: string;
  retryAfterSeconds?: number;
}

const envelope = z.object({
  data: SearchSchema,
  message: z.string().optional(),
  retry_after_seconds: z.number().int().optional(),
});

const OUTCOMES: Record<number, CreateSearchOutcome> = {
  201: 'created',
  200: 'existing',
  503: 'blocked',
  502: 'failed',
};

export function useCreateSearch() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (input: CreateSearchInput): Promise<CreateSearchResult> => {
      const { status, body } = await apiRequestRaw('/searches', {
        method: 'POST',
        body: input,
        // 422 and 429 are NOT listed: a rejected cap or a throttle is a real
        // error the form must surface, not an outcome to render.
        acceptStatuses: [503, 502],
      });

      const parsed = envelope.parse(body);

      return {
        search: parsed.data,
        outcome: OUTCOMES[status] ?? 'failed',
        message: parsed.message,
        retryAfterSeconds: parsed.retry_after_seconds,
      };
    },
    onSuccess: () => {
      // A new run changes both the run list and the health counters.
      void queryClient.invalidateQueries({ queryKey: ['searches'] });
      void queryClient.invalidateQueries({ queryKey: queryKeys.health() });
    },
  });
}
