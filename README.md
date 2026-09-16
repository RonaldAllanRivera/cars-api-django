# Cars Images API — Django

A **Django + Django REST Framework** platform that searches, filters, reviews, and bulk-exports car photography from **Wikimedia Commons** — one vehicle at a time, or thousands of rows from a CSV — then has **Claude** write illustrated, SEO-ready **WordPress draft posts** from the approved images under a hard AI spend cap. A **Vue 3** web client and a **React Native (Expo)** mobile client share the same versioned `/api/v1` JSON API.

[![Backend CI](https://github.com/RonaldAllanRivera/cars-api-django/actions/workflows/backend.yml/badge.svg)](https://github.com/RonaldAllanRivera/cars-api-django/actions/workflows/backend.yml)
[![Web CI](https://github.com/RonaldAllanRivera/cars-api-django/actions/workflows/web.yml/badge.svg)](https://github.com/RonaldAllanRivera/cars-api-django/actions/workflows/web.yml)
[![Mobile CI](https://github.com/RonaldAllanRivera/cars-api-django/actions/workflows/mobile.yml/badge.svg)](https://github.com/RonaldAllanRivera/cars-api-django/actions/workflows/mobile.yml)

![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-5.2%20LTS-092E20?logo=django&logoColor=white)
![DRF](https://img.shields.io/badge/DRF-3.18-A30000)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17-4169E1?logo=postgresql&logoColor=white)
![Vue](https://img.shields.io/badge/Vue-3-4FC08D?logo=vuedotjs&logoColor=white)
![React Native](https://img.shields.io/badge/React%20Native-0.86-61DAFB?logo=react&logoColor=black)
![Expo](https://img.shields.io/badge/Expo-SDK%2057-000020?logo=expo&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![Claude API](https://img.shields.io/badge/Claude%20API-Haiku%204.5-D97757?logo=anthropic&logoColor=white)
![WordPress](https://img.shields.io/badge/WordPress-REST%20API-21759B?logo=wordpress&logoColor=white)

> **Status:** feature-complete, deployed on free tiers. Changes are tracked in [CHANGELOG.md](CHANGELOG.md).
>
> **Live demo**
>
> | App | URL |
> |---|---|
> | Vue web client | <https://cars-images-django-web.netlify.app> |
> | Expo client (web build) | <https://cars-images-django-mobile.netlify.app> |
> | Django API · admin | <https://cars-images-api.onrender.com/api/v1> · <https://cars-images-api.onrender.com/admin/> |
>
> The API runs on a free instance, so the first request after it has been idle can take about a minute.

## Highlights

- **Two apps, one contract.** Vue 3 and Expo clients on a single versioned API, plus a Django admin; shared JSON fixtures fail the build on contract drift in either direction.
- **An LLM feature built like a payments feature.** Every Claude call reserves its worst-case cost under a PostgreSQL row lock before it is sent, so concurrent requests cannot overspend the monthly cap, a crash over-reports rather than under-reports, and no failure path pays for the same article twice.
- **Retries chosen by what a failure proves.** A refused connection is retried; a timed-out response that may already have been billed is not; a WordPress create that may have succeeded is recovered by slug instead of duplicated.
- **Untrusted input treated as untrusted.** Commons text never enters the model's instructions, is escaped into HTML, and API keys are kept out of error logs and Django error reports.
- **Long jobs without a worker.** Time-boxed, resumable chunks on a 512 MB free instance, where the database rows are the run state.
- **Over 1,000 automated tests** across backend, web and mobile, with HTTP to Wikimedia, Claude and WordPress faked, so the suite spends no tokens and touches no live site.

---

## Contents

- [Highlights](#highlights)
- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [JSON API](#json-api)
- [Clients](#clients)
- [Engineering decisions](#engineering-decisions)
- [Tech stack](#tech-stack)
- [Getting started](#getting-started)
- [Configuration](#configuration)
- [Testing](#testing)
- [Deployment](#deployment)
- [Project structure](#project-structure)
- [Milestones](#milestones)
- [Roadmap](#roadmap)

---

## Overview

Sourcing usable photos for a large vehicle catalogue is tedious: every make/model/year needs its own search, Wikimedia's full-text index is inconsistent, results are often mis-filed or not cars at all, and the originals are far too large to ship to a website.

This platform turns that into a reviewable pipeline:

1. **Import** a vehicle list (CSV) or run a single ad-hoc search.
2. **Harvest** images from Wikimedia Commons at a rate the API accepts.
3. **Review** what came back — off-target results are flagged, never silently trusted.
4. **Export** the approved set as a web-optimised ZIP plus a matching CSV manifest.
5. **Publish** one Claude-written, illustrated draft post per vehicle to WordPress, for an editor to review.

Every stage is inspectable from the Django admin, the Vue web client, or the Expo mobile app.

The API is built to a versioned JSON contract that both clients hold to. The Expo client validates every response with Zod, and a single set of shared JSON fixtures keeps the backend and the clients honest — drift in either direction fails the contract test rather than surfacing as a crash in the app.

---

## Architecture

```mermaid
flowchart LR
    subgraph Clients
        WEB["Vue 3 web client<br/>Vite · TanStack Query · Zod"]
        MOB["Expo / React Native<br/>iOS · Android · Web"]
        ADM["Django admin<br/>makes · users · error log"]
    end

    subgraph API["Django + DRF  —  /api/v1"]
        AUTH["Scoped bearer tokens"]
        VIEWS["ViewSets · Serializers<br/>cursor pagination · 422 errors"]
    end

    subgraph Domain["Domain services"]
        SRCH["Search runner<br/>multi-year orchestration"]
        WMC["Wikimedia client<br/>retry · cache · block detection"]
        MATCH["Category resolver<br/>year + make matching"]
        CSV["CSV importer<br/>dedupe · caps · coverage"]
        EXP["ZIP / CSV exporters<br/>Pillow resize · signed links"]
        OBS["Error-event logger<br/>health summary"]
        PUB["Publisher<br/>resumable chunks · spend cap"]
    end

    DB[("PostgreSQL")]
    WM(["Wikimedia Commons"])
    CL(["Claude API"])
    WP(["WordPress<br/>REST API"])

    WEB --> AUTH
    MOB --> AUTH
    AUTH --> VIEWS
    ADM --> DB
    VIEWS --> SRCH & CSV & EXP & OBS & PUB
    ADM --> PUB
    SRCH --> MATCH --> WMC --> WM
    EXP --> WM
    PUB --> CL & WP & WM
    SRCH & CSV & EXP & OBS & PUB --> DB
```

### How a post is published

Each stage is saved before the next can fail, so a run that dies anywhere resumes without paying for the text again or creating a second post.

```mermaid
sequenceDiagram
    autonumber
    participant R as Publishing run
    participant DB as PostgreSQL
    participant C as Claude API
    participant WP as WordPress

    R->>DB: Reserve worst-case cost (row lock, refuse over cap)
    R->>C: Facts as data, static instructions, strict JSON schema
    C-->>R: Title, article, SEO fields, token usage
    R->>DB: Settle real cost, save article (status: generated)
    R->>WP: Upload approved images with Commons credits
    R->>DB: Record each attachment (the upload ledger)
    R->>WP: Create draft (or update in place, status untouched)
    R->>DB: Save WordPress id first, then mark published
```

---

## Features

### Search
- Search by **make, model, year range, colour, and transmission**, fetched **one year at a time**.
- **Commons category resolution** — model names are normalised (engine sizes and drivetrain qualifiers like `AWD`, `xDrive`, `Hatchback` stripped) and tried longest-first; hits are cached permanently, misses expire.
- **Exact-year filtering** — an image is kept only when its title names that model year next to the make; photo dates and year ranges are ignored.
- **Make confirmation** — each image is flagged *Confirmed* or *Not confirmed* from its title, description, and categories.
- **Deduplication** — an identical completed search is reused instead of hitting Wikimedia again.

### CSV pipeline
- Upload a `Make, Model, Year[, Transmission]` CSV; rows are validated, deduplicated, and turned into queued searches.
- Guard rails on **unique query count** and **projected image count**, not just file size.
- **Coverage report** per import: total, searched, not run, failed, with images, no images.
- **Chunked bulk runs** with pause/resume, progress, and automatic stop when Wikimedia rate-limits.

### Review & export
- Human review workflow: `pending → approved / rejected`, recording reviewer and time.
- **ZIP export** of up to 100 images, resized to 1600 px JPEG; filenames like `2021 Toyota Corolla 2.jpg`.
- **CSV manifest** whose filenames match the ZIP entries exactly.
- Exports are delivered through **short-lived, single-use signed links**.

### Observability
- Structured **error-event log** (CSV upload, CSV row, search run, image download, Wikimedia block, AI generation, AI budget, WordPress publish, WordPress media) with size-clamped messages and a per-import cap.
- **Health summary**: searches by status, errors in 24 h, errors by context over 7 days, images collected.
- **Admin dashboard** — health stats with a 7-day sparkline, failures by kind (14 days), search throughput
  (30 days) and the ten latest failures, drawn as inline SVG with no charting library.
- `prune_error_events` management command with configurable retention.

### AI blog publishing
Turns reviewed images into WordPress **draft** posts written by Claude (`claude-haiku-4-5`, the cheapest current model, by default).
- **One post per make, model and year**, illustrated only with approved images: the first is the featured image, the rest an editable Gutenberg gallery, and every image is credited with its Commons title, author and licence.
- **SEO-ready** — title, meta description and keywords, derived when the model leaves one empty, and copied to Yoast SEO or Rank Math by the **Cars Images Publisher** WordPress plugin, which lives in this repo and prints the tags itself when neither SEO plugin is installed.
- **One-click plugin install** — staff download the plugin zip from the web app (**Pipeline → WordPress plugin**) through a signed, single-use link; the zip is built from the source in this deploy, so it always matches the API.
- **Drafts only** — a person publishes. An update never changes the status an editor chose, so a live post stays live.
- **Bounded spend** — a hard monthly cap checked before every call, a daily limit on new posts, at most three paid attempts per post, and per-model pricing so switching `ANTHROPIC_MODEL` reprices the budget.
- **No invented figures** — the prompt forbids any price, mileage or performance figure the pipeline did not supply; any the model quotes anyway are flagged in the error log for the reviewer.
- **Visible cost** — every call's tokens and dollar cost are recorded, with month-to-date spend on the admin dashboard and at `GET /blog-posts/budget`.
- Run it from the admin (**Blog posts → Write and publish selected**), the API (`POST /blog-posts/run-chunk`) or `manage.py publish_blog_posts --seed`.

---

## JSON API

All endpoints live under `/api/v1`, require `Authorization: Bearer <token>` (except login), and return JSON.

| Method | Path | Ability | Purpose |
|---|---|---|---|
| `POST` | `/auth/login` | — | Issue a scoped token (5/min) |
| `POST` | `/auth/logout` | any | Revoke the current token |
| `GET` | `/auth/me` | any | Current user |
| `GET` | `/images` | `search:read` | Filterable, cursor-paginated image list |
| `GET` | `/images/count` | `search:read` | Count for the same filters |
| `GET` | `/images/{id}` | `search:read` | Image detail |
| `PATCH` | `/images/{id}/review` | `review:write` | Approve / reject / reset |
| `GET` | `/searches` | `search:read` | Filter by status, source, import, coverage |
| `GET` | `/searches/{id}` | `search:read` | Search detail |
| `GET` | `/searches/{id}/images` | `search:read` | Images for a search |
| `POST` | `/searches` | `search:write` | Run an ad-hoc search (10/min) |
| `POST` | `/searches/run-chunk` | `search:run` | Run the next chunk of a CSV import |
| `GET` | `/imports` | `imports:read` | CSV imports |
| `GET` | `/imports/{id}` | `imports:read` | Import detail with coverage |
| `POST` | `/imports` | `imports:write` | Upload a CSV |
| `POST` | `/exports` | `exports:read` | Create a signed ZIP/CSV download link |
| `GET` | `/health/summary` | `errors:read` | Pipeline health |
| `GET` | `/errors` | `errors:read` | Error-event log |
| `GET` | `/blog-posts` | `blog:read` | AI-written posts; filter by status, make, year, import |
| `GET` | `/blog-posts/{id}` | `blog:read` | Post detail with article, SEO and media |
| `GET` | `/blog-posts/budget` | `blog:read` | This month's AI spend against the cap |
| `POST` | `/blog-posts/sync` | `blog:write` | Queue a post per vehicle with approved images (spends nothing) |
| `POST` | `/blog-posts/run-chunk` | `blog:publish` | Write and publish the next chunk as drafts (spends AI budget, 6/min) |
| `POST` | `/wordpress-plugin/download-link` | `blog:write` + staff | Signed, single-use link to the WordPress plugin zip |

### Contract

- **Single resources** are wrapped: `{ "data": { ... } }`.
- **Lists** use cursor pagination:
  ```json
  {
    "data": [],
    "links": { "first": null, "last": null, "prev": null, "next": "…" },
    "meta": { "path": "…", "per_page": 24, "next_cursor": "…", "prev_cursor": null }
  }
  ```
- **Validation errors** return `422` with `{ "message": "…", "errors": { "field": ["…"] } }`.
- **`POST /searches`** status codes carry meaning: `201` created, `200` reused, `503` Wikimedia blocked (with `Retry-After`), `502` upstream failure — each still returns the search in `data`.

---

## Clients

### Vue 3 web client — `web/`
Search, run history, image library with filters, review queue, CSV pipeline with live bulk-run progress, and a health dashboard. The API layer mirrors the mobile client: one typed `fetch` wrapper, Zod schemas for every response, TanStack Query for caching and optimistic review updates.

### React Native / Expo client — `mobile/`
Five tabs — **Search, Library, Pipeline, Review, Health** — on iOS, Android, and web.

- Tokens stored in **SecureStore** on native, `localStorage` on web.
- Every response validated with **Zod**; a contract drift fails loudly, not silently.
- **Optimistic review** — the card leaves the queue instantly and rolls back on failure.
- Bulk runs keep the screen awake and stop cleanly when rate-limited.

Point it at this backend with a single variable:

```bash
EXPO_PUBLIC_API_URL=http://localhost:8000
```

---

## Engineering decisions

**Drop-in API compatibility.** DRF defaults differ from what the mobile client expects (`Token` vs `Bearer`, `400` vs `422`, `{next, results}` vs `{data, meta}`). Three small, tested extension points — a bearer authentication class, a cursor pagination class, and an exception handler — close the gap, so no client code changes.

**Scoped tokens, hashed at rest.** API tokens store only a SHA-256 hash and a list of abilities. A DRF permission class checks the ability each view declares; a missing ability is `403`, an invalid token is `401`. The `blog:*` abilities, which spend AI budget, are granted at login only to staff accounts, and the plugin download also checks staff status itself, so a token alone is never enough.

**Polite Wikimedia usage.** A real `User-Agent`, `maxlag`, response caching, a pause between queries, and exponential back-off on transient errors. `429`/`403`/`503` are never retried — they are recorded as block events and stop the bulk run immediately.

**Local image resizing.** Wikimedia's thumbnail CDN rejects many datacenter IPs, so originals are downloaded and resized with **Pillow** (1600 px, JPEG q82, transparency flattened) — roughly 85 % smaller.

**No worker required.** Searches, chunks, and ZIPs run inside the request with hard caps (queries per chunk, seconds per chunk, images per ZIP). Clients drive long jobs by calling `run-chunk` repeatedly, which keeps hosting free and failure modes visible. The domain services are framework-agnostic, so moving them to Celery is a wiring change.

**Explicit failures.** A failed image download is skipped and logged; a ZIP where every download failed is reported, never served empty; a search refresh runs in one database transaction.

**Forward-compatible error contexts.** New kinds of failure are added server-side before the clients ship an update. The health summary reports a fixed set of context keys, and both clients accept a context they have never seen and label it readably, so a new failure type cannot break a deployed app.

**Spend enforced before the call, not tallied after.** Each Claude call first reserves its worst-case cost under a `SELECT … FOR UPDATE` on the month's budget row, then calls the API outside the lock and settles to the real cost. The estimate is a true upper bound — the request's UTF-8 byte length (a token covers at least one byte) plus the full `max_tokens` allowance — so the cap holds even if every article comes back at maximum length. A two-thread test against real PostgreSQL locks proves two concurrent calls cannot both squeeze under it.

**Retries follow what a failure proves.** A refused connection never reached the API, so it is retried. A server error or overload was not billed, so it is retried with back-off. A read timeout, dropped connection or gateway timeout may hide a generation that was billed, so it is **not** retried and keeps its worst-case charge; the SDK's own automatic retries are switched off for exactly that reason. WordPress writes follow the same rule: a create that may have succeeded is found by its slug on the next run instead of being posted twice.

**Resumable without a queue.** The generated article is a durable commit point, the WordPress id is saved before anything else can fail, and each uploaded image is a ledger row. A run killed at any point resumes by being called again: it neither pays for the text twice nor creates a duplicate post or attachment.

**Untrusted text stays data.** Wikimedia titles and attributions are text anyone can edit. They reach the model only in the data message, never its instructions, so a title that reads like an instruction is not followed; the instructions are identical for every vehicle, which also keeps them cache-friendly. The same text is HTML-escaped into posts, non-`http(s)` links are dropped, and API keys are scrubbed from error logs and hidden from Django's error reports.

**Query performance.** Composite indexes on `(make, model, year)` and `(context, occurred_at)`, a unique constraint on image ownership, `select_related` / `annotate(Count(...))` to avoid N+1 queries, and cursor pagination that stays fast on deep pages.

---

## Tech stack

| Layer | Technology |
|---|---|
| API | Python 3.13, Django 5.2 LTS, Django REST Framework, django-filter |
| Data | PostgreSQL 17, Django migrations, database cache |
| Imaging / HTTP | Pillow, httpx |
| AI and publishing | Anthropic Claude API (official `anthropic` SDK, structured outputs), WordPress REST API (Application Passwords), WordPress plugin in PHP |
| Web client | Vue 3, Vite, TypeScript, Vue Router, TanStack Query, Zod, Tailwind CSS |
| Mobile client | Expo SDK 57, React Native 0.86, expo-router, TanStack Query, Zod, NativeWind |
| Quality | pytest, pytest-django, factory_boy, respx, Ruff, Vitest, Jest |
| Infrastructure | Docker Compose, GitHub Actions, Gunicorn, WhiteNoise |

---

## Getting started

### With Docker (recommended)

```bash
cp .env.example .env
docker compose up --build
docker compose exec api python manage.py createsuperuser
```

The `api` container applies migrations, creates the cache table, and seeds an empty make/model catalog on start. Set `ADMIN_EMAIL` and `ADMIN_PASSWORD` in `.env` to have the admin account created automatically instead of running `createsuperuser`.

| Service | URL |
|---|---|
| API | http://localhost:8000/api/v1 |
| Django admin | http://localhost:8000/admin |
| Vue web client | http://localhost:5173 |

### Without Docker

**Backend**
```bash
cp .env.example .env
docker compose up -d db          # PostgreSQL on localhost:5434
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements/dev.txt
python manage.py migrate
python manage.py createcachetable
python manage.py createsuperuser
python manage.py runserver
```

**Web client**
```bash
cd web
npm install
npm run dev
```

**Mobile client**
```bash
cd mobile
npm install
npx expo start
```

---

## Configuration

Settings are read from environment variables. One flat set of names is shared by local, CI and deployed runs, so the same `.env` works everywhere.

### Core

| Variable | Purpose |
|---|---|
| `APP_KEY` | Django `SECRET_KEY` |
| `APP_ENV` / `APP_DEBUG` | Environment name and debug mode |
| `APP_URL` | Public base URL (used for signed export links) |
| `DATABASE_URL` | Optional single connection URL; overrides `DB_*` |
| `DB_SSLMODE` | `require` for managed PostgreSQL (Neon) |
| `DB_HOST` · `DB_PORT` · `DB_DATABASE` · `DB_USERNAME` · `DB_PASSWORD` | PostgreSQL connection |
| `CORS_ALLOWED_ORIGINS` | Comma-separated web client origins |

### Wikimedia

| Variable | Default |
|---|---|
| `WIKIMEDIA_BASE_URL` | `https://commons.wikimedia.org/w/api.php` |
| `WIKIMEDIA_USER_AGENT` | *set a contact URL or email* |
| `WIKIMEDIA_TIMEOUT` | `10` |
| `WIKIMEDIA_RETRY_TIMES` | `3` |
| `WIKIMEDIA_RETRY_SLEEP_MS` | `200` |
| `WIKIMEDIA_CACHE_TTL` | `3600` |
| `WIKIMEDIA_MAXLAG` | `5` |
| `WIKIMEDIA_CATEGORY_MISS_TTL_DAYS` | `30` |
| `WIKIMEDIA_CATEGORY_MAX_FILES` | `500` |
| `WIKIMEDIA_CATEGORY_PAGE_SIZE` | `200` |

### Pipeline limits

| Variable | Default |
|---|---|
| `CSV_IMPORT_MAX_COMBOS` | `1000` |
| `CSV_IMPORT_DEFAULT_IMAGES_PER_YEAR` | `5` |
| `CSV_IMPORT_MAX_UPLOAD_KB` | `5120` |
| `CSV_IMPORT_MAX_PROJECTED_IMAGES` | `5000` |
| `CARS_BULK_RUN_MAX_QUERIES` | `50` |
| `CARS_BULK_RUN_AUTO_CHUNK_SECONDS` | `10` |
| `CARS_BULK_RUN_SLEEP_SECONDS` | `1` |
| `CARS_DOWNLOAD_MAX_WIDTH` | `1600` |
| `CARS_DOWNLOAD_JPEG_QUALITY` | `82` |
| `CARS_BULK_DOWNLOAD_MAX_IMAGES` | `100` |
| `API_SEARCH_MAX_YEAR_SPAN` | `3` |
| `API_SEARCH_MAX_IMAGES_PER_YEAR` | `5` |
| `ERROR_LOG_RETENTION_DAYS` | `30` |
| `ERROR_LOG_MAX_EVENTS_PER_IMPORT` | `500` |

### AI generation

| Variable | Default |
|---|---|
| `ANTHROPIC_API_KEY` | *secret — required to generate* |
| `ANTHROPIC_MODEL` | `claude-haiku-4-5` (the cheapest current model) |
| `ANTHROPIC_MAX_TOKENS` | `8000` |
| `ANTHROPIC_EFFORT` | *blank — not sent; Haiku 4.5 rejects it* |
| `ANTHROPIC_TIMEOUT` · `ANTHROPIC_CONNECT_TIMEOUT` | `120` · `10` |
| `ANTHROPIC_RETRY_TIMES` · `ANTHROPIC_RETRY_SLEEP_MS` | `2` · `500` |
| `ANTHROPIC_INPUT_USD_PER_1M` · `ANTHROPIC_OUTPUT_USD_PER_1M` · `ANTHROPIC_CACHE_WRITE_USD_PER_1M` · `ANTHROPIC_CACHE_READ_USD_PER_1M` | *blank — use the built-in price list* |
| `ANTHROPIC_BASE_URL` | `https://api.anthropic.com` |
| `AI_MONTHLY_BUDGET_USD` | `10.0` (`0` disables the cap) |
| `AI_RESERVATION_STALE_MINUTES` | `15` |

Prices for known models are built in, so changing `ANTHROPIC_MODEL` reprices the budget automatically. A model missing from the list refuses to run until all four prices are set, so nothing is spent unmetered.

### WordPress publishing

| Variable | Default |
|---|---|
| `WORDPRESS_BASE_URL` | *site root without `/wp-json`, as its canonical URL — redirects are refused* |
| `WORDPRESS_USERNAME` | *a user with the `unfiltered_html` capability* |
| `WORDPRESS_APP_PASSWORD` | *secret — an Application Password; spaces are fine* |
| `WORDPRESS_POST_STATUS` | `draft` |
| `WORDPRESS_DEFAULT_CATEGORY_ID` · `WORDPRESS_AUTHOR_ID` | `0` · `0` (`0` sends nothing) |
| `WORDPRESS_HOMEPAGE_URL` | *blank omits the linked sub-headline* |
| `WORDPRESS_SITE_NAME` | *blank* |
| `WORDPRESS_USE_BLOCKS` | `true` |
| `WORDPRESS_TIMEOUT` · `WORDPRESS_UPLOAD_TIMEOUT` | `30` · `60` |
| `WORDPRESS_RETRY_TIMES` · `WORDPRESS_RETRY_SLEEP_MS` | `2` · `500` |

### Publishing limits

| Variable | Default |
|---|---|
| `PUBLISH_MAX_POSTS_PER_CHUNK` | `2` |
| `PUBLISH_CHUNK_SECONDS` | `60` |
| `PUBLISH_MAX_POSTS_PER_DAY` | `50` |
| `PUBLISH_SLEEP_SECONDS` | `0.5` |
| `PUBLISH_MAX_IMAGES_PER_POST` | `8` |
| `PUBLISH_MAX_GENERATION_ATTEMPTS` | `3` |
| `PUBLISH_IMAGE_MAX_WIDTH` · `PUBLISH_IMAGE_JPEG_QUALITY` | *same as `CARS_DOWNLOAD_*`* |
| `PUBLISH_IMAGE_FETCH_TIMEOUT` | `30` |
| `PUBLISH_IMAGE_MAX_BYTES` | `25000000` |
| `PUBLISH_STALE_RUN_MINUTES` | `5` |

### Clients

| Variable | Purpose |
|---|---|
| `VITE_API_URL` | API base URL for the Vue client |
| `EXPO_PUBLIC_API_URL` | API base URL for the Expo client |

---

## Testing

```bash
# Backend — unit, service, and API contract tests
cd backend && pytest

# Lint and format check
ruff check . && ruff format --check .

# Web client
cd web && npm run typecheck && npm run test

# Mobile client
cd mobile && npm run typecheck && npm test
```

**What is covered**

- **Unit** — model-name normalisation, category candidates, year matching, make confirmation, filename building, image resizing.
- **Services** — Wikimedia pagination, caching and block handling (HTTP mocked with respx), CSV import rules and caps, import coverage, chunked runs, ZIP/CSV exports.
- **API** — authentication and ability scoping, filtering, pagination, validation, rate limits, CORS, and signed single-use export links.
- **Publishing** — the spend cap under concurrent reservations (real PostgreSQL row locks), month and year boundaries, every failure class of a Claude or WordPress call, crash recovery without duplicate posts or double charges, per-model pricing, prompt-injection separation, and HTML escaping. Claude, WordPress and Commons are faked at the HTTP layer, so the suite spends no tokens.
- **WordPress plugin** — REST field registration and permissions, Yoast SEO and Rank Math copying, escaped head tags, and running beside other SEO plugins, in PHP with WordPress stubbed; the backend suite runs them, lints every PHP file and checks the zip, and CI fails rather than skips if PHP is missing.
- **Admin** — every admin page renders; review, run, prune and publishing actions behave as expected, and the publishing actions that must not spend AI budget are proven not to.
- **Contract** — API responses are compared against the JSON fixtures the mobile client's Zod schemas are tested with, so a breaking change fails both test suites.

---

## Deployment

The whole stack runs on free tiers.

| Component | Host |
|---|---|
| Django API + admin | Render (Docker web service, Gunicorn + WhiteNoise) |
| PostgreSQL | Neon |
| Vue web client | Netlify |
| Expo web build | Netlify |
| Post generation | Anthropic Claude API |
| Publishing target | Any WordPress site with the Cars Images Publisher plugin |

GitHub Actions runs linting and tests on every pull request, and deploys `main` once checks pass. Exports are streamed from temporary files, so no object storage is required.

Step-by-step setup, required secrets, and smoke checks: [DEPLOYMENT.md](DEPLOYMENT.md).

---

## Project structure

```
cars-api-django/
├── backend/
│   ├── config/              # settings, URLs, WSGI
│   ├── apps/
│   │   ├── accounts/        # users, scoped API tokens, abilities
│   │   ├── catalog/         # car makes and models
│   │   ├── searches/        # searches, Wikimedia client, category resolver, bulk runs
│   │   ├── images/          # images, review, year and make matching
│   │   ├── imports/         # CSV importer, coverage
│   │   ├── exports/         # ZIP / CSV builders, signed links
│   │   ├── observability/   # error events, block events, health summary
│   │   └── publishing/      # blog posts, Claude and WordPress clients, AI budget, publishing runs
│   ├── api/                 # bearer auth, abilities, pagination, errors, throttling, v1 views
│   ├── tests/               # unit, service, API, contract, and admin tests
│   ├── wordpress-plugin/    # Cars Images Publisher, zipped on download
│   ├── bin/start.sh         # migrate, cache table, admin, seed, Gunicorn
│   ├── Dockerfile
│   └── requirements/
├── web/                     # Vue 3 client
├── mobile/                  # Expo / React Native client
├── .github/workflows/       # CI / CD
├── docker-compose.yml
├── render.yaml              # Render Blueprint (API)
├── .env.example
├── DEPLOYMENT.md
├── CHANGELOG.md
└── README.md
```

---

## Milestones

- [x] Django project, PostgreSQL, Docker Compose
- [x] Data model and migrations
- [x] Wikimedia client, category resolver, year and make matching
- [x] Search runner, CSV importer, chunked bulk runs
- [x] ZIP / CSV exports with signed links
- [x] `/api/v1` with scoped tokens and mobile contract parity
- [x] Django admin
- [x] Vue 3 web client
- [x] Expo client connected to the Django API
- [x] CI and free-tier deployment
- [x] AI-written WordPress draft posts (Claude) with a hard monthly spend cap

---

## Roadmap

- Celery + Redis workers for bulk searches and exports.
- OpenAPI schema and generated TypeScript types shared by both clients.
- Persist exports to object storage (S3-compatible) instead of streaming.
- AI-assisted classification for ambiguous images.
- An evaluation set for generated articles (factual-figure checks, length targets) to compare models and prompts on quality per dollar.
- Scheduled publishing runs once a worker is in place.
- Tag-triggered Android and iOS builds.

---

## Author

**Ronald Allan Rivera** — [GitHub](https://github.com/RonaldAllanRivera)
