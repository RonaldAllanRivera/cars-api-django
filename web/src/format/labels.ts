import type { ErrorContext, Image, Search } from '@/api/schemas';

export const CONTEXT_LABELS: Record<ErrorContext, string> = {
  csv_upload: 'CSV upload',
  csv_row: 'CSV row',
  search_run: 'Search run',
  image_download: 'Image download',
  wikimedia_block: 'Wikimedia block',
};

export function sentenceCase(value: string): string {
  const spaced = value.replace(/_/g, ' ');

  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

/** "Toyota RAV4 1997" - the name a card leads with. */
export function vehicleName(image: Pick<Image, 'make' | 'model' | 'year'>): string {
  return [image.make, image.model, image.year].filter(Boolean).join(' ');
}

/** "1997" or "1997–1999". */
export function yearRange(search: Pick<Search, 'from_year' | 'to_year'>): string {
  return search.from_year === search.to_year
    ? String(search.from_year)
    : `${search.from_year}–${search.to_year}`;
}
