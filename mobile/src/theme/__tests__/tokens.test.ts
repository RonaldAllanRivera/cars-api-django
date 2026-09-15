import { color, fontSize, radius, space } from '../tokens';

describe('design tokens', () => {
  it('gives every colour a six-digit hex value', () => {
    // tailwind.config.js requires this module from Node at build time and
    // spreads it straight into theme.extend.colors. A non-hex value there is
    // not a type error, it is a class name that silently does nothing.
    for (const [name, value] of Object.entries(color)) {
      expect(`${name}: ${value}`).toMatch(/: #[0-9a-f]{6}$/);
    }
  });

  it('separates the three surface tiers', () => {
    // A single step is what makes the current app read flat; the card must be
    // lighter than the shell and the input lighter again.
    expect(color.surface).not.toBe(color.surfaceRaised);
    expect(color.surfaceRaised).not.toBe(color.surfaceSunken);
  });

  it('puts a dark label on the amber fill', () => {
    // White on amber-500 is ~1.8:1 and fails; slate-950 on it is ~9:1. The
    // panel's own amber button has dark text.
    expect(color.accentFg).toBe(color.surface);
  });

  it('scales type in five ascending steps', () => {
    const steps = [
      fontSize.micro,
      fontSize.meta,
      fontSize.body,
      fontSize.section,
      fontSize.title,
    ].map(([size]) => parseFloat(size));

    expect(steps).toEqual([...steps].sort((a, b) => a - b));
    expect(new Set(steps).size).toBe(steps.length);
  });

  it('keeps spacing on a 4px rhythm', () => {
    for (const value of Object.values(space)) {
      expect(parseFloat(value) % 4).toBe(0);
    }
  });

  it('names three radius tiers', () => {
    expect(radius.control).toBeLessThan(radius.surface);
    expect(radius.pill).toBeGreaterThan(radius.surface);
  });
});
