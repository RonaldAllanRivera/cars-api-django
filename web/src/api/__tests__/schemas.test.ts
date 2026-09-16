import { describe, expect, it } from 'vitest';
import type { z } from 'zod';

import errors from '../__fixtures__/errors.json';
import health from '../__fixtures__/health.json';
import image from '../__fixtures__/image.json';
import images from '../__fixtures__/images.json';
import csvImport from '../__fixtures__/import.json';
import imports from '../__fixtures__/imports.json';
import login from '../__fixtures__/login.json';
import me from '../__fixtures__/me.json';
import review from '../__fixtures__/review.json';
import searchCreate from '../__fixtures__/search-create.json';
import search from '../__fixtures__/search.json';
import searches from '../__fixtures__/searches.json';
import validationError from '../__fixtures__/validation-error.json';
import {
  cursorPage,
  ErrorEventSchema,
  HealthSummarySchema,
  ImageSchema,
  ImportSchema,
  LoginResponseSchema,
  RunChunkResponseSchema,
  SearchSchema,
  single,
  UserSchema,
  ValidationErrorSchema,
} from '../schemas';

/*
 * The fixtures are shared with the mobile client and the backend's contract
 * tests. If one of these fails, the server and this client disagree about the
 * shape of a response - fix the side that drifted, not the fixture.
 */
const cases: [string, unknown, z.ZodType][] = [
  ['errors.json', errors, cursorPage(ErrorEventSchema)],
  ['health.json', health, single(HealthSummarySchema)],
  ['image.json', image, single(ImageSchema)],
  ['images.json', images, cursorPage(ImageSchema)],
  ['import.json', csvImport, single(ImportSchema)],
  ['imports.json', imports, cursorPage(ImportSchema)],
  ['login.json', login, LoginResponseSchema],
  ['me.json', me, single(UserSchema)],
  ['review.json', review, single(ImageSchema)],
  ['search-create.json', searchCreate, single(SearchSchema)],
  ['search.json', search, single(SearchSchema)],
  ['searches.json', searches, cursorPage(SearchSchema)],
  ['validation-error.json', validationError, ValidationErrorSchema],
];

describe('response schemas', () => {
  it.each(cases)('parse %s', (_name, fixture, schema) => {
    const result = schema.safeParse(fixture);

    expect(result.success, result.success ? '' : JSON.stringify(result.error.issues)).toBe(true);
  });

  it('covers every committed fixture', () => {
    const files = Object.keys(import.meta.glob('../__fixtures__/*.json')).map((path) => path.split('/').pop());

    expect(files.sort()).toEqual(cases.map(([name]) => name).sort());
  });

  it('keeps the coverage block on the import detail', () => {
    const parsed = single(ImportSchema).parse(csvImport);

    expect(parsed.data.coverage).toEqual({ total: 2, searched: 1, not_run: 1, failed: 0, with_images: 1, no_images: 0 });
  });

  it('treats a null verdict as unknown rather than false', () => {
    const parsed = cursorPage(ImageSchema).parse(images);

    expect(parsed.data[0]?.make_confirmed).toBeNull();
  });

  it('rejects an image with an unknown review status', () => {
    const drifted = { ...image.data, review_status: 'maybe' };

    expect(ImageSchema.safeParse(drifted).success).toBe(false);
  });

  it('parses a blocked run chunk with no retry window', () => {
    const chunk = { outcomes: [], ran_seconds: 0.4, remaining: 3, blocked: { status: 429, retry_after_seconds: null } };

    expect(RunChunkResponseSchema.parse(chunk).blocked?.retry_after_seconds).toBeNull();
  });
});

describe('a server newer than this build', () => {
  const eventFromANewerServer = {
    ...errors.data[0],
    context: 'wordpress_publish',
  };

  it('does not fail the whole error log over an unknown context', () => {
    expect(ErrorEventSchema.parse(eventFromANewerServer).context).toBe('wordpress_publish');
  });

  it('does not fail the health summary over an unknown context key', () => {
    const summary = {
      ...health.data,
      errors_by_context_last_7d: { ...health.data.errors_by_context_last_7d, ai_generation: 2 },
    };

    expect(HealthSummarySchema.parse(summary).errors_by_context_last_7d.ai_generation).toBe(2);
  });
});
