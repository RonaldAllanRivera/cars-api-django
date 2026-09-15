import { onScopeDispose, ref, watch } from 'vue';

/**
 * Calls `onVisible` whenever the returned element scrolls into view.
 * Degrades to nothing where IntersectionObserver is missing (jsdom, very old
 * browsers) - the visible "Load more" button still works there.
 */
export function useInfiniteScroll(onVisible: () => void, rootMargin = '600px') {
  const sentinel = ref<HTMLElement | null>(null);
  let observer: IntersectionObserver | null = null;

  watch(
    sentinel,
    (element) => {
      observer?.disconnect();
      observer = null;

      if (!element || typeof IntersectionObserver === 'undefined') return;

      observer = new IntersectionObserver(
        (entries) => {
          if (entries.some((entry) => entry.isIntersecting)) onVisible();
        },
        { rootMargin },
      );
      observer.observe(element);
    },
    { flush: 'post' },
  );

  onScopeDispose(() => observer?.disconnect());

  return sentinel;
}
