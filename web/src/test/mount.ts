import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query';
import { flushPromises, mount } from '@vue/test-utils';
import { createApp, defineComponent, h } from 'vue';
import type { App } from 'vue';
import { createMemoryHistory, RouterView } from 'vue-router';

import ToastHost from '@/components/ToastHost.vue';
import { createAppRouter } from '@/router';

export function testQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: Infinity, staleTime: Infinity },
      mutations: { retry: false },
    },
  });
}

const mountedApps: App[] = [];

export function unmountSetups(): void {
  while (mountedApps.length) mountedApps.pop()?.unmount();
}

/** Runs a composable inside a real component setup, with Vue Query installed. */
export function withSetup<T>(composable: () => T, queryClient = testQueryClient()) {
  let result!: T;

  const app = createApp(
    defineComponent({
      setup() {
        result = composable();

        return () => h('div');
      },
    }),
  );

  app.use(VueQueryPlugin, { queryClient });
  app.mount(document.createElement('div'));
  mountedApps.push(app);

  return { result, app, queryClient };
}

/** Mounts the whole app at `path`: real router, guards, shell and pages. The caller mocks fetch. */
export async function mountAt(path: string, queryClient = testQueryClient()) {
  const router = createAppRouter(createMemoryHistory());
  const Root = defineComponent({ render: () => h('div', [h(RouterView), h(ToastHost)]) });

  await router.push(path);
  await router.isReady();

  const wrapper = mount(Root, {
    attachTo: document.body,
    global: { plugins: [router, [VueQueryPlugin, { queryClient }]] },
  });

  // Lazy route components resolve over a few ticks.
  await flushPromises();

  return { wrapper, router, queryClient };
}

/** Polls until `check` stops throwing - for UI that settles over several ticks. */
export async function waitFor(check: () => void, timeout = 1500): Promise<void> {
  const started = Date.now();

  for (;;) {
    try {
      check();

      return;
    } catch (error) {
      if (Date.now() - started > timeout) throw error;
      await flushPromises();
      await new Promise((resolve) => setTimeout(resolve, 10));
    }
  }
}
