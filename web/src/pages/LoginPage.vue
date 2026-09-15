<script setup lang="ts">
import { ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { ApiValidationError, errorMessage } from '@/api/client';
import { useAuth } from '@/auth/auth';
import BaseButton from '@/components/BaseButton.vue';
import ErrorBanner from '@/components/ErrorBanner.vue';
import TextField from '@/components/TextField.vue';
import { useDocumentTitle } from '@/composables/useDocumentTitle';
import { APP_NAME } from '@/config';

useDocumentTitle('Sign in');

const route = useRoute();
const router = useRouter();
const { signIn, state } = useAuth();

const email = ref('');
const password = ref('');
const busy = ref(false);
const error = ref<string | null>(null);
const fieldErrors = ref<{ email?: string; password?: string }>({});

/** Only same-app paths: an open redirect on the login page is a phishing aid. */
function safeRedirect(): string {
  const target = route.query.redirect;

  return typeof target === 'string' && target.startsWith('/') && !target.startsWith('//') ? target : '/search';
}

async function submit(): Promise<void> {
  error.value = null;
  fieldErrors.value = {};

  if (!email.value.trim() || !password.value) {
    fieldErrors.value = {
      email: email.value.trim() ? undefined : 'Enter your email address.',
      password: password.value ? undefined : 'Enter your password.',
    };

    return;
  }

  busy.value = true;

  try {
    await signIn(email.value.trim(), password.value);
    await router.replace(safeRedirect());
  } catch (caught) {
    if (caught instanceof ApiValidationError) {
      // Usually "These credentials do not match our records." - which is about
      // the pair, so it reads better above the form than under one field.
      error.value = caught.first('email') ?? caught.message;
      fieldErrors.value = { password: caught.first('password') };
    } else {
      error.value = errorMessage(caught, 'Sign in failed. Try again.');
    }
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <main class="grid min-h-dvh lg:grid-cols-[1.1fr_1fr]">
    <section class="relative hidden overflow-hidden border-r border-line bg-raised lg:flex lg:flex-col lg:justify-between lg:p-12">
      <div class="flex items-center gap-2.5">
        <span class="grid size-9 place-items-center rounded-control bg-accent text-accent-fg">
          <svg viewBox="0 0 32 32" class="size-7" aria-hidden="true">
            <path
              d="M7 19.5 9.6 13a3 3 0 0 1 2.8-1.9h7.2a3 3 0 0 1 2.8 1.9L25 19.5V23a1 1 0 0 1-1 1h-2a1 1 0 0 1-1-1v-1H11v1a1 1 0 0 1-1 1H8a1 1 0 0 1-1-1z"
              fill="currentColor"
            />
          </svg>
        </span>
        <span class="type-display text-[18px] text-ink">{{ APP_NAME }}</span>
      </div>

      <div>
        <p class="type-display max-w-[14ch] text-[clamp(2.75rem,4.8vw,4.5rem)] leading-[0.95] text-ink">
          Every make, model and year, photographed.
        </p>
        <p class="mt-6 max-w-[46ch] text-body text-ink-2">
          Search Wikimedia Commons one car at a time or a whole CSV at once, check what came back,
          and export the approved set.
        </p>
      </div>

      <ol class="grid grid-cols-4 gap-4 border-t border-line pt-6 text-meta text-ink-2">
        <li><span class="block type-figure text-section text-accent-text">1</span>Import</li>
        <li><span class="block type-figure text-section text-accent-text">2</span>Harvest</li>
        <li><span class="block type-figure text-section text-accent-text">3</span>Review</li>
        <li><span class="block type-figure text-section text-accent-text">4</span>Export</li>
      </ol>
    </section>

    <section class="flex items-center justify-center px-4 py-12 sm:px-8">
      <div class="w-full max-w-sm">
        <h1 class="type-display text-title text-ink">Sign in</h1>
        <p class="mt-2 text-body text-ink-2">Credentials are issued on request. There is no demo account.</p>

        <form class="mt-8 flex flex-col gap-5" novalidate @submit.prevent="submit">
          <ErrorBanner v-if="error" :message="error" />
          <p
            v-else-if="state.bootError"
            role="status"
            class="rounded-surface border border-line-strong bg-raised px-4 py-3 text-meta text-ink-2"
          >
            {{ state.bootError }}
          </p>

          <TextField
            v-model="email"
            label="Email"
            type="email"
            autocomplete="username"
            inputmode="email"
            autocapitalize="none"
            spellcheck="false"
            :error="fieldErrors.email"
            required
          />
          <TextField
            v-model="password"
            label="Password"
            type="password"
            autocomplete="current-password"
            :error="fieldErrors.password"
            required
          />
          <BaseButton type="submit" size="lg" block :pending="busy">Sign in</BaseButton>
        </form>
      </div>
    </section>
  </main>
</template>
