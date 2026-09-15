/**
 * The single source of truth for colour, type, spacing and radius.
 *
 * Deliberately plain data with no imports: `tailwind.config.js` requires this
 * file from Node at build time, so anything importing React, NativeWind or a
 * path alias would break the Tailwind build rather than fail a type check.
 *
 * Two consumers, one file. Navigator options (headerStyle,
 * tabBarActiveTintColor, contentStyle) and props like placeholderTextColor and
 * RefreshControl.tintColor take values, not class names, so a palette that
 * lived only in the Tailwind config would land in the classNames and miss
 * every navigator - shipping amber content inside sky-blue chrome.
 */

/**
 * Three surface tiers, mirroring how Filament's light panel raises a white
 * card off a grey shell. The app previously had one step (slate-800 on
 * slate-900), which is why its card density read as flat.
 */
export const color = {
  surface: '#020617', // slate-950 - screen background
  surfaceRaised: '#0f172a', // slate-900 - cards, list rows
  surfaceSunken: '#1e293b', // slate-800 - inputs, inactive chips
  border: '#1e293b', // slate-800 - hairlines
  borderStrong: '#334155', // slate-700 - chip outlines, dividers

  text: '#f8fafc', // slate-50
  textSecondary: '#94a3b8', // slate-400
  textMuted: '#64748b', // slate-500

  /*
   * Amber is the panel's configured primary (AdminPanelProvider sets
   * `'primary' => Color::Amber`). It is the ACTION colour only - no status
   * badge is ever amber, so it never competes with the failure red.
   */
  accent: '#f59e0b', // amber-500 - primary action fills
  accentText: '#fbbf24', // amber-400 - links and accents on dark
  accentFg: '#020617', // the label ON an amber fill; white would be ~1.8:1

  /*
   * Status colours keep the roles StatusBadge already gave them. Sky survives
   * here as "running" and stops being the app's accent.
   */
  success: '#10b981', // emerald-500
  successText: '#6ee7b7', // emerald-300
  danger: '#ef4444', // red-500
  dangerText: '#fca5a5', // red-300
  info: '#0ea5e9', // sky-500
  infoText: '#7dd3fc', // sky-300
} as const;

/** 4px rhythm. Screen padding 4, card padding 3, list gap 2, section gap 6. */
export const space = {
  1: '4px',
  2: '8px',
  3: '12px',
  4: '16px',
  6: '24px',
  8: '32px',
} as const;

/** Three tiers: what kind of thing a surface is, encoded as its corner. */
export const radius = {
  control: 8,
  surface: 12,
  pill: 9999,
} as const;

/**
 * Five steps at roughly a 1.2 ratio, as [size, { lineHeight, letterSpacing?,
 * fontWeight }] - the tuple shape Tailwind's fontSize theme key accepts.
 *
 * Body is 15, not 14: at 14 it blurs into meta at 12. The gap to 13 is what
 * makes a card's title and its byline read as different kinds of information.
 */
export const fontSize = {
  micro: ['11px', { lineHeight: '16px', letterSpacing: '0.02em', fontWeight: '600' }],
  meta: ['13px', { lineHeight: '18px', fontWeight: '400' }],
  body: ['15px', { lineHeight: '22px', fontWeight: '400' }],
  section: ['18px', { lineHeight: '24px', fontWeight: '600' }],
  title: ['24px', { lineHeight: '30px', letterSpacing: '-0.02em', fontWeight: '700' }],
} as const;
