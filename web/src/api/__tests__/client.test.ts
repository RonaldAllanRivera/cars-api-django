import { beforeEach, describe, expect, it, vi } from 'vitest';

import { mockApi } from '@/test/http';

import me from '../__fixtures__/me.json';
import validationError from '../__fixtures__/validation-error.json';
import { ApiError, apiRequest, apiRequestRaw, ApiValidationError, buildUrl, configureApiClient } from '../client';
import { single, UserSchema } from '../schemas';

describe('buildUrl', () => {
  it('prefixes the version and joins the base', () => {
    expect(buildUrl('/images', undefined, 'https://api.example.test')).toBe('https://api.example.test/api/v1/images');
  });

  it('uses VITE_API_URL by default', () => {
    expect(buildUrl('/auth/me')).toBe('http://api.test/api/v1/auth/me');
  });

  it('omits null, undefined and empty-string params rather than sending them blank', () => {
    const url = new URL(
      buildUrl('/images', { make: 'Toyota', model: '', year: undefined, cursor: null, per_page: 24 }),
    );

    expect([...url.searchParams.keys()]).toEqual(['make', 'per_page']);
    expect(url.searchParams.get('per_page')).toBe('24');
  });

  it('sends booleans as the literals "true" and "false"', () => {
    const url = new URL(buildUrl('/images', { make_confirmed: true, year_confirmed: false }));

    expect(url.searchParams.get('make_confirmed')).toBe('true');
    expect(url.searchParams.get('year_confirmed')).toBe('false');
  });

  it('keeps false and zero, which are values, not absence', () => {
    const url = new URL(buildUrl('/images', { year_confirmed: false, csv_import_id: 0 }));

    expect(url.searchParams.has('year_confirmed')).toBe(true);
    expect(url.searchParams.get('csv_import_id')).toBe('0');
  });

  it('encodes values', () => {
    const url = buildUrl('/images', { make: 'Mercedes-Benz & Co' });

    expect(url).toContain('make=Mercedes-Benz+%26+Co');
  });
});

describe('apiRequest', () => {
  const onUnauthorized = vi.fn();
  let token: string | null = 'secret-token';

  beforeEach(() => {
    onUnauthorized.mockReset();
    token = 'secret-token';
    configureApiClient({ getToken: () => token, onUnauthorized });
  });

  it('sends Accept JSON and the bearer token', async () => {
    const api = mockApi({ 'GET /auth/me': { body: me } });

    await apiRequest('/auth/me');

    expect(api.requests[0]?.headers).toMatchObject({ Accept: 'application/json', Authorization: 'Bearer secret-token' });
  });

  it('sends no Authorization header without a token', async () => {
    token = null;
    const api = mockApi({ 'GET /auth/me': { body: me } });

    await apiRequest('/auth/me');

    expect(api.requests[0]?.headers.Authorization).toBeUndefined();
  });

  it('serialises a JSON body with a Content-Type', async () => {
    const api = mockApi({ 'PATCH /images/2/review': { body: {} } });

    await apiRequest('/images/2/review', { method: 'PATCH', body: { review_status: 'approved' } });

    expect(api.requests[0]?.headers['Content-Type']).toBe('application/json');
    expect(api.requests[0]?.body).toEqual({ review_status: 'approved' });
  });

  it('leaves multipart Content-Type to the browser so the boundary is written', async () => {
    const api = mockApi({ 'POST /imports': { status: 201, body: {} } });
    const form = new FormData();
    form.append('csv_file', new Blob(['Make,Model,Year']), 'queries.csv');

    await apiRequest('/imports', { method: 'POST', body: form });

    expect(api.requests[0]?.headers['Content-Type']).toBeUndefined();
    expect(api.requests[0]?.body).toBeInstanceOf(FormData);
  });

  it('returns the parsed body when a schema is given', async () => {
    mockApi({ 'GET /auth/me': { body: me } });

    const result = await apiRequest('/auth/me', { schema: single(UserSchema) });

    expect(result.data.email).toBe('fixtures@example.test');
  });

  it('resolves a 204 to undefined without reading a body', async () => {
    mockApi({ 'POST /auth/logout': { status: 204 } });

    await expect(apiRequest('/auth/logout', { method: 'POST' })).resolves.toBeUndefined();
  });

  it('signs out on a 401 and says why', async () => {
    mockApi({ 'GET /auth/me': { status: 401, body: { message: 'Unauthenticated.' } } });

    const error = await apiRequest('/auth/me').catch((caught: unknown) => caught);

    expect(onUnauthorized).toHaveBeenCalledTimes(1);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(401);
    expect((error as ApiError).message).toMatch(/session has expired/i);
  });

  it('does not sign out on a 403 - the token is alive, it lacks an ability', async () => {
    mockApi({ 'GET /imports': { status: 403, body: { message: 'Invalid ability provided.' } } });

    const error = await apiRequest('/imports').catch((caught: unknown) => caught);

    expect(onUnauthorized).not.toHaveBeenCalled();
    expect((error as ApiError).message).toBe('Invalid ability provided.');
  });

  it('turns a 422 into an ApiValidationError with field errors', async () => {
    mockApi({ 'POST /searches': { status: 422, body: validationError } });

    const error = await apiRequest('/searches', { method: 'POST', body: {} }).catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(ApiValidationError);
    expect((error as ApiValidationError).message).toBe(validationError.message);
    expect((error as ApiValidationError).first('to_year')).toBe(validationError.errors.to_year[0]);
    expect((error as ApiValidationError).first('make')).toBeUndefined();
  });

  it('gives a 429 a message a person can act on', async () => {
    mockApi({ 'GET /images': { status: 429, body: { message: 'Too Many Attempts.' } } });

    await expect(apiRequest('/images')).rejects.toThrow('Too many requests. Wait a moment and try again.');
  });

  it("uses the server's message for other errors", async () => {
    mockApi({ 'GET /images/9': { status: 404, body: { message: 'Image not found.' } } });

    await expect(apiRequest('/images/9')).rejects.toMatchObject({ status: 404, message: 'Image not found.' });
  });

  it('falls back to the status when there is no message', async () => {
    mockApi({ 'GET /health/summary': () => ({ status: 500, body: undefined }) });

    await expect(apiRequest('/health/summary')).rejects.toThrow('The request failed (500).');
  });

  it('names the drifted field when a response breaks the contract', async () => {
    mockApi({ 'GET /auth/me': { body: { data: { id: 'one', name: 'A', email: 'a@b.c' } } } });

    await expect(apiRequest('/auth/me', { schema: single(UserSchema) })).rejects.toThrow(/data\.id/);
  });
});

describe('apiRequestRaw', () => {
  beforeEach(() => configureApiClient({ getToken: () => 't', onUnauthorized: vi.fn() }));

  it('hands back accepted error statuses with their body', async () => {
    mockApi({ 'POST /searches': { status: 503, body: { message: 'Blocked', data: {} } } });

    const result = await apiRequestRaw('/searches', { method: 'POST', body: {}, acceptStatuses: [503] });

    expect(result).toEqual({ status: 503, body: { message: 'Blocked', data: {} } });
  });

  it('still throws for statuses it was not told to accept', async () => {
    mockApi({ 'POST /searches': { status: 422, body: validationError } });

    await expect(apiRequestRaw('/searches', { method: 'POST', body: {}, acceptStatuses: [503] })).rejects.toBeInstanceOf(
      ApiValidationError,
    );
  });
});
