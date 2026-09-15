/**
 * Inlined by Vite at build time. There is no runtime config file to fetch, so a
 * deployed bundle cannot be pointed at the wrong backend by accident.
 */
export const API_URL: string = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(
  /\/+$/,
  '',
);

export const APP_NAME = 'Cars Images';

/** Mirrors the server's bulk-download cap. The server enforces the real value. */
export const ZIP_CAP = 100;
