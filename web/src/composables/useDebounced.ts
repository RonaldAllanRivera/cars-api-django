import { onScopeDispose, ref, watch } from 'vue';
import type { Ref } from 'vue';

/**
 * A copy of `source` that only updates once it has been still for `delay` ms.
 * The raw value drives the input; the settled value drives the query, so a
 * typed word is one request rather than one per keystroke.
 */
export function useDebounced<T>(source: Ref<T>, delay = 300): Ref<T> {
  const settled = ref(source.value) as Ref<T>;
  let timer: ReturnType<typeof setTimeout> | undefined;

  watch(source, (value) => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      settled.value = value;
    }, delay);
  });

  onScopeDispose(() => clearTimeout(timer));

  return settled;
}
