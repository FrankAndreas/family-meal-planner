import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
  },
  {
    // The React side (pages, components, hooks) gets its data through the modules in src (plan.ts, recipes.ts, ...),
    // never an HTTP client itself: one place per backend route, and its types next to it
    files: ['src/**/*.tsx', 'src/hooks/**'],
    rules: {
      'no-restricted-imports': [
        'error',
        {
          paths: [{ name: 'axios', allowTypeImports: true, message: 'Call the backend through a module in src.' }],
          patterns: [
            {
              regex: '(^|/)api(\\.ts)?$',
              importNames: ['default'],
              message: 'Call the backend through a module in src (plan.ts, recipes.ts, ...), not the api client.',
            },
          ],
        },
      ],
      'no-restricted-globals': [
        'error',
        { name: 'fetch', message: 'Call the backend through a module in src (e.g. settings.ts), not fetch.' },
      ],
      'no-restricted-properties': [
        'error',
        { object: 'window', property: 'fetch', message: 'Call the backend through a module in src, not fetch.' },
        { object: 'globalThis', property: 'fetch', message: 'Call the backend through a module in src, not fetch.' },
      ],
    },
  },
])
