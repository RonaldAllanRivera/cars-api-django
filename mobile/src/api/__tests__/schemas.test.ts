import errorsFixture from '../__fixtures__/errors.json';
import healthFixture from '../__fixtures__/health.json';
import imageFixture from '../__fixtures__/image.json';
import imagesFixture from '../__fixtures__/images.json';
import importFixture from '../__fixtures__/import.json';
import importsFixture from '../__fixtures__/imports.json';
import loginFixture from '../__fixtures__/login.json';
import meFixture from '../__fixtures__/me.json';
import reviewFixture from '../__fixtures__/review.json';
import searchFixture from '../__fixtures__/search.json';
import searchCreateFixture from '../__fixtures__/search-create.json';
import searchesFixture from '../__fixtures__/searches.json';
import validationErrorFixture from '../__fixtures__/validation-error.json';
import {
  cursorPage,
  ErrorEventSchema,
  HealthSummarySchema,
  ImageSchema,
  ImportSchema,
  RunChunkResponseSchema,
  LoginResponseSchema,
  SearchSchema,
  single,
  TokenAbilitySchema,
  UserSchema,
  ValidationErrorSchema,
} from '../schemas';

describe('the API contract', () => {
  it('parses a chunk response', () => {
    const parsed = RunChunkResponseSchema.parse({
      outcomes: [{ id: 1, make: 'Honda', model: 'Civic', from_year: 1998, outcome: 'completed' }],
      ran_seconds: 8.4,
      remaining: 21,
      blocked: null,
    });

    expect(parsed.remaining).toBe(21);
  });

  it('parses a blocked chunk', () => {
    // The block path matters most and is exercised by hand least often.
    const parsed = RunChunkResponseSchema.parse({
      outcomes: [],
      ran_seconds: 3.1,
      remaining: 21,
      blocked: { status: 429, retry_after_seconds: 600 },
    });

    expect(parsed.blocked?.retry_after_seconds).toBe(600);
  });

  it('accepts a block with no retry window', () => {
    // Wikimedia does not always send Retry-After, and the exception's field is
    // nullable - a schema that required it would fail to parse a real block.
    expect(() =>
      RunChunkResponseSchema.parse({
        outcomes: [],
        ran_seconds: 0.2,
        remaining: 5,
        blocked: { status: 403, retry_after_seconds: null },
      }),
    ).not.toThrow();
  });

  it('parses the imports list', () => {
    const parsed = cursorPage(ImportSchema).parse(importsFixture);

    expect(parsed.data[0]?.original_filename).toBeTruthy();
  });

  it('parses an import with its coverage', () => {
    const parsed = single(ImportSchema).parse(importFixture);

    // `searched` is derived server-side, not stored. A client that recomputed
    // it would drift from the panel's number.
    expect(parsed.data.coverage?.searched).toBeDefined();
  });

  it('accepts an import whose coverage is null', () => {
    // Null is what the server returns for an import with no searches; six
    // zeroes would read as a broken import rather than an empty one.
    expect(() =>
      single(ImportSchema).parse({ data: { ...importFixture.data, coverage: null } }),
    ).not.toThrow();
  });

  it('accepts every ability the API can issue, including the privileged ones', () => {
    // P2 never requests these; P3's native build does. A narrow enum here
    // would throw on a login response that is entirely valid, which is the
    // failure mode this whole sub-project exists to avoid.
    const every = [
      'search:read',
      'search:write',
      'review:write',
      'errors:read',
      'imports:read',
      'imports:write',
      'search:run',
      'exports:read',
    ];

    expect(() => TokenAbilitySchema.array().parse(every)).not.toThrow();
  });

  it('still rejects an ability the API cannot issue', () => {
    expect(() => TokenAbilitySchema.parse('users:write')).toThrow();
  });

  it('parses the unwrapped login response', () => {
    const parsed = LoginResponseSchema.parse(loginFixture);

    expect(parsed.token_type).toBe('Bearer');
    expect(parsed.abilities).toContain('review:write');
  });

  it('parses the data-wrapped single resources', () => {
    expect(single(UserSchema).parse(meFixture).data.email).toBeTruthy();
    expect(single(ImageSchema).parse(imageFixture).data.review_status).toBe('approved');
    expect(single(ImageSchema).parse(reviewFixture).data.review_status).toBe('rejected');
    expect(single(SearchSchema).parse(searchFixture).data.status).toBe('completed');
    expect(single(HealthSummarySchema).parse(healthFixture).data.errors_last_24h).toBeGreaterThanOrEqual(0);
  });

  it('parses a successful POST /searches response with its populated images array', () => {
    const created = single(SearchSchema).parse(searchCreateFixture).data;

    // This is the one response where `images` is loaded rather than absent,
    // so it is the only fixture that exercises ImageSchema nested inside a
    // populated array instead of through the `.optional()` branch alone.
    expect(created.images?.length).toBeGreaterThan(0);
    expect(created.images?.[0]?.review_status).toBe('pending');
  });

  it('parses the cursor-paginated collections', () => {
    const images = cursorPage(ImageSchema).parse(imagesFixture);

    expect(images.data.length).toBe(1);
    // per_page=1 with two images, so there is a further page.
    expect(images.meta.next_cursor).not.toBeNull();

    expect(cursorPage(SearchSchema).parse(searchesFixture).meta.next_cursor).toBeNull();
    expect(cursorPage(ErrorEventSchema).parse(errorsFixture).data[0]?.context).toBe('search_run');
  });

  it('parses a 422', () => {
    const parsed = ValidationErrorSchema.parse(validationErrorFixture);

    // The 30-year span breaks the cap, and the cap names the offending field.
    expect(parsed.errors.to_year).toBeDefined();
  });

  it('rejects a response with a field the schema does not know about being wrong', () => {
    expect(() => ImageSchema.parse({ ...imageFixture.data, review_status: 'maybe' })).toThrow();
  });
});
