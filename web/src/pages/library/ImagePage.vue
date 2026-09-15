<script setup lang="ts">
import { computed } from 'vue';
import { RouterLink, useRouter } from 'vue-router';

import { errorMessage } from '@/api/client';
import { useImage } from '@/api/composables/useImages';
import { useReviewImage } from '@/api/composables/useReviewImage';
import type { ReviewStatus } from '@/api/schemas';
import { useAuth } from '@/auth/auth';
import BaseButton from '@/components/BaseButton.vue';
import CarImage from '@/components/CarImage.vue';
import ErrorBanner from '@/components/ErrorBanner.vue';
import Icon from '@/components/Icon.vue';
import SkeletonBlock from '@/components/SkeletonBlock.vue';
import StatusBadge from '@/components/StatusBadge.vue';
import VerdictBadge from '@/components/VerdictBadge.vue';
import { useDocumentTitle } from '@/composables/useDocumentTitle';
import { showToast } from '@/composables/useToast';
import { cleanTitle } from '@/format/imageTitle';
import { vehicleName } from '@/format/labels';
import { formatDateTime } from '@/format/time';

const props = defineProps<{ id: number }>();

const router = useRouter();
const { can } = useAuth();
const query = useImage(() => props.id);
const review = useReviewImage();

const image = computed(() => query.data.value);
const name = computed(() => (image.value ? vehicleName(image.value) : 'Image'));
useDocumentTitle(name);

const details = computed(() => {
  const current = image.value;
  if (!current) return [];

  return [
    { label: 'Title', value: cleanTitle(current.title) },
    { label: 'Description', value: current.description },
    { label: 'Licence', value: current.license },
    { label: 'Attribution', value: current.attribution },
    { label: 'Dimensions', value: current.width && current.height ? `${current.width} × ${current.height} px` : null },
    { label: 'Colour', value: current.color },
    { label: 'Reviewed', value: formatDateTime(current.reviewed_at) },
    { label: 'Found', value: formatDateTime(current.created_at) },
  ].filter((row): row is { label: string; value: string } => Boolean(row.value));
});

function goBack(): void {
  // Back to wherever the card was - a filtered library or a run - when there is one.
  if (window.history.state?.back) router.back();
  else void router.push({ name: 'library' });
}

async function setVerdict(status: ReviewStatus): Promise<void> {
  try {
    await review.mutateAsync({ id: props.id, review_status: status });
    showToast(status === 'pending' ? 'Verdict cleared.' : status === 'approved' ? 'Approved.' : 'Rejected.');
  } catch (caught) {
    showToast(`${errorMessage(caught, 'The verdict could not be saved.')} Nothing was changed.`, 'error');
  }
}
</script>

<template>
  <div>
    <button
      type="button"
      class="focus-ring mb-4 inline-flex items-center gap-1 rounded-control text-meta font-medium text-ink-2 hover:text-ink"
      @click="goBack"
    >
      <Icon name="arrowLeft" :size="16" />
      Back
    </button>

    <div v-if="query.isPending.value" class="grid gap-8 lg:grid-cols-[minmax(0,1fr)_22rem]" aria-label="Loading image">
      <SkeletonBlock class="aspect-[4/3]" />
      <div class="space-y-3">
        <SkeletonBlock class="h-9 w-3/4 rounded" />
        <SkeletonBlock class="h-6 w-1/2 rounded" />
        <SkeletonBlock class="h-40" />
      </div>
    </div>

    <ErrorBanner v-else-if="query.isError.value || !image" :message="errorMessage(query.error.value, 'This image could not be loaded.')" :retry="() => query.refetch()" />

    <article v-else class="grid items-start gap-8 lg:grid-cols-[minmax(0,1fr)_22rem]">
      <figure class="overflow-hidden rounded-surface border border-line bg-sunken">
        <div class="aspect-[4/3] max-h-[78dvh] w-full">
          <CarImage :src="image.source_url" :placeholder="image.thumbnail_url" :alt="name" fit="contain" eager />
        </div>
      </figure>

      <div class="flex flex-col gap-6">
        <div>
          <h1 class="type-display text-title break-words text-ink">{{ name }}</h1>
          <div class="mt-3 flex flex-wrap gap-1.5">
            <StatusBadge :status="image.review_status" />
            <StatusBadge :status="image.download_status" />
            <VerdictBadge kind="make" :value="image.make_confirmed" />
            <VerdictBadge kind="year" :value="image.year_confirmed" />
          </div>
        </div>

        <section v-if="can('review:write')" aria-labelledby="verdict-heading" class="rounded-surface border border-line bg-raised p-4">
          <h2 id="verdict-heading" class="text-meta font-medium text-ink-2">Your verdict</h2>
          <div class="mt-3 flex flex-wrap gap-2">
            <BaseButton
              size="sm"
              icon="check"
              variant="secondary"
              :disabled="review.isPending.value || image.review_status === 'approved'"
              @click="setVerdict('approved')"
            >
              {{ image.review_status === 'approved' ? 'Approved' : 'Approve' }}
            </BaseButton>
            <BaseButton
              size="sm"
              icon="x"
              variant="danger"
              :disabled="review.isPending.value || image.review_status === 'rejected'"
              @click="setVerdict('rejected')"
            >
              {{ image.review_status === 'rejected' ? 'Rejected' : 'Reject' }}
            </BaseButton>
            <BaseButton
              v-if="image.review_status !== 'pending'"
              size="sm"
              icon="undo"
              variant="ghost"
              :disabled="review.isPending.value"
              @click="setVerdict('pending')"
            >
              Clear
            </BaseButton>
          </div>
        </section>

        <dl class="divide-y divide-line border-y border-line">
          <div v-for="row in details" :key="row.label" class="grid grid-cols-[6.5rem_1fr] gap-3 py-2.5">
            <dt class="text-meta text-ink-3">{{ row.label }}</dt>
            <dd class="text-meta break-words text-ink">{{ row.value }}</dd>
          </div>
        </dl>

        <div class="flex flex-wrap gap-x-5 gap-y-2">
          <a
            :href="image.source_url"
            target="_blank"
            rel="noopener noreferrer"
            class="focus-ring inline-flex items-center gap-1.5 rounded-control text-meta font-semibold text-accent-text hover:underline"
          >
            Open the original
            <Icon name="external" :size="14" />
          </a>
          <RouterLink
            v-if="image.car_search_id"
            :to="{ name: 'run', params: { id: image.car_search_id } }"
            class="focus-ring rounded-control text-meta font-semibold text-ink-2 hover:text-ink hover:underline"
          >
            See the run that found it
          </RouterLink>
        </div>
      </div>
    </article>
  </div>
</template>
