<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { RouterLink } from 'vue-router';

import { errorMessage } from '@/api/client';
import { useImageCount } from '@/api/composables/useImages';
import { useReviewImage, useReviewQueue } from '@/api/composables/useReviewImage';
import type { Image, ReviewStatus } from '@/api/schemas';
import BaseButton from '@/components/BaseButton.vue';
import CarImage from '@/components/CarImage.vue';
import EmptyState from '@/components/EmptyState.vue';
import ErrorBanner from '@/components/ErrorBanner.vue';
import PageHeader from '@/components/PageHeader.vue';
import SkeletonBlock from '@/components/SkeletonBlock.vue';
import VerdictBadge from '@/components/VerdictBadge.vue';
import { useDocumentTitle } from '@/composables/useDocumentTitle';
import { showToast } from '@/composables/useToast';
import { byline, cleanTitle } from '@/format/imageTitle';
import { vehicleName } from '@/format/labels';

useDocumentTitle('Review');

const { query, images } = useReviewQueue();
const review = useReviewImage();
const waiting = useImageCount({ review_status: 'pending' });

/*
 * The light table: one image large, the rest of the queue as a strip. A verdict
 * removes the image from the queue optimistically, so the same position now
 * holds the next one - the reviewer never has to move to keep going.
 */
const position = ref(0);
const current = computed<Image | undefined>(() => images.value[Math.min(position.value, images.value.length - 1)]);
const currentIndex = computed(() => (current.value ? images.value.indexOf(current.value) : -1));

watch(
  () => images.value.length,
  (length) => {
    if (position.value > length - 1) position.value = Math.max(0, length - 1);
  },
);

// Keep a few images ahead loaded, so the strip never runs dry mid-session.
watch(
  [currentIndex, () => images.value.length],
  ([index, length]) => {
    if (length - index <= 4 && query.hasNextPage.value && !query.isFetchingNextPage.value) {
      void query.fetchNextPage();
    }
  },
);

/** Which way the outgoing image leaves: the one piece of motion on this page. */
const exit = ref<'approve' | 'reject' | 'none'>('none');
const lastVerdict = ref<{ image: Image; status: Exclude<ReviewStatus, 'pending'> } | null>(null);
const failure = ref<string | null>(null);

function decide(status: Exclude<ReviewStatus, 'pending'>): void {
  const image = current.value;
  if (!image) return;

  exit.value = status === 'approved' ? 'approve' : 'reject';
  failure.value = null;
  lastVerdict.value = { image, status };

  review.mutate(
    { id: image.id, review_status: status },
    {
      onError: (error) => {
        const message = `${errorMessage(error, 'The verdict could not be saved.')} ${vehicleName(image)} is back in the queue.`;
        failure.value = message;
        showToast(message, 'error');
        if (lastVerdict.value?.image.id === image.id) lastVerdict.value = null;
      },
    },
  );
}

/** Set by undo; the queue moves to this image once it is back in the list. */
const returning = ref<number | null>(null);

watch(images, (list) => {
  if (returning.value === null) return;

  const index = list.findIndex((image) => image.id === returning.value);
  if (index === -1) return;

  position.value = index;
  returning.value = null;
});

function undo(): void {
  const last = lastVerdict.value;
  if (!last) return;

  lastVerdict.value = null;
  exit.value = 'none';
  returning.value = last.image.id;

  review.mutate(
    { id: last.image.id, review_status: 'pending' },
    {
      onError: (error) => {
        returning.value = null;
        showToast(errorMessage(error, 'The verdict could not be undone.'), 'error');
      },
    },
  );
}

function move(step: number): void {
  exit.value = 'none';
  const next = Math.min(Math.max(0, currentIndex.value + step), images.value.length - 1);
  position.value = next;
}

function select(index: number): void {
  exit.value = 'none';
  position.value = index;
}

function onKeydown(event: KeyboardEvent): void {
  if (event.metaKey || event.ctrlKey || event.altKey || event.defaultPrevented) return;

  // Typing in a field is not a verdict.
  const target = event.target;
  if (target instanceof Element && target.closest('input, textarea, select, [contenteditable="true"]')) return;

  const handlers: Record<string, () => void> = {
    a: () => decide('approved'),
    r: () => decide('rejected'),
    u: undo,
    ArrowRight: () => move(1),
    ArrowDown: () => move(1),
    j: () => move(1),
    ArrowLeft: () => move(-1),
    ArrowUp: () => move(-1),
    k: () => move(-1),
  };

  const handler = handlers[event.key.length === 1 ? event.key.toLowerCase() : event.key];
  if (!handler) return;

  // Arrow keys would otherwise scroll the page as well as move the selection.
  event.preventDefault();
  handler();
}

