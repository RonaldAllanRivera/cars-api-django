import type { z } from 'zod';

import { API_URL } from '@/config';

import { ValidationErrorSchema } from './schemas';

export type QueryParams = Record<string, string | number | boolean | null | undefined>;

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly body: unknown = undefined,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export class ApiValidationError extends ApiError {
  constructor(
    message: string,
    public readonly fieldErrors: Record<string, string[]>,
    body: unknown,
  ) {
    super(422, message, body);
    this.name = 'ApiValidationError';
  }

  /** The first message for a field, for rendering under an input. */
  first(field: string): string | undefined {
    return this.fieldErrors[field]?.[0];
  }
}

export interface ClientConfig {
  onUnauthorized: () => void;
  getToken: () => string | null;
}

let config: ClientConfig = {
  onUnauthorized: () => {},
  getToken: () => null,
};

export function configureApiClient(next: ClientConfig): void {
  config = next;
}

export function buildUrl(path: string, query?: QueryParams, base: string = API_URL): string {
  const url = new URL(`/api/v1${path}`, base);

  for (const [key, value] of Object.entries(query ?? {})) {
    // Absent is not the same as empty: the list filters are optional rules, so
    // an empty string would 422 rather than mean "no filter".
    if (value === null || value === undefined || value === '') continue;

    // String(true) is "true" - the literal the API's boolean filters accept.
    url.searchParams.set(key, String(value));
  }

  return url.toString();
}

export interface RequestOptions<T> {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE';
  body?: unknown;
  query?: QueryParams;
  schema?: z.ZodType<T>;
  signal?: AbortSignal;
}

/**
 * The one place a request is built and sent, so the auth header, URL building
 * and 204 handling cannot drift apart between the two public entry points.
 */
async function send(
  path: string,
  options: Omit<RequestOptions<unknown>, 'schema'>,
): Promise<{ response: Response; payload: unknown }> {
  const { method = 'GET', body, query, signal } = options;
  const token = config.getToken();

  const headers: Record<string, string> = { Accept: 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;

  // FormData goes out without a Content-Type: the browser writes the multipart
  // boundary itself, and a hand-written header would omit it.
  const isMultipart = typeof FormData !== 'undefined' && body instanceof FormData;
  if (body !== undefined && !isMultipart) headers['Content-Type'] = 'application/json';

  const response = await fetch(buildUrl(path, query), {
    method,
    headers,
    signal,
    body: body === undefined ? undefined : isMultipart ? (body as FormData) : JSON.stringify(body),
  });

  // A 204 has no body, so response.json() would reject.
  const payload: unknown =
    response.status === 204 ? undefined : await response.json().catch(() => undefined);

  return { response, payload };
}

export async function apiRequest<T = unknown>(
  path: string,
  options: RequestOptions<T> = {},
): Promise<T> {
  const { schema } = options;
  const { response, payload } = await send(path, options);

  if (response.status === 204) {
    return undefined as T;
  }

  if (!response.ok) {
    throw toError(response.status, payload);
  }

  if (!schema) {
    return payload as T;
  }

  const parsed = schema.safeParse(payload);

  if (!parsed.success) {
    // Drift between the server and this schema surfaces here, at the fetch,
    // naming the field - not as a crash three screens later.
    throw new ApiError(
      response.status,
      `The API response did not match the client contract for ${path}: ${parsed.error.issues
        .map((issue) => `${issue.path.join('.')} ${issue.message}`)
        .join('; ')}`,
      payload,
    );
  }

  return parsed.data;
}

/**
 * Like apiRequest, but hands back the status with the body and does not throw
 * for the listed statuses. POST /searches answers 503 and 502 with a real
 * search row: only the caller knows that is information, not a failure.
 */
export async function apiRequestRaw(
  path: string,
  options: Omit<RequestOptions<unknown>, 'schema'> & { acceptStatuses: number[] },
): Promise<{ status: number; body: unknown }> {
  const { response, payload } = await send(path, options);

  if (!response.ok && !options.acceptStatuses.includes(response.status)) {
    throw toError(response.status, payload);
  }

  return { status: response.status, body: payload };
}

function toError(status: number, payload: unknown): ApiError {
  if (status === 401) {
    // The single place a dead token signs the user out. A 403 must not: the
    // token is alive but lacks an ability.
    config.onUnauthorized();

    return new ApiError(401, 'Your session has expired. Sign in again.', payload);
  }

  if (status === 422) {
    const parsed = ValidationErrorSchema.safeParse(payload);

    if (parsed.success) {
      return new ApiValidationError(parsed.data.message, parsed.data.errors, payload);
    }
  }

  if (status === 429) {
    return new ApiError(429, 'Too many requests. Wait a moment and try again.', payload);
  }

  const message =
    typeof payload === 'object' && payload !== null && 'message' in payload
      ? String((payload as { message: unknown }).message)
      : `The request failed (${status}).`;

  return new ApiError(status, message, payload);
}

/** A readable message for any thrown value, for banners and toasts. */
export function errorMessage(error: unknown, fallback = 'Something went wrong.'): string {
  if (error instanceof Error && error.message) return error.message;

  return fallback;
}
