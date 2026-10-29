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

// Log in through the login page, and collect errors in the browser console (the test checks they are empty)
export async function login(page: Page, name: string, pin = PIN): Promise<string[]> {
    const errors: string[] = [];
    page.on('pageerror', e => errors.push(String(e)));
    page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
    page.on('dialog', d => d.accept());
    await page.goto('/login');
    await page.getByRole('button', { name, exact: true }).click();
    await page.locator('#pin').fill(pin);
    await page.locator('button[type=submit]').click();
    await expect(page.getByRole('button', { name: /log out|abmelden/i })).toBeVisible();
    return errors;
}
