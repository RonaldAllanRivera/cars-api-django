import { describe, expect, it } from 'vitest';

import { byline, cleanTitle } from '../imageTitle';
import { vehicleName, yearRange } from '../labels';
import { humanSeconds, plural, timeAgo } from '../time';

describe('cleanTitle', () => {
  it('strips the Commons prefix, extension, duplicate marker and underscores', () => {
    expect(cleanTitle('File:2001_Audi_RS4_B5_Avant - Flickr (3).jpg')).toBe('2001 Audi RS4 B5 Avant - Flickr');
  });

  it('keeps a parenthetical that is real content', () => {
    expect(cleanTitle('File:Ferrari F40 (Geneva).JPG')).toBe('Ferrari F40 (Geneva)');
  });

  it('returns null rather than an empty line', () => {
    expect(cleanTitle('File:.jpg')).toBeNull();
    expect(cleanTitle(null)).toBeNull();
  });
});

describe('byline', () => {
  it('prefers the attribution, then the cleaned title', () => {
    expect(byline('Photo by A. Person', 'File:x.jpg')).toBe('Photo by A. Person');
    expect(byline('   ', 'File:Toyota_RAV4.jpg')).toBe('Toyota RAV4');
  });
});

describe('labels', () => {
  it('names a vehicle without gaps for a missing model', () => {
    expect(vehicleName({ make: 'Toyota', model: null, year: 1997 })).toBe('Toyota 1997');
  });

  it('collapses a single-year range', () => {
    expect(yearRange({ from_year: 1997, to_year: 1997 })).toBe('1997');
    expect(yearRange({ from_year: 1997, to_year: 1999 })).toBe('1997–1999');
  });
});

describe('time', () => {
  it('reads a wait in minutes', () => {
    expect(humanSeconds(45)).toBe('45s');
    expect(humanSeconds(600)).toBe('10m 0s');
    expect(humanSeconds(3720)).toBe('1h 2m');
  });

  it('says how long ago', () => {
    const now = Date.parse('2026-01-15T12:00:00Z');

    expect(timeAgo('2026-01-15T09:00:00Z', now)).toBe('3 hours ago');
    expect(timeAgo('2026-01-15T11:59:30Z', now)).toBe('just now');
    expect(timeAgo(null, now)).toBeNull();
  });

  it('pluralises', () => {
    expect(plural(1, 'query', 'queries')).toBe('1 query');
    expect(plural(1200, 'image')).toBe('1,200 images');
  });
});
