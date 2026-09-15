<script setup lang="ts">
/**
 * A handful of stroke icons, inlined rather than pulled from an icon package:
 * fifteen paths do not justify a dependency, and inline SVG needs no CSP room.
 */
const PATHS = {
  search: 'M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16Zm10 2-4.35-4.35',
  images:
    'M4 5h12a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2Zm18 3v11a3 3 0 0 1-3 3H7M2 15l4.5-4.5a1.5 1.5 0 0 1 2.1 0L13 15m-1.5-1.5 1.9-1.9a1.5 1.5 0 0 1 2.1 0L18 14',
  layers: 'm12 2 10 5-10 5L2 7l10-5Zm-10 10 10 5 10-5M2 17l10 5 10-5',
  review: 'M9 12.5 11 14.5 15.5 10M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z',
  pulse: 'M3 12h4l3-8 4 16 3-8h4',
  logout: 'M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3M10 17l-5-5 5-5M5 12h12',
  upload: 'M12 16V4m0 0-4.5 4.5M12 4l4.5 4.5M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3',
  back: 'M19 12H5m0 0 6 6m-6-6 6-6',
  external: 'M14 4h6v6m0-6-9 9M18 14v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4',
  play: 'M7 5.5v13a1 1 0 0 0 1.5.86l11-6.5a1 1 0 0 0 0-1.72l-11-6.5A1 1 0 0 0 7 5.5Z',
  pause: 'M8 5v14M16 5v14',
  x: 'M6 6l12 12M18 6 6 18',
  check: 'm5 12.5 4.5 4.5L19 7.5',
  chevron: 'm6 9 6 6 6-6',
  alert: 'M12 9v4m0 4h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z',
  download: 'M12 4v12m0 0-4.5-4.5M12 16l4.5-4.5M4 20h16',
  file: 'M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5Zm0 0v5h5M9 13h6M9 17h4',
  clock: 'M12 7v5l3 2m6-2a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z',
  arrowLeft: 'm15 18-6-6 6-6',
  arrowRight: 'm9 18 6-6-6-6',
  undo: 'M9 14 4 9l5-5M4 9h11a5 5 0 0 1 0 10h-3',
} as const;

export type IconName = keyof typeof PATHS;

withDefaults(defineProps<{ name: IconName; size?: number; strokeWidth?: number }>(), {
  size: 20,
  strokeWidth: 1.75,
});
</script>

<template>
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    :stroke-width="strokeWidth"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
    focusable="false"
  >
    <path :d="PATHS[name]" />
  </svg>
</template>
