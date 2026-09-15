# Cars Images — web client

The browser counterpart of [`mobile/`](../mobile): a Vue 3 app for searching Wikimedia Commons for car
photos, running CSV imports in paced batches, reviewing what came back and exporting the approved set.
It talks to the same `/api/v1` JSON API and validates every response with the same Zod schemas and
shared fixtures.

**Stack:** Vite, Vue 3 (`<script setup>`, TypeScript strict), Vue Router, TanStack Query, Zod,
Tailwind CSS v4, Vitest + Vue Test Utils.

## Setup

```bash
cd web
cp .env.example .env    # point VITE_API_URL at the API
npm ci
npm run dev             # http://localhost:5173
```

Node 22 or newer. The API must allow the dev origin in its CORS settings.

## Scripts

| Script | What it does |
| --- | --- |
| `npm run dev` | Dev server with hot reload |
| `npm run build` | Type-checks (`vue-tsc -b`), then builds to `dist/` |
| `npm run preview` | Serves the production build locally |
| `npm run typecheck` | Type-checks the app, tests and config |
| `npm run test` | Runs the Vitest suite once (jsdom, fetch mocked) |
| `npm run lint` | ESLint (flat config, `eslint-plugin-vue`, `typescript-eslint`) |

## Environment

| Variable | Default | Notes |
| --- | --- | --- |
| `VITE_API_URL` | `http://localhost:8000` | API origin, without `/api/v1`. Inlined at build time. |

## Layout

```
src/
  api/          client.ts (fetch wrapper), schemas.ts (Zod), queryKeys.ts, composables/ (queries, mutations, bulk run)
  auth/         token store (localStorage `cars-images.token`) and session state
  components/   shell, form controls, cards, run progress, coverage, export panel
  pages/        search, library, pipeline, review, health, login
  format/       titles, labels, times
  test/         fetch mock and mount helpers
```

## Deploy

`netlify.toml` builds with `npm run build`, publishes `dist`, rewrites every path to `index.html` for
the router, and sets security headers (a CSP that allows images from Wikimedia and API calls to any
HTTPS origin). Set the Netlify base directory to `web` and `VITE_API_URL` in the site's environment.
