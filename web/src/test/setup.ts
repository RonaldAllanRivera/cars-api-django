import { enableAutoUnmount } from '@vue/test-utils';
import { afterEach, beforeEach } from 'vitest';

import { queryClient } from '@/api/queryClient';
import { resetAuthForTests } from '@/auth/auth';
import { clearToastsForTests } from '@/composables/useToast';
import { unmountSetups } from '@/test/mount';

// jsdom does not implement scrolling; the router's scrollBehavior calls it.
window.scrollTo = () => {};

beforeEach(() => {
  window.localStorage.clear();
  resetAuthForTests();
  clearToastsForTests();
});

enableAutoUnmount(afterEach);

afterEach(() => {
  unmountSetups();
  queryClient.clear();
  document.body.innerHTML = '';
});
