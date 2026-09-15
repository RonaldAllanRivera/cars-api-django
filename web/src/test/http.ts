import { vi } from 'vitest';

export interface RecordedRequest {
  method: string;
  url: URL;
  path: string;
  headers: Record<string, string>;
  body: unknown;
}

type Reply = { status?: number; body?: unknown } | ((request: RecordedRequest) => { status?: number; body?: unknown } | Promise<{ status?: number; body?: unknown }>);

/**
 * A fetch stand-in keyed by "METHOD /path" (the part after /api/v1, no query).
 * Unmatched requests fail loudly with a 599 so a test never passes by accident
 * against a route it did not mean to hit.
 */
export function mockApi(routes: Record<string, Reply>) {
  const requests: RecordedRequest[] = [];

  const fetchMock = vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = new URL(typeof input === 'string' ? input : input instanceof URL ? input.href : input.url);
    const method = (init.method ?? 'GET').toUpperCase();
    const path = url.pathname.replace(/^\/api\/v1/, '');
    const headers = Object.fromEntries(Object.entries((init.headers ?? {}) as Record<string, string>));
    const body =
      typeof init.body === 'string' ? JSON.parse(init.body) : init.body instanceof FormData ? init.body : undefined;

    const request: RecordedRequest = { method, url, path, headers, body };
    requests.push(request);

    const reply = routes[`${method} ${path}`];
    if (!reply) {
      return jsonResponse(599, { message: `No mock for ${method} ${path}` });
    }

    const { status = 200, body: payload } = typeof reply === 'function' ? await reply(request) : reply;

    return status === 204 ? new Response(null, { status }) : jsonResponse(status, payload);
  });

  vi.stubGlobal('fetch', fetchMock);

  return { fetchMock, requests, calls: (key: string) => requests.filter((r) => `${r.method} ${r.path}` === key) };
}

export function jsonResponse(status: number, body: unknown): Response {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

/** Resolves once pending promises and a macrotask have run. */
export const flush = () => new Promise((resolve) => setTimeout(resolve, 0));
