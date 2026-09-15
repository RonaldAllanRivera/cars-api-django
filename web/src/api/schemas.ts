import { z } from 'zod';

/** The three review verdicts. Never write make_confirmed from the client. */
export const ReviewStatusSchema = z.enum(['pending', 'approved', 'rejected']);
export type ReviewStatus = z.infer<typeof ReviewStatusSchema>;

export const DownloadStatusSchema = z.enum([
  'not_downloaded',
  'downloading',
  'downloaded',
  'failed',
]);
export type DownloadStatus = z.infer<typeof DownloadStatusSchema>;

export const SearchStatusSchema = z.enum(['pending', 'running', 'completed', 'failed']);
export type SearchStatus = z.infer<typeof SearchStatusSchema>;

export const ErrorContextSchema = z.enum([
  'csv_upload',
  'csv_row',
  'search_run',
  'image_download',
  'wikimedia_block',
]);
export type ErrorContext = z.infer<typeof ErrorContextSchema>;

/** ListErrorsRequest validates severity against exactly these two values. */
export const ErrorSeveritySchema = z.enum(['error', 'warning']);
export type ErrorSeverity = z.infer<typeof ErrorSeveritySchema>;

/**
 * Every ability a token can carry. The last four are privileged and are issued
 * only when a client names them in the login request; a login that sends no
 * `abilities` receives the first four.
 */
export const TokenAbilitySchema = z.enum([
  'search:read',
  'search:write',
  'review:write',
  'errors:read',
  'imports:read',
  'imports:write',
  'search:run',
  'exports:read',
]);
export type TokenAbility = z.infer<typeof TokenAbilitySchema>;

export const UserSchema = z.object({
  id: z.number().int(),
  name: z.string(),
  email: z.string(),
});
export type User = z.infer<typeof UserSchema>;

export const ImageSchema = z.object({
  id: z.number().int(),
  car_search_id: z.number().int().nullable(),
  make: z.string(),
  model: z.string().nullable(),
  year: z.number().int(),
  color: z.string().nullable(),
  title: z.string(),
  description: z.string().nullable(),
  source_url: z.string(),
  thumbnail_url: z.string().nullable(),
  width: z.number().int().nullable(),
  height: z.number().int().nullable(),
  license: z.string().nullable(),
  attribution: z.string().nullable(),
  // Nullable is the machine's "unknown" verdict - neither true nor false.
  make_confirmed: z.boolean().nullable(),
  year_confirmed: z.boolean().nullable(),
  review_status: ReviewStatusSchema,
  reviewed_by: z.number().int().nullable(),
  reviewed_at: z.string().nullable(),
  download_status: DownloadStatusSchema,
  created_at: z.string().nullable(),
});
export type Image = z.infer<typeof ImageSchema>;

export const SearchSchema = z.object({
  id: z.number().int(),
  make: z.string(),
  model: z.string().nullable(),
  commons_category: z.string().nullable(),
  from_year: z.number().int(),
  to_year: z.number().int(),
  color: z.string().nullable(),
  transmission: z.string().nullable(),
  transparent_background: z.boolean(),
  images_per_year: z.number().int(),
  status: SearchStatusSchema,
  csv_import_id: z.number().int().nullable(),
  // The migration declares this column NOT NULL - every search has a creator.
  requested_by: z.number().int(),
  // whenCounted / whenLoaded: present only on the endpoints that add them.
  images_count: z.number().int().optional(),
  images: z.array(ImageSchema).optional(),
  created_at: z.string().nullable(),
  updated_at: z.string().nullable(),
});
export type Search = z.infer<typeof SearchSchema>;

export const ErrorEventSchema = z.object({
  id: z.number().int(),
  context: ErrorContextSchema,
  severity: ErrorSeveritySchema,
  message: z.string().nullable(),
  exception_class: z.string().nullable(),
  exception_message: z.string().nullable(),
  trace_excerpt: z.string().nullable(),
  details: z.unknown().nullable(),
  car_search_id: z.number().int().nullable(),
  csv_import_id: z.number().int().nullable(),
  car_image_id: z.number().int().nullable(),
  occurred_at: z.string().nullable(),
});
export type ErrorEvent = z.infer<typeof ErrorEventSchema>;

