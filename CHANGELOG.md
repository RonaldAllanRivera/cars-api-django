# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-09-15

### Added
- Project foundation for the Django port of Cars Images API.
- `README.md` covering architecture, API contract, engineering decisions, configuration, testing, and deployment.
- `.gitignore` for Django, Vue, and Expo, with secrets, local environment files, and native build artifacts excluded.
- `CHANGELOG.md` following Keep a Changelog.

### Decided
- **Backend:** Django 5.2 LTS + Django REST Framework, chosen for long-term support through April 2028.
- **Database:** PostgreSQL, replacing MySQL, for free managed hosting and native JSON and index support.
- **Web client:** Vue 3 with TanStack Query and Zod, mirroring the mobile client's API layer.
- **Mobile client:** the existing Expo / React Native app is kept unchanged. The API matches its JSON contract (bearer tokens, `{data}` envelopes, cursor pagination, `422` validation errors).
- **Configuration:** environment variable names carried over from the Laravel project so existing `.env` files and deployment secrets can be reused.
- **Hosting:** free tiers — Render (API), Neon (PostgreSQL), Netlify (web clients).

### Fixed (compared with the Laravel version)
- Deleting a CSV import will remove its queued searches, matching what the delete confirmation promises.
- No seeded admin with a hard-coded password; admins are created with `createsuperuser`.
- `CARS_BULK_RUN_AUTO_CHUNK_SECONDS` and the `WIKIMEDIA_CATEGORY_*` settings are documented in the configuration reference.

[Unreleased]: https://github.com/RonaldAllanRivera/cars-api-django/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/RonaldAllanRivera/cars-api-django/releases/tag/v0.1.0
