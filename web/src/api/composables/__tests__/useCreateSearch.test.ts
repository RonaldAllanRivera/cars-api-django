import { describe, expect, it } from 'vitest';

import { mockApi } from '@/test/http';

import searchCreate from '../../__fixtures__/search-create.json';
import validationError from '../../__fixtures__/validation-error.json';
import { ApiValidationError } from '../../client';
import { createSearch } from '../useSearches';

const input = { make: 'Honda', model: 'CR-V', from_year: 1997, to_year: 1997, images_per_year: 2 };

describe('createSearch', () => {
  it.each([
    [201, 'created'],
    [200, 'existing'],
  ])('maps %i to %s', async (status, outcome) => {
    mockApi({ 'POST /searches': { status, body: searchCreate } });

    const result = await createSearch(input);

    expect(result.outcome).toBe(outcome);
    expect(result.search.id).toBe(3);
  });

  it('treats a 503 as a blocked run that still has a row, with the wait', async () => {
    mockApi({
      'POST /searches': {
        status: 503,
        body: { ...searchCreate, message: 'Wikimedia is rate-limiting this server.', retry_after_seconds: 120 },
      },
    });

    const result = await createSearch(input);

    expect(result).toMatchObject({
      outcome: 'blocked',
      message: 'Wikimedia is rate-limiting this server.',
      retryAfterSeconds: 120,
    });
  });

  it('treats a 502 as a failed run with the reason', async () => {
    mockApi({ 'POST /searches': { status: 502, body: { ...searchCreate, message: 'Commons did not answer.' } } });

    const result = await createSearch(input);

    expect(result).toMatchObject({ outcome: 'failed', message: 'Commons did not answer.' });
  });

  it('throws a 422 for the form to show', async () => {
    mockApi({ 'POST /searches': { status: 422, body: validationError } });

    await expect(createSearch(input)).rejects.toBeInstanceOf(ApiValidationError);
  });
});
