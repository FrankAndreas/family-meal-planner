import { defineConfig, devices } from '@playwright/test';
import path from 'node:path';
import { PYTHON as python } from './tests/helpers';

// The tests start their own family hub (from a family-hub checkout: logins and people, Admin PIN 1111), backend
// (fresh SQLite database) and frontend on ports of their own, so a dev server on 8000/5173 and its data are never
// touched. E2E_PYTHON: the Python with the backend's packages. HUB_DIR: a family-hub checkout (default: next to this
// repo); HUB_PYTHON: the Python with the hub's packages (default: E2E_PYTHON).
export const BACKEND = 'http://localhost:8100';
export const FRONTEND = 'http://localhost:3100';
export const HUB = 'http://localhost:8130';
const database = path.resolve(__dirname, '.tmp', 'e2e.db');
const hubData = path.resolve(__dirname, '.tmp', 'hub');
const hubDir = path.resolve(process.env.HUB_DIR ?? path.join(__dirname, '..', '..', 'family-hub'));
const hubPython = process.env.HUB_PYTHON ? path.resolve(process.env.HUB_PYTHON) : python;

export default defineConfig({
    testDir: './tests',
    // One backend and database for all tests; each test works with people of its own
    workers: 1,
    retries: process.env.CI ? 1 : 0,
    reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
    use: {
        baseURL: FRONTEND,
        // The tests find elements by their English texts (one test switches to German itself)
        locale: 'en-US',
        trace: 'retain-on-failure',
        screenshot: 'only-on-failure',
    },
    projects: [
        // The Friday planning happens on an iPad-sized screen in landscape
        { name: 'tablet', testIgnore: /plan-phone\.spec\.ts/, use: { ...devices['Desktop Chrome'], viewport: { width: 1180, height: 820 }, hasTouch: true } },
        { name: 'phone', use: { ...devices['Pixel 7'] }, testMatch: /(login|plan-phone)\.spec\.ts/ },
    ],
    webServer: [
        {
            command: `rm -rf "${hubData}" && mkdir -p "${hubData}" && "${hubPython}" -m uvicorn app.main:app --port 8130`,
            cwd: path.join(hubDir, 'backend'),
            url: `${HUB}/health`,
            env: {
                DATABASE_URL: `sqlite:///${hubData}/hub.db`,
                DATA_DIR: hubData,
                INITIAL_ADMIN_PIN: '1111',
                DEFAULT_LANGUAGE: 'en',
                // Plain http in the tests: a Secure cookie would never come back
                COOKIE_INSECURE: '1',
            },
            reuseExistingServer: false,
            timeout: 60_000,
        },
        {
            command: `mkdir -p "${path.dirname(database)}" && rm -f "${database}" && "${python}" -m uvicorn app.main:app --port 8100`,
            cwd: path.resolve(__dirname, '..', 'backend'),
            url: `${BACKEND}/health`,
            env: {
                DATABASE_URL: `sqlite:///${database}`,
                DATA_DIR: path.dirname(database),
                HUB_URL: HUB,
                HUB_PUBLIC_URL: HUB,
                DEFAULT_LANGUAGE: 'en',
                // Recipe mails as the Cloudflare Email Worker delivers them, and a fake AI (never the real service)
                INBOUND_SECRET: 'e2e-inbound',
                AI_FAKE: '1',
                INFOMANIAK_AI_TOKEN: 'fake',
                INFOMANIAK_AI_PRODUCT_ID: 'fake',
            },
            reuseExistingServer: false,
            timeout: 60_000,
        },
        {
            command: 'npx vite --port 3100 --strictPort',
            cwd: path.resolve(__dirname, '..', 'frontend'),
            url: FRONTEND,
            // Vite forwards /api to the test backend, so the hub's cookie is the page's own (as with nginx)
            env: { API_PROXY: BACKEND },
            reuseExistingServer: false,
            timeout: 60_000,
        },
    ],
});
