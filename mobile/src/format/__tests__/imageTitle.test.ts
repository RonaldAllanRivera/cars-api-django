import { byline, cleanTitle } from '../imageTitle';

describe('cleanTitle', () => {
  it('strips the File: prefix, the extension and the disambiguator', () => {
    expect(cleanTitle('File:2001 Audi RS4 B5 Avant - Flickr - The Car Spy (3).jpg')).toBe(
      '2001 Audi RS4 B5 Avant - Flickr - The Car Spy',
    );
  });

  it('turns underscores back into spaces', () => {
    // Commons page titles use underscores where the URL form does.
    expect(cleanTitle('File:1998_Toyota_Corolla.jpg')).toBe('1998 Toyota Corolla');
  });

  it('leaves a title that is already clean alone', () => {
    expect(cleanTitle('A red car')).toBe('A red car');
  });

  it('keeps a bracketed word that is not a disambiguator', () => {
    // Only a bare integer in trailing parentheses is Commons' duplicate
    // marker. Stripping every trailing bracket would eat real content.
    expect(cleanTitle('File:Audi at the show (Geneva).jpg')).toBe('Audi at the show (Geneva)');
  });

  it('handles an uppercase extension', () => {
    expect(cleanTitle('File:Audi A4.JPEG')).toBe('Audi A4');
  });

  it('passes null through', () => {
    expect(cleanTitle(null)).toBeNull();
  });

  it('returns null rather than an empty string when nothing survives', () => {
    // An empty string would render as a blank line where a title should be.
    expect(cleanTitle('File:.jpg')).toBeNull();
  });
});

describe('byline', () => {
  it('prefers the attribution when there is one', () => {
    expect(byline('The Car Spy', 'File:Audi.jpg')).toBe('The Car Spy');
  });

  it('falls back to the cleaned title', () => {
    expect(byline(null, 'File:1998_Toyota_Corolla.jpg')).toBe('1998 Toyota Corolla');
  });

  it('treats a whitespace-only attribution as absent', () => {
    expect(byline('   ', 'File:1998_Toyota_Corolla.jpg')).toBe('1998 Toyota Corolla');
  });

  it('is null when there is nothing to say', () => {
    expect(byline(null, null)).toBeNull();
  });
});
