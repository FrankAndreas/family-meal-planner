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
    // Pages and components get their data through the modules in src (plan.ts, recipes.ts, ...), never the HTTP
    // client itself: one place per backend route, and its types next to it
    files: ['src/pages/**', 'src/components/**', 'src/AuthContext.tsx'],
    rules: {
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              regex: '^(\\.\\./)+api$|^\\./api$',
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
    },
  },
])
