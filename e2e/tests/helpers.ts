import path from 'node:path';
import { expect, type APIRequestContext, type Page } from '@playwright/test';

// The Python with the backend's packages; a path is made absolute (Python warns about relative ones with "..")
const configured = process.env.E2E_PYTHON ?? 'python3';
export const PYTHON = configured.includes('/') ? path.resolve(configured) : configured;

export const API = 'http://localhost:8100/api';
export const ADMIN_PIN = '1111';
export const PIN = '2468';

export interface Person { name: string; token: string }

export const uniqueName = (prefix: string) => `${prefix}${Date.now().toString(36).slice(-4)}${Math.random().toString(36).slice(2, 5)}`;

export async function token(request: APIRequestContext, name: string, pin: string): Promise<string> {
    const response = await request.post(`${API}/token`, { data: { name, pin } });
    expect(response.ok(), await response.text()).toBeTruthy();
    return (await response.json()).access_token;
}

// A person of the test's own, created by Admin through the API
export async function newPerson(request: APIRequestContext, role: 'PARENT' | 'CHILD' = 'PARENT'): Promise<Person> {
    const admin = await token(request, 'Admin', ADMIN_PIN);
    const name = uniqueName(role === 'PARENT' ? 'P' : 'K');
    const created = await request.post(`${API}/users`, {
        data: { name, pin: PIN, role },
        headers: { Authorization: `Bearer ${admin}` },
    });
    expect(created.ok(), await created.text()).toBeTruthy();
    return { name, token: await token(request, name, PIN) };
}

const pageErrors = new WeakMap<Page, string[]>();

// Log in through the login page, and collect errors in the browser console (the test checks they are empty).
// The listeners go on once per page: a test that logs in twice would otherwise accept each dialog twice.
export async function login(page: Page, name: string, pin = PIN): Promise<string[]> {
    let errors = pageErrors.get(page);
    if (!errors) {
        const collected: string[] = [];
        errors = collected;
        pageErrors.set(page, collected);
        page.on('pageerror', e => collected.push(String(e)));
        page.on('console', m => { if (m.type() === 'error') collected.push(m.text()); });
        page.on('dialog', d => d.accept());
    }
    await page.goto('/login');
    await page.getByRole('button', { name, exact: true }).click();
    await page.locator('#pin').fill(pin);
    await page.locator('button[type=submit]').click();
    await expect(page.getByRole('button', { name: /log out|abmelden/i })).toBeVisible();
    return errors;
}

// A recipe made through the API, for tests that are about something else than typing one in
export async function createRecipe(request: APIRequestContext, person: Person, fields: Record<string, unknown> = {}) {
    const response = await request.post(`${API}/recipes`, {
        data: {
            title: uniqueName('Rezept '),
            servings: 4,
            ingredients: [{ amount: 400, unit: 'g', name: 'Hörnli' }],
            steps: ['Kochen'],
            tags: [],
            ...fields,
        },
        headers: { Authorization: `Bearer ${person.token}` },
    });
    expect(response.ok(), await response.text()).toBeTruthy();
    return response.json();
}

// A week of the test's own, far in the future, so tests sharing the database never plan into the same week
export function ownWeek(): string {
    const day = new Date(Date.UTC(2031, 0, 1) + Math.floor(Math.random() * 3000) * 7 * 86_400_000);
    return day.toISOString().slice(0, 10);
}

export async function call<T = any>(
    request: APIRequestContext, person: Person, method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE', path: string, data?: unknown,
): Promise<T> {
    const response = await request.fetch(`${API}${path}`, { method, data, headers: { Authorization: `Bearer ${person.token}` } });
    expect(response.ok(), `${method} ${path}: ${await response.text()}`).toBeTruthy();
    return response.status() === 204 ? (undefined as T) : response.json();
}
