import { defineConfigWithVueTs, vueTsConfigs } from '@vue/eslint-config-typescript';
import pluginVue from 'eslint-plugin-vue';

export default defineConfigWithVueTs(
  { name: 'app/files-to-lint', files: ['**/*.{ts,mts,vue}'] },
  { name: 'app/ignores', ignores: ['dist/**', 'coverage/**', 'node_modules/**'] },
  pluginVue.configs['flat/recommended'],
  vueTsConfigs.recommended,
  {
    name: 'app/test-helpers',
    files: ['src/test/**'],
    rules: { 'vue/one-component-per-file': 'off' },
  },
  {
    name: 'app/rules',
    rules: {
      // Formatting is not what lint is for here; these fight readable templates.
      'vue/max-attributes-per-line': 'off',
      'vue/singleline-html-element-content-newline': 'off',
      'vue/html-self-closing': 'off',
      'vue/multi-word-component-names': 'off',
      // Optional TypeScript props are undefined by default; a default adds nothing.
      'vue/require-default-prop': 'off',
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
    },
  },
);
