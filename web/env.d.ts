/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Origin of the Cars Images API, without the /api/v1 prefix. */
  readonly VITE_API_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
