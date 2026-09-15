import { toValue, watchEffect } from 'vue';
import type { MaybeRefOrGetter } from 'vue';

import { APP_NAME } from '@/config';

export function useDocumentTitle(title: MaybeRefOrGetter<string | null | undefined>): void {
  watchEffect(() => {
    const value = toValue(title);
    document.title = value ? `${value} - ${APP_NAME}` : APP_NAME;
  });
}
