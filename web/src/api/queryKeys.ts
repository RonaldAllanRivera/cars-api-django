import type {
  DownloadStatus,
  ErrorContext,
  ErrorSeverity,
  ReviewStatus,
  SearchStatus,
} from './schemas';

export interface ImageFilters {
  make?: string;
  model?: string;
  year?: number;
  make_confirmed?: boolean;
  year_confirmed?: boolean;
  review_status?: ReviewStatus;
  download_status?: DownloadStatus;
  csv_import_id?: number;
}

export type CoverageFilter = 'with_images' | 'no_images' | 'not_run';

export interface SearchFilters {
  status?: SearchStatus;
  /** CSV-derived queries live under Pipeline; ad-hoc runs under Search. */
  source?: 'csv' | 'adhoc';
  csv_import_id?: number;
  coverage?: CoverageFilter;
}

export interface ErrorFilters {
  context?: ErrorContext;
  severity?: ErrorSeverity;
}

export const queryKeys = {
  images: (filters: ImageFilters = {}) => ['images', filters] as const,
  // 'count' as its own segment so it can never collide with images(filters)
  // or image(id), which share the 'images' prefix.
  imageCount: (filters: ImageFilters = {}) => ['images', 'count', filters] as const,
  image: (id: number) => ['images', id] as const,
  searchImages: (searchId: number, filters: ImageFilters = {}) =>
    ['searches', searchId, 'images', filters] as const,
  searches: (filters: SearchFilters = {}) => ['searches', filters] as const,
  search: (id: number) => ['searches', id] as const,
  imports: () => ['imports'] as const,
  import: (id: number) => ['imports', id] as const,
  health: () => ['health'] as const,
  errors: (filters: ErrorFilters = {}) => ['errors', filters] as const,
};

/** Drops undefined keys so `{ make: undefined }` and `{}` share a cache entry. */
export function compact<T extends object>(filters: T): T {
  return Object.fromEntries(
    Object.entries(filters).filter(([, value]) => value !== undefined && value !== ''),
  ) as T;
}
