<script setup lang="ts">
import { computed } from 'vue';
import { RouterLink, RouterView, useRoute } from 'vue-router';

import { useImageCount } from '@/api/composables/useImages';
import { useAuth } from '@/auth/auth';
import { APP_NAME } from '@/config';

import Icon from './Icon.vue';
import type { IconName } from './Icon.vue';

const route = useRoute();
const { user, signOut, can } = useAuth();

type Section = 'search' | 'library' | 'pipeline' | 'review' | 'health';

const NAV: { section: Section; label: string; icon: IconName; ability: Parameters<typeof can>[0] }[] = [
  { section: 'search', label: 'Search', icon: 'search', ability: 'search:read' },
  { section: 'library', label: 'Library', icon: 'images', ability: 'search:read' },
  { section: 'pipeline', label: 'Pipeline', icon: 'layers', ability: 'imports:read' },
  { section: 'review', label: 'Review', icon: 'review', ability: 'review:write' },
  { section: 'health', label: 'Health', icon: 'pulse', ability: 'errors:read' },
];

// A tab that can only 403 is worse than no tab.
const items = computed(() => NAV.filter((item) => can(item.ability)));
const active = computed(() => route.meta.section);

// The one number worth carrying in the chrome: how much is waiting for a person.
const pending = useImageCount({ review_status: 'pending' }, () => can('review:write'));
const pendingLabel = computed(() => {
  const count = pending.data.value;
  if (!count) return null;

  return count > 999 ? '999+' : String(count);
});

const initials = computed(() =>
  (user.value?.name ?? '')
    .split(/\s+/)
    .map((part) => part.charAt(0))
    .join('')
    .slice(0, 2)
    .toUpperCase(),
);
</script>

<template>
  <div class="min-h-dvh md:grid md:grid-cols-[15rem_1fr]">
    <a
      href="#main"
      class="sr-only z-50 rounded-control bg-accent px-3 py-2 font-semibold text-accent-fg focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
    >
      Skip to content
    </a>

    <!-- Sidebar: tablet and up. -->
    <aside class="sticky top-0 hidden h-dvh flex-col border-r border-line bg-raised md:flex">
      <RouterLink to="/search" class="focus-ring mx-3 mt-5 mb-8 flex items-center gap-2.5 rounded-control px-2 py-1">
        <span class="grid size-8 place-items-center rounded-control bg-accent text-accent-fg">
          <svg viewBox="0 0 32 32" class="size-6" aria-hidden="true">
            <path
              d="M7 19.5 9.6 13a3 3 0 0 1 2.8-1.9h7.2a3 3 0 0 1 2.8 1.9L25 19.5V23a1 1 0 0 1-1 1h-2a1 1 0 0 1-1-1v-1H11v1a1 1 0 0 1-1 1H8a1 1 0 0 1-1-1z"
              fill="currentColor"
            />
          </svg>
        </span>
        <span class="type-display text-[17px] leading-5 text-ink">{{ APP_NAME }}</span>
      </RouterLink>

      <nav aria-label="Main" class="flex-1 px-3">
        <ul class="flex flex-col gap-0.5">
          <li v-for="item in items" :key="item.section">
            <RouterLink
              :to="{ name: item.section }"
              :aria-current="active === item.section ? 'page' : undefined"
              class="focus-ring relative flex h-10 items-center gap-3 rounded-control px-3 text-body font-medium transition-colors"
              :class="active === item.section ? 'bg-sunken text-ink' : 'text-ink-2 hover:bg-sunken/50 hover:text-ink'"
            >
              <span
                v-if="active === item.section"
                class="absolute top-2 bottom-2 -left-3 w-[3px] rounded-r-full bg-accent"
                aria-hidden="true"
              />
              <Icon :name="item.icon" :class="active === item.section ? 'text-accent-text' : ''" />
              <span class="flex-1">{{ item.label }}</span>
              <span
                v-if="item.section === 'review' && pendingLabel"
                class="rounded-full bg-sunken px-2 py-0.5 text-micro font-semibold text-ink tabular-nums ring-1 ring-line-strong"
              >
                {{ pendingLabel }}<span class="sr-only"> waiting</span>
              </span>
            </RouterLink>
          </li>
        </ul>
      </nav>

      <div class="border-t border-line p-3">
        <div class="flex items-center gap-3 px-2 py-2">
          <span class="grid size-8 shrink-0 place-items-center rounded-full bg-sunken text-micro font-semibold text-ink-2" aria-hidden="true">
            {{ initials }}
          </span>
          <div class="min-w-0 flex-1">
            <p class="truncate text-meta font-semibold text-ink">{{ user?.name }}</p>
            <p class="truncate text-micro text-ink-3">{{ user?.email }}</p>
          </div>
          <button
            type="button"
            class="focus-ring rounded-control p-2 text-ink-3 hover:bg-sunken hover:text-ink"
            aria-label="Sign out"
            title="Sign out"
            @click="signOut()"
          >
            <Icon name="logout" :size="18" />
          </button>
        </div>
      </div>
    </aside>

    <!-- Top bar: phones. -->
    <header class="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-line bg-raised/95 px-4 backdrop-blur md:hidden">
      <RouterLink to="/search" class="focus-ring flex items-center gap-2 rounded-control">
        <span class="grid size-7 place-items-center rounded-md bg-accent text-accent-fg">
          <svg viewBox="0 0 32 32" class="size-5" aria-hidden="true">
            <path
              d="M7 19.5 9.6 13a3 3 0 0 1 2.8-1.9h7.2a3 3 0 0 1 2.8 1.9L25 19.5V23a1 1 0 0 1-1 1h-2a1 1 0 0 1-1-1v-1H11v1a1 1 0 0 1-1 1H8a1 1 0 0 1-1-1z"
              fill="currentColor"
            />
          </svg>
        </span>
        <span class="type-display text-[16px] text-ink">{{ APP_NAME }}</span>
      </RouterLink>
      <button
        type="button"
        class="focus-ring flex items-center gap-1.5 rounded-control px-2 py-1.5 text-meta font-medium text-ink-2 hover:text-ink"
        @click="signOut()"
      >
        <Icon name="logout" :size="16" />
        Sign out
      </button>
    </header>

    <main id="main" tabindex="-1" class="min-w-0 px-4 pt-6 pb-28 focus:outline-none sm:px-6 md:px-10 md:pt-10 md:pb-16">
      <div class="mx-auto max-w-[76rem]">
        <RouterView v-slot="{ Component }">
          <component :is="Component" :key="route.path" />
        </RouterView>
      </div>
    </main>

    <!-- Bottom tabs: phones. -->
    <nav
      aria-label="Main"
      class="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-raised/95 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden"
    >
      <ul class="grid" :style="{ gridTemplateColumns: `repeat(${items.length}, minmax(0, 1fr))` }">
        <li v-for="item in items" :key="item.section">
          <RouterLink
            :to="{ name: item.section }"
            :aria-current="active === item.section ? 'page' : undefined"
            class="focus-ring relative flex h-16 flex-col items-center justify-center gap-1 text-micro font-medium"
            :class="active === item.section ? 'text-accent-text' : 'text-ink-2'"
          >
            <Icon :name="item.icon" :size="22" />
            {{ item.label }}
            <span
              v-if="item.section === 'review' && pendingLabel"
              class="absolute top-2 left-1/2 ml-2 rounded-full bg-accent px-1.5 text-[10px] leading-4 font-bold text-accent-fg tabular-nums"
            >
              {{ pendingLabel }}<span class="sr-only"> waiting</span>
            </span>
          </RouterLink>
        </li>
      </ul>
    </nav>
  </div>
</template>
