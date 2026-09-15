<script setup lang="ts">
import type { CoverageFilter } from '@/api/queryKeys';
import type { Coverage } from '@/api/schemas';

/**
 * How much of an import has actually been searched. The image list can only
 * show images that exist, so a run that stopped early and one that finished
 * finding little look identical; these counts tell them apart.
 *
 * Three tiles are buttons because three is how many the API can filter the
 * query list by. The other three are figures: a button would promise a list
 * that cannot be fetched.
 */
defineProps<{ coverage: Coverage; selected: CoverageFilter | null }>();
const emit = defineEmits<{ select: [filter: CoverageFilter | null] }>();

const FILTERABLE: { key: CoverageFilter; caption: string }[] = [
  { key: 'not_run', caption: 'not run yet' },
  { key: 'no_images', caption: 'ran, found nothing' },
  { key: 'with_images', caption: 'found images' },
];
</script>

<template>
  <section aria-label="Coverage" class="grid grid-cols-2 gap-px overflow-hidden rounded-surface border border-line bg-line sm:grid-cols-3 lg:grid-cols-6">
    <div class="bg-raised p-4">
      <p class="type-figure text-[28px] leading-8 text-ink">{{ coverage.total }}</p>
      <p class="mt-1 text-meta text-ink-2">queries</p>
    </div>
    <div class="bg-raised p-4">
      <p class="type-figure text-[28px] leading-8 text-ink">{{ coverage.searched }}</p>
      <p class="mt-1 text-meta text-ink-2">searched</p>
    </div>
    <div class="bg-raised p-4">
      <p class="type-figure text-[28px] leading-8" :class="coverage.failed > 0 ? 'text-danger-text' : 'text-ink'">
        {{ coverage.failed }}
      </p>
      <p class="mt-1 text-meta text-ink-2">failed</p>
    </div>
    <button
      v-for="tile in FILTERABLE"
      :key="tile.key"
      type="button"
      :aria-pressed="selected === tile.key"
      :aria-label="`${coverage[tile.key]} ${tile.caption}. ${selected === tile.key ? 'Showing only these; press to show all' : 'Show only these'}`"
      class="group relative p-4 text-left transition-colors focus-visible:z-10 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-accent-text"
      :class="selected === tile.key ? 'bg-accent text-accent-fg' : 'bg-raised hover:bg-sunken'"
      @click="emit('select', selected === tile.key ? null : tile.key)"
    >
      <p class="type-figure text-[28px] leading-8" :class="selected === tile.key ? 'text-accent-fg' : 'text-ink'">
        {{ coverage[tile.key] }}
      </p>
      <p class="mt-1 text-meta" :class="selected === tile.key ? 'text-accent-fg' : 'text-ink-2 group-hover:text-ink'">
        {{ tile.caption }}
      </p>
      <span
        class="absolute top-3 right-3 text-micro font-semibold"
        :class="selected === tile.key ? 'text-accent-fg' : 'text-accent-text opacity-0 group-hover:opacity-100'"
        aria-hidden="true"
      >{{ selected === tile.key ? 'Clear' : 'Filter' }}</span>
    </button>
  </section>
</template>
