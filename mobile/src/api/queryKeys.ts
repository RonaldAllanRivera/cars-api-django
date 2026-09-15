import type { ErrorContext, ErrorSeverity, ReviewStatus, SearchStatus } from './schemas';

export interface ImageFilters {
  make?: string;
  model?: string;
  year?: number;
  make_confirmed?: boolean;
  year_confirmed?: boolean;
  review_status?: ReviewStatus;
  download_status?: 'not_downloaded' | 'downloading' | 'downloaded' | 'failed';
  csv_import_id?: number;
}

export interface SearchFilters {
  status?: SearchStatus;
  /** The panel keeps CSV-derived and ad-hoc searches in separate resources. */
  source?: 'csv' | 'adhoc';
  csv_import_id?: number;
  coverage?: 'with_images' | 'no_images' | 'not_run';
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
