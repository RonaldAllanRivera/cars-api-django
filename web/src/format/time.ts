/** "10m 0s" rather than "600s": minutes are how a wait is actually judged. */
export function humanSeconds(seconds: number): string {
  const whole = Math.max(0, Math.round(seconds));
  const hours = Math.floor(whole / 3600);
  const minutes = Math.floor((whole % 3600) / 60);
  const rest = whole % 60;

  if (hours > 0) return `${hours}h ${minutes}m`;

  return minutes > 0 ? `${minutes}m ${rest}s` : `${rest}s`;
}

const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ['year', 31_536_000],
  ['month', 2_592_000],
  ['week', 604_800],
  ['day', 86_400],
  ['hour', 3_600],
  ['minute', 60],
];

const relative = new Intl.RelativeTimeFormat('en', { numeric: 'auto' });

/** "3 hours ago". Null in, null out, so templates can fall back. */
export function timeAgo(iso: string | null, now: number = Date.now()): string | null {
  if (!iso) return null;

  const then = Date.parse(iso);
  if (Number.isNaN(then)) return null;

  const seconds = Math.round((then - now) / 1000);

  for (const [unit, size] of UNITS) {
    if (Math.abs(seconds) >= size) return relative.format(Math.round(seconds / size), unit);
  }

  return 'just now';
}

const absolute = new Intl.DateTimeFormat('en', { dateStyle: 'medium', timeStyle: 'short' });

export function formatDateTime(iso: string | null): string | null {
  if (!iso) return null;

  const then = Date.parse(iso);

  return Number.isNaN(then) ? null : absolute.format(then);
}

export function plural(count: number, one: string, many = `${one}s`): string {
  return `${count.toLocaleString('en')} ${count === 1 ? one : many}`;
}
