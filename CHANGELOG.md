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

### Changed
- Commons descriptions and attributions are stored as plain text instead of raw HTML, so every client shows clean credits.
- The resizer applies EXIF orientation, and a failed image download is skipped instead of aborting the whole ZIP.

### Fixed
- `\x00` bytes in upstream error bodies no longer make PostgreSQL reject error-log inserts.

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
