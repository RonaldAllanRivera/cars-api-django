import { fileURLToPath, URL } from 'node:url';

import tailwindcss from '@tailwindcss/vite';
import vue from '@vitejs/plugin-vue';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  build: {
    // The router lazy-loads each page, so the entry chunk only has to carry
    // the shell, the API layer and Vue itself.
    target: 'es2022',
    rollupOptions: {
      output: {
        // Named, stable vendor chunks: they change far less often than the app,
        // so a deploy does not bust the browser's cache for all of them.
        advancedChunks: {
          groups: [
            { name: 'vue', test: /node_modules[\\/](@vue|vue|vue-router)[\\/]/ },
            { name: 'query', test: /node_modules[\\/]@tanstack[\\/]/ },
            { name: 'zod', test: /node_modules[\\/]zod[\\/]/ },
          ],
        },
      },
    },
  },
});