onMounted(() => window.addEventListener('keydown', onKeydown));
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown));

// The strip follows the selection.
const strip = ref<HTMLElement | null>(null);
watch(currentIndex, async (index) => {
  await nextTick();
  const container = strip.value;
  const thumb = container?.querySelector<HTMLElement>(`[data-index="${index}"]`);
  if (!container || !thumb || typeof container.scrollTo !== 'function') return;

  // Scrolls the strip only. scrollIntoView would also scroll the page, which
  // on a phone yanks the image out from under the reviewer's thumb.
  const left = thumb.offsetLeft - container.offsetLeft;
  if (left < container.scrollLeft || left + thumb.offsetWidth > container.scrollLeft + container.clientWidth) {
    container.scrollTo({ left: left - container.clientWidth / 2 + thumb.offsetWidth / 2, behavior: 'smooth' });
  }
});

const credit = computed(() => (current.value ? byline(current.value.attribution, null) : null));
const title = computed(() => (current.value ? cleanTitle(current.value.title) : null));
const waitingCount = computed(() => waiting.data.value ?? images.value.length);
</script>

<template>
  <div>
    <PageHeader
      title="Review"
      description="Approve the photos that show the right car and reject the rest. Your verdict is kept separately from the machine's checks, so both stay comparable."
    >
      <template #actions>
        <p v-if="!query.isPending.value && images.length > 0" class="text-body text-ink-2" aria-live="polite">
          <span class="type-figure text-section text-ink">{{ waitingCount.toLocaleString('en') }}</span>
          waiting
        </p>
      </template>
    </PageHeader>

    <ErrorBanner v-if="failure" :message="failure" class="mb-4" />

    <ErrorBanner
      v-if="query.isError.value && images.length === 0"
      :message="errorMessage(query.error.value, 'The review queue could not be loaded.')"
      :retry="() => query.refetch()"
    />

    <div v-else-if="query.isPending.value" class="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]" aria-label="Loading the review queue">
      <SkeletonBlock class="aspect-[4/3]" />
      <div class="space-y-3">
        <SkeletonBlock class="h-9 w-3/4 rounded" />
        <SkeletonBlock class="h-5 w-1/2 rounded" />
        <SkeletonBlock class="mt-8 h-12" />
        <SkeletonBlock class="h-12" />
      </div>
    </div>

    <EmptyState
      v-else-if="!current"
      title="Nothing left to review"
      hint="Every image has a verdict. New searches add to this queue as they find images."
      icon="review"
    >
      <div class="flex flex-wrap gap-4">
        <RouterLink :to="{ name: 'library', query: { review: 'approved' } }" class="focus-ring rounded-control font-semibold text-accent-text hover:underline">
          See approved images
        </RouterLink>
        <button v-if="lastVerdict" type="button" class="focus-ring rounded-control font-semibold text-ink-2 hover:text-ink" @click="undo">
          Undo the last verdict
        </button>
      </div>
    </EmptyState>

    <section v-else aria-label="Image under review" class="flex flex-col gap-5">
      <div class="grid items-stretch gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div class="relative overflow-hidden rounded-surface border border-line bg-[#010413]">
          <Transition :name="`exit-${exit}`" mode="out-in">
            <div :key="current.id" class="aspect-[4/3] w-full">
              <CarImage :src="current.source_url" :placeholder="current.thumbnail_url" :alt="vehicleName(current)" fit="contain" eager />
            </div>
          </Transition>
          <p class="absolute top-3 left-3 rounded-full bg-surface/80 px-2.5 py-1 text-micro font-semibold text-ink-2 tabular-nums backdrop-blur-sm">
            {{ currentIndex + 1 }} of {{ images.length }}{{ query.hasNextPage.value ? '+' : '' }}
          </p>
        </div>

        <div class="flex flex-col gap-5">
          <div>
            <h2 class="type-display text-title break-words text-ink">{{ vehicleName(current) }}</h2>
            <p v-if="title" class="mt-2 text-meta break-words text-ink-2">{{ title }}</p>
            <p v-if="credit" class="mt-1 text-meta break-words text-ink-3">{{ credit }}</p>
          </div>

          <div>
            <p class="mb-2 text-meta font-medium text-ink-2">What the machine found</p>
            <div class="flex flex-wrap gap-1.5">
              <VerdictBadge kind="make" :value="current.make_confirmed" />
              <VerdictBadge kind="year" :value="current.year_confirmed" />
            </div>
          </div>

          <div class="mt-auto flex flex-col gap-2">
            <BaseButton size="lg" icon="check" block @click="decide('approved')">
              <span class="flex-1 text-left">Approve</span>
              <kbd class="rounded border border-accent-fg/25 px-1.5 text-micro font-semibold" aria-hidden="true">A</kbd>
            </BaseButton>
            <BaseButton size="lg" icon="x" variant="danger" block @click="decide('rejected')">
              <span class="flex-1 text-left">Reject</span>
              <kbd class="rounded border border-danger-text/30 px-1.5 text-micro font-semibold" aria-hidden="true">R</kbd>
            </BaseButton>

            <p class="mt-1 min-h-5 text-meta text-ink-3" aria-live="polite">
              <template v-if="lastVerdict">
                {{ lastVerdict.status === 'approved' ? 'Approved' : 'Rejected' }} {{ vehicleName(lastVerdict.image) }}.
                <button type="button" class="focus-ring rounded font-semibold text-ink-2 underline-offset-4 hover:text-ink hover:underline" @click="undo">
                  Undo
                </button>
              </template>
            </p>
          </div>

          <div class="flex items-center justify-between border-t border-line pt-3 text-meta text-ink-3">
            <span>
              <kbd class="rounded border border-line-strong px-1 text-micro">←</kbd>
              <kbd class="rounded border border-line-strong px-1 text-micro">→</kbd>
              to move, <kbd class="rounded border border-line-strong px-1 text-micro">U</kbd> to undo
            </span>
            <RouterLink :to="{ name: 'image', params: { id: current.id } }" class="focus-ring rounded font-semibold text-ink-2 hover:text-ink hover:underline">
              Details
            </RouterLink>
          </div>
        </div>
      </div>

      <nav aria-label="Review queue">
        <ol ref="strip" class="relative flex snap-x gap-2 overflow-x-auto pb-2 [scrollbar-width:thin]">
          <li v-for="(image, index) in images" :key="image.id" :data-index="index" class="shrink-0 snap-start">
            <button
              type="button"
              class="focus-ring relative block h-16 w-24 overflow-hidden rounded-control border-2 transition-[border-color,opacity] sm:h-20 sm:w-28"
              :class="index === currentIndex ? 'border-accent' : 'border-transparent opacity-60 hover:opacity-100'"
              :aria-current="index === currentIndex ? 'true' : undefined"
              :aria-label="`${index + 1}: ${vehicleName(image)}`"
              @click="select(index)"
            >
              <CarImage :src="image.thumbnail_url ?? image.source_url" alt="" />
            </button>
          </li>
          <li v-if="query.isFetchingNextPage.value" class="shrink-0">
            <SkeletonBlock class="h-16 w-24 rounded-control sm:h-20 sm:w-28" />
          </li>
        </ol>
      </nav>
    </section>
  </div>
</template>

<style scoped>
/*
 * The verdict leaves in the direction of its meaning - approved up and away,
 * rejected down and aside - tinted for a beat. Moving between images without a
 * verdict just cross-fades.
 */
.exit-approve-leave-active,
.exit-reject-leave-active {
  transition:
    transform 200ms cubic-bezier(0.4, 0, 1, 1),
    opacity 200ms ease-in,
    filter 200ms ease-in;
}
.exit-approve-leave-to {
  transform: translateY(-6%) scale(0.96);
  opacity: 0;
  filter: sepia(1) hue-rotate(80deg) saturate(2.5);
}
.exit-reject-leave-to {
  transform: translateX(-8%) rotate(-1.5deg) scale(0.96);
  opacity: 0;
  filter: sepia(1) hue-rotate(-40deg) saturate(3);
}
.exit-approve-enter-active,
.exit-reject-enter-active,
.exit-none-enter-active,
.exit-none-leave-active {
  transition: opacity 160ms ease-out;
}
.exit-approve-enter-from,
.exit-reject-enter-from,
.exit-none-enter-from,
.exit-none-leave-to {
  opacity: 0;
}
</style>
