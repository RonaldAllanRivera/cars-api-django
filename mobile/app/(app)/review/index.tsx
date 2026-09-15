import { Text } from 'react-native';

import { useReviewImage } from '@/api/hooks/useReviewImage';
import { useReviewQueueImages } from '@/api/hooks/useReviewQueueImages';
import type { Image as CarImage } from '@/api/schemas';
import { ErrorBanner } from '@/ui/ErrorBanner';
import { InfiniteGrid } from '@/ui/InfiniteGrid';
import { PageTitle } from '@/ui/PageTitle';
import { ReviewCard } from '@/ui/ReviewCard';
import { Screen } from '@/ui/Screen';

export default function ReviewQueue() {
  // The queue is exactly the images no human has ruled on yet - and stays
  // that way the instant a verdict lands, not just after the next refetch:
  // see useReviewQueueImages for why the filtering has to happen here.
  const query = useReviewQueueImages();
  const review = useReviewImage();

  return (
    <Screen>
      <PageTitle title="Review queue - Cars Images" />
      <Text className="mb-3 text-meta text-text-secondary">
        Your verdict is recorded separately from the machine&apos;s, so both stay comparable.
      </Text>

      {review.isError ? (
        <ErrorBanner
          message={
            review.error instanceof Error
              ? `${review.error.message}. The card has been put back.`
              : 'The verdict could not be saved. The card has been put back.'
          }
        />
      ) : null}

      <InfiniteGrid
        query={query}
        keyExtractor={(image) => String(image.id)}
        emptyTitle="Nothing left to review"
        emptyHint="Every image has a verdict."
        renderItem={(image: CarImage) => (
          <ReviewCard
            image={image}
            // Scoped to the card whose verdict is in flight: a bare
            // `review.isPending` would freeze every card in the queue.
            pending={review.isPending && review.variables?.id === image.id}
            onApprove={() => review.mutate({ id: image.id, review_status: 'approved' })}
            onReject={() => review.mutate({ id: image.id, review_status: 'rejected' })}
          />
        )}
      />
    </Screen>
  );
}
