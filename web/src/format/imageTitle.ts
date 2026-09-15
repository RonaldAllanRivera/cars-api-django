/**
 * Wikimedia Commons file titles, made fit for a human.
 *
 * The API returns the page title verbatim - `File:` prefix, underscores,
 * extension and Commons' ` (n)` duplicate marker included - so a card would
 * otherwise show a reviewer
 * `File:2001 Audi RS4 B5 Avant - Flickr - The Car Spy (3).jpg`.
 *
 * Pure functions, so they are unit-testable without mounting anything.
 */

/** Commons' duplicate marker is a bare integer; `(Geneva)` is real content. */
const DISAMBIGUATOR = /\s*\(\d+\)$/;
const EXTENSION = /\.(jpe?g|png|gif|webp|tiff?|svg)$/i;
const PREFIX = /^file:/i;

export function cleanTitle(raw: string | null): string | null {
  if (raw === null) return null;

  const cleaned = raw
    .replace(PREFIX, '')
    .replace(EXTENSION, '')
    .replace(DISAMBIGUATOR, '')
    .replace(/_/g, ' ')
    .trim();

  // An empty string would render as a blank line where a title should be.
  return cleaned === '' ? null : cleaned;
}

/** The line under a card's heading: who took it, else what it is called. */
export function byline(attribution: string | null, title: string | null): string | null {
  const attributed = attribution?.trim();

  if (attributed) return attributed;

  return cleanTitle(title);
}
