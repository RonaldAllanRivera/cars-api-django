import { createRouter, createWebHistory } from 'vue-router';
import type { Router, RouteRecordRaw, RouterHistory } from 'vue-router';

import { onSignedOut, restoreSession, useAuth } from '@/auth/auth';

declare module 'vue-router' {
  interface RouteMeta {
    /** Reachable without a session. */
    public?: boolean;
    /** Which sidebar section a route belongs to. */
    section?: 'search' | 'library' | 'pipeline' | 'review' | 'health';
  }
}

export const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/pages/LoginPage.vue'),
    meta: { public: true },
  },
  {
    path: '/',
    component: () => import('@/components/AppShell.vue'),
    children: [
      { path: '', redirect: { name: 'search' } },
      {
        path: 'search',
        name: 'search',
        component: () => import('@/pages/search/SearchPage.vue'),
        meta: { section: 'search' },
      },
      {
        path: 'search/runs/:id(\\d+)',
        name: 'run',
        component: () => import('@/pages/search/RunPage.vue'),
        props: (route) => ({ id: Number(route.params.id) }),
        meta: { section: 'search' },
      },
      {
        path: 'library',
        name: 'library',
        component: () => import('@/pages/library/LibraryPage.vue'),
        meta: { section: 'library' },
      },
      {
        path: 'library/:id(\\d+)',
        name: 'image',
        component: () => import('@/pages/library/ImagePage.vue'),
        props: (route) => ({ id: Number(route.params.id) }),
        meta: { section: 'library' },
      },
      {
        path: 'pipeline',
        name: 'pipeline',
        component: () => import('@/pages/pipeline/PipelinePage.vue'),
        meta: { section: 'pipeline' },
      },
      {
        path: 'pipeline/:id(\\d+)',
        name: 'import',
        component: () => import('@/pages/pipeline/ImportPage.vue'),
        props: (route) => ({ id: Number(route.params.id) }),
        meta: { section: 'pipeline' },
      },
      {
        path: 'review',
        name: 'review',
        component: () => import('@/pages/review/ReviewPage.vue'),
        meta: { section: 'review' },
      },
      {
        path: 'health',
        name: 'health',
        component: () => import('@/pages/health/HealthPage.vue'),
        meta: { section: 'health' },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/pages/NotFoundPage.vue'),
    meta: { public: true },
  },
];

export function createAppRouter(history: RouterHistory = createWebHistory()): Router {
  const router = createRouter({
    history,
    routes,
    scrollBehavior: (_to, _from, saved) => saved ?? { top: 0 },
  });

  router.beforeEach(async (to) => {
    await restoreSession();
    const { isAuthenticated } = useAuth();

    if (to.name === 'login' && isAuthenticated.value) {
      return { name: 'search' };
    }

    if (!to.meta.public && !isAuthenticated.value) {
      return { name: 'login', query: to.fullPath === '/' ? {} : { redirect: to.fullPath } };
    }

    return true;
  });

  // A 401 anywhere, or signing out, lands on the login page with a way back.
  onSignedOut(() => {
    const current = router.currentRoute.value;
    if (current.meta.public) return;

    void router.replace({ name: 'login', query: { redirect: current.fullPath } });
  });

  return router;
}