export const HealthSummarySchema = z.object({
  searches_by_status: z.record(SearchStatusSchema, z.number().int()),
  errors_last_24h: z.number().int(),
  errors_by_context_last_7d: z.record(ErrorContextSchema, z.number().int()),
  images_last_7d: z.number().int(),
  latest_error_at: z.string().nullable(),
});
export type HealthSummary = z.infer<typeof HealthSummarySchema>;

/**
 * The six coverage counts. `searched` is derived server-side (total minus
 * not_run) rather than recomputed here, so every client and the admin cannot
 * disagree about what "searched" means.
 */
export const CoverageSchema = z.object({
  total: z.number().int(),
  searched: z.number().int(),
  not_run: z.number().int(),
  failed: z.number().int(),
  with_images: z.number().int(),
  no_images: z.number().int(),
});
export type Coverage = z.infer<typeof CoverageSchema>;

export const ImportSchema = z.object({
  id: z.number().int(),
  original_filename: z.string(),
  total_rows: z.number().int().nullable(),
  unique_combos: z.number().int().nullable(),
  duplicates_skipped: z.number().int().nullable(),
  imported_by: z.number().int().nullable(),
  importer_name: z.string().nullable().optional(),
  searches_count: z.number().int().optional(),
  // Absent on the list, present-and-nullable on the detail: null is what the
  // server returns for an import with no searches yet.
  coverage: CoverageSchema.nullable().optional(),
  created_at: z.string().nullable(),
});
export type Import = z.infer<typeof ImportSchema>;

/**
 * One search's result inside a bulk-run chunk.
 *
 * No `skipped`: the server re-selects from the database each call rather than
 * draining a queue captured at start, so a row deleted or finished by someone
 * else is simply not selected. There is nothing to skip.
 */
export const RunOutcomeSchema = z.object({
  id: z.number().int(),
  make: z.string(),
  model: z.string().nullable(),
  from_year: z.number().int(),
  outcome: z.enum(['completed', 'failed']),
});
export type RunOutcome = z.infer<typeof RunOutcomeSchema>;

export const RunChunkResponseSchema = z.object({
  outcomes: z.array(RunOutcomeSchema),
  ran_seconds: z.number(),
  /** Recounted server-side after the slice, so it survives a dropped response. */
  remaining: z.number().int(),
  // Wikimedia does not always send Retry-After, so the window is nullable even
  // when a block did happen.
  blocked: z
    .object({ status: z.number().int(), retry_after_seconds: z.number().int().nullable() })
    .nullable(),
});
export type RunChunkResponse = z.infer<typeof RunChunkResponseSchema>;

export const ImageCountSchema = z.object({ count: z.number().int() });

export const ExportLinkSchema = z.object({
  url: z.string().url(),
  expires_at: z.string(),
  count: z.number().int(),
  format: z.enum(['csv', 'zip']),
});
export type ExportLink = z.infer<typeof ExportLinkSchema>;

/** POST /auth/login is the ONE endpoint with no `data` envelope. */
export const LoginResponseSchema = z.object({
  token: z.string(),
  token_type: z.literal('Bearer'),
  abilities: z.array(TokenAbilitySchema),
  user: UserSchema,
});
export type LoginResponse = z.infer<typeof LoginResponseSchema>;

/** A 422 from any Form Request. */
export const ValidationErrorSchema = z.object({
  message: z.string(),
  errors: z.record(z.string(), z.array(z.string())),
});
export type ValidationError = z.infer<typeof ValidationErrorSchema>;

/** Every single-resource endpoint except login. */
export const single = <T extends z.ZodTypeAny>(schema: T) => z.object({ data: schema });

/**
 * The cursor envelope every list endpoint returns. `meta.next_cursor` is null on the last page -
 * that null is the infinite-scroll terminator.
 */
export const cursorPage = <T extends z.ZodTypeAny>(schema: T) =>
  z.object({
    data: z.array(schema),
    links: z.object({
      first: z.string().nullable(),
      last: z.string().nullable(),
      prev: z.string().nullable(),
      next: z.string().nullable(),
    }),
    meta: z.object({
      path: z.string(),
      per_page: z.number().int(),
      next_cursor: z.string().nullable(),
      prev_cursor: z.string().nullable(),
    }),
  });

export type CursorPage<T> = {
  data: T[];
  links: { first: string | null; last: string | null; prev: string | null; next: string | null };
  meta: { path: string; per_page: number; next_cursor: string | null; prev_cursor: string | null };
};
