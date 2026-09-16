# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Backend:** Django 5.2 + DRF API with scoped, hashed bearer tokens, cursor pagination and `422` validation errors matching the published client contract.
- **Search:** Wikimedia Commons client with caching, back-off and block detection; category resolution; exact-year and make matching; multi-year search runner; time-boxed bulk runs.
- **Pipeline:** CSV importer with validation, dedupe and caps; import coverage; Pillow ZIP export and matching CSV manifest; health summary; `prune_error_events`.
- **API:** all `/api/v1` endpoints, with a contract test against the mobile client's JSON fixtures. Export links are signed, and ZIP links are single-use.
- **Admin:** Django admin for runs, reviews, exports, error log and token revocation; `ensure_admin` and `seed_catalog` commands.
- **Admin dashboard:** pipeline health stats, failures by kind, search throughput and latest failures on the admin home page, drawn as inline SVG so the admin needs no charting library.
- **Web client:** Vue 3 app with search, library, CSV pipeline with live bulk-run progress, keyboard-driven review queue, and health dashboard.
- **Mobile client:** the existing Expo app, running unchanged against the new API.
- **Infrastructure:** Docker image, Render Blueprint, GitHub Actions for backend, web and mobile, and a free-tier deployment guide.
- **Publishing (in progress):** `apps.publishing` with the blog post, attachment, AI usage and monthly budget records; `ANTHROPIC`, `AI_BUDGET`, `WORDPRESS` and `CARS_PUBLISHING` settings; SEO fallbacks that derive a missing SEO title, description or keywords from the article and the vehicle; the post prompt with a strict JSON response schema; a hard monthly AI spend cap enforced before every call; the Claude and WordPress clients; image upload with Commons credits and a Gutenberg gallery; time-boxed publishing runs; admin actions, an AI spend widget on the dashboard, `publish_blog_posts`, and `/api/v1/blog-posts` behind new `blog:read`, `blog:write` and `blog:publish` abilities. Posts are created as WordPress drafts.

### Changed
- Commons descriptions and attributions are stored as plain text instead of raw HTML, so every client shows clean credits.
- The resizer applies EXIF orientation, and a failed image download is skipped instead of aborting the whole ZIP.
- The error log gains AI generation, AI budget, WordPress publish and WordPress media contexts, and an optional link to the blog post a failure happened on.
- `/health/summary` reports a fixed set of context keys rather than every `ErrorEvent.Context`, so adding a context server-side cannot break a deployed client's parsing.
- Both clients accept an error context they have never seen and label it readably, instead of rejecting the whole response.

### Fixed
- `\x00` bytes in upstream error bodies no longer make PostgreSQL reject error-log inserts.
- An error context with no assigned chart colour no longer raises `KeyError` on the admin home page; it greys out instead.

### Decided
- **One post per (make, model, year), keyed by slug.** `model` is nullable and PostgreSQL treats NULLs as distinct, so a unique constraint over the three columns would admit duplicates. The slug doubles as the WordPress slug, which is how a crashed run finds the draft it already created.
- **Money is `Decimal`, never `float`.** A budget compared against accumulated float error is not a budget.
- **AI text is committed before WordPress is touched.** A failed publish is retried without paying for the words again.
- **Facts never enter the prompt's instructions.** Commons file titles are text anyone can upload, so they travel only in the data message. The instructions stay identical for every vehicle, which is also the prefix a provider can cache.
- **No invented figures.** The prompt forbids any price, mileage or performance figure the pipeline did not supply, because an article about a model year has none to give.
- **SEO descriptions come from the intro paragraph**, not the whole article: it opens with a linked sub-headline, which makes a poor description.
- **Posts are written by Claude through the official `anthropic` SDK**, defaulting to `claude-haiku-4-5`, the cheapest current model. The model is configurable with `ANTHROPIC_MODEL`.
- **Prices are keyed by model.** Changing the model reprices the budget; an unpriced model refuses to run rather than spending unmetered.
- **The SDK's automatic retries are off.** It retries timeouts, and a request that timed out may already have been billed, so a retry could pay for the same article twice.
- **Drafts only, and an update never sends a status**, so a post an editor already put live stays live.
- **Quoted figures are flagged, not discarded.** Discarding would pay to regenerate on every run; every post is a draft a person reviews anyway.
- **At most three paid writing attempts per post** (`PUBLISH_MAX_GENERATION_ATTEMPTS`), so a post that always fails cannot drain the budget.
- **A spend cap enforced before the call, not tallied after.** Each call reserves its worst-case cost under a row lock and settles to the real cost; a crash over-reports spend rather than under-reporting it.

## [0.1.0] - 2026-09-15

### Added
- Project foundation for Cars Images API.
- `README.md` covering architecture, API contract, engineering decisions, configuration, testing, and deployment.
- `.gitignore` for Django, Vue, and Expo, with secrets, local environment files, and native build artifacts excluded.
- `CHANGELOG.md` following Keep a Changelog.

### Decided
- **Backend:** Django 5.2 LTS + Django REST Framework, chosen for long-term support through April 2028.
- **Database:** PostgreSQL, replacing MySQL, for free managed hosting and native JSON and index support.
- **Web client:** Vue 3 with TanStack Query and Zod, mirroring the mobile client's API layer.
- **Mobile client:** the existing Expo / React Native app is kept unchanged. The API matches its JSON contract (bearer tokens, `{data}` envelopes, cursor pagination, `422` validation errors).
- **Configuration:** one flat set of environment variable names shared by local, CI and deployed runs, so the same `.env` and deployment secrets work everywhere.
- **Hosting:** free tiers — Render (API), Neon (PostgreSQL), Netlify (web clients).

### Fixed
- Deleting a CSV import will remove its queued searches, matching what the delete confirmation promises.
- No seeded admin with a hard-coded password; admins are created with `createsuperuser`.
- `CARS_BULK_RUN_AUTO_CHUNK_SECONDS` and the `WIKIMEDIA_CATEGORY_*` settings are documented in the configuration reference.

[Unreleased]: https://github.com/RonaldAllanRivera/cars-api-django/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/RonaldAllanRivera/cars-api-django/releases/tag/v0.1.0
