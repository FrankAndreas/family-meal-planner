import fs from 'node:fs';
import path from 'node:path';
import { expect, request as playwrightRequest, type APIRequestContext, type Locator, type Page } from '@playwright/test';

// The Python with the backend's packages; a path is made absolute (Python warns about relative ones with "..")
const configured = process.env.E2E_PYTHON ?? 'python3';
export const PYTHON = configured.includes('/') ? path.resolve(configured) : configured;

export const API = 'http://localhost:8100/api';
// The family hub the planner logs in through (a real one, from a family-hub checkout: playwright.config.ts)
export const HUB = 'http://localhost:8130';
export const FRONTEND = 'http://localhost:3100';
export const ADMIN_PIN = '1111';
export const PIN = '2468';
// The hub takes changes only with its own header, and the manage cookie of the login
const HUB_HEADERS = { 'X-Requested-With': 'hub' };

// token: the hub login the planner gets (hub_session, also as Bearer); hubCookies: what the hub needs for a change
export interface Person { name: string; token: string; hubCookies: string }

// The hub writes its mails here in the tests (MAIL_OUTBOX, inside the hub's data, which every run starts afresh)
export const HUB_OUTBOX = path.resolve(__dirname, '..', '.tmp', 'hub', 'outbox.jsonl');

export const uniqueName = (prefix: string) => `${prefix}${Date.now().toString(36).slice(-4)}${Math.random().toString(36).slice(2, 5)}`;

// A login at the hub, in a throwaway API context: logging out would end the login, so the cookies are only read
async function hubCookies(name: string, pin: string): Promise<{ token: string; cookies: string }> {
    const context = await playwrightRequest.newContext();
    try {
        const response = await context.post(`${HUB}/api/login`, { data: { name, pin }, headers: HUB_HEADERS });
        expect(response.ok(), await response.text()).toBeTruthy();
        const found = response.headersArray()
            .filter(h => h.name.toLowerCase() === 'set-cookie' && /^hub_(session|manage)=/.test(h.value))
            .map(h => h.value.split(';')[0]);
        const session = found.find(c => c.startsWith('hub_session='));
        expect(session, 'the hub sets hub_session').toBeTruthy();
        return { token: session!.slice('hub_session='.length), cookies: found.join('; ') };
    } finally {
        await context.dispose();
    }
}

async function asHubAdmin<T = any>(request: APIRequestContext, method: string, path: string, data?: unknown): Promise<T> {
    const { cookies } = await hubCookies('Admin', ADMIN_PIN);
    const response = await request.fetch(`${HUB}${path}`, { method, data, headers: { ...HUB_HEADERS, Cookie: cookies } });
    expect(response.ok(), `${method} ${path}: ${await response.text()}`).toBeTruthy();
    return response.json();
}

// Who may use the planner: the hub tile with the key "meals" (made on first use, with Admin)
export async function giveAccess(request: APIRequestContext, personId: number, access: boolean): Promise<void> {
    const tiles = await asHubAdmin<{ id: number; app_key: string | null; people: number[] }[]>(request, 'GET', '/api/tiles/manage');
    let tile = tiles.find(t => t.app_key === 'meals');
    if (!tile) {
        const admin = (await asHubAdmin<{ id: number; name: string }[]>(request, 'GET', '/api/people')).find(p => p.name === 'Admin')!;
        tile = await asHubAdmin(request, 'POST', '/api/tiles', { name: 'Essen', local_url: FRONTEND, app_key: 'meals', people: [admin.id] });
    }
    const people = access ? [...new Set([...tile!.people, personId])] : tile!.people.filter(id => id !== personId);
    await asHubAdmin(request, 'PATCH', `/api/tiles/${tile!.id}`, { people });
}

// The token of the hub's last confirmation mail to this address (the hub sends in the background: waited for)
async function confirmToken(address: string): Promise<string> {
    let token: string | undefined;
    await expect.poll(() => {
        const lines = fs.existsSync(HUB_OUTBOX) ? fs.readFileSync(HUB_OUTBOX, 'utf-8').trim().split('\n').filter(Boolean) : [];
        const mails = lines.map(line => JSON.parse(line) as { to: string[]; text: string }).reverse();
        token = mails.map(m => m.to.includes(address) ? m.text.match(/confirm-email#token=([^\s]+)/)?.[1] : undefined).find(Boolean);
        return token;
    }, { message: `a confirmation mail to ${address}` }).toBeTruthy();
    return token!;
}

// The address given when the person was added, confirmed with the link of the hub's mail, and the planner's tile
// sharing the addresses: recipe mails from it are the person's (security review 2026-11-08)
async function confirmAddress(request: APIRequestContext, address: string): Promise<void> {
    const response = await request.post(`${HUB}/api/email-confirm`, { data: { token: await confirmToken(address) }, headers: HUB_HEADERS });
    expect(response.ok(), await response.text()).toBeTruthy();
    const tiles = await asHubAdmin<{ id: number; app_key: string | null; share_email: boolean }[]>(request, 'GET', '/api/tiles/manage');
    const tile = tiles.find(t => t.app_key === 'meals')!;
    if (!tile.share_email) await asHubAdmin(request, 'PATCH', `/api/tiles/${tile.id}`, { share_email: true });
}

// A person added in the hub, with access to the planner unless access=false. With an address, it is confirmed before
// the planner gets access: so the planner knows it from the person's very first sync
export async function addToHub(
    request: APIRequestContext, name: string, role: 'PARENT' | 'CHILD', access = true, address?: string,
): Promise<number> {
    const person = await asHubAdmin<{ id: number }>(request, 'POST', '/api/people', { name, pin: PIN, role, email: address });
    if (address) {
        // The planner's tile exists before its sharing is switched on
        await giveAccess(request, person.id, false);
        await confirmAddress(request, address);
    }
    if (access) await giveAccess(request, person.id, true);
    return person.id;
}

export async function hubLogin(name: string, pin = name === 'Admin' ? ADMIN_PIN : PIN): Promise<Person> {
    const { token, cookies } = await hubCookies(name, pin);
    return { name, token, hubCookies: cookies };
}

// The token of a person's hub login (tests that call the planner's API with it as Bearer)
export async function token(_request: APIRequestContext, name: string, pin?: string): Promise<string> {
    return (await hubLogin(name, pin)).token;
}

// A person of the test's own, added in the hub with access to the planner, and logged in there
// `address`: the person's mail address, confirmed in the hub (recipe mails come only from such addresses)
export async function newPerson(
    request: APIRequestContext, role: 'PARENT' | 'CHILD' = 'PARENT', address?: string,
): Promise<Person> {
    const name = uniqueName(role === 'PARENT' ? 'P' : 'K');
    await addToHub(request, name, role, true, address);
    const person = await hubLogin(name);
    // The planner knows people from the hub once someone uses it (then every minute): mails from the address count now
    if (address) await call(request, person, 'GET', '/me');
    return person;
}

const pageErrors = new WeakMap<Page, string[]>();

// Log in with the person's hub login (the cookie the hub sets at home), and collect errors in the browser console (the
// test checks they are empty). The listeners go on once per page: a test that logs in twice would otherwise accept
// each dialog twice.
export async function login(page: Page, name: string, pin?: string): Promise<string[]> {
    let errors = pageErrors.get(page);
    if (!errors) {
        const collected: string[] = [];
        errors = collected;
        pageErrors.set(page, collected);
        page.on('pageerror', e => collected.push(String(e)));
        page.on('console', m => { if (m.type() === 'error') collected.push(m.text()); });
        page.on('dialog', d => d.accept());
    }
    const { token: session } = await hubLogin(name, pin);
    await page.context().clearCookies();
    await page.context().addCookies([{ name: 'hub_session', value: session, url: FRONTEND }]);
    await page.goto('/');
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

// "2031-01-01" moved by a number of days
export function addDays(day: string, days: number): string {
    return new Date(Date.parse(`${day}T00:00:00Z`) + days * 86_400_000).toISOString().slice(0, 10);
}

export async function call<T = any>(
    request: APIRequestContext, person: Person, method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE', path: string, data?: unknown,
): Promise<T> {
    const response = await request.fetch(`${API}${path}`, { method, data, headers: { Authorization: `Bearer ${person.token}` } });
    expect(response.ok(), `${method} ${path}: ${await response.text()}`).toBeTruthy();
    return response.status() === 204 ? (undefined as T) : response.json();
}

const PNG = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==';

// A mail as the Cloudflare Email Worker posts it: text and one screenshot
export async function sendMail(request: APIRequestContext, from: string, subject: string) {
    const raw = [
        `From: <${from}>`,
        'To: rezepte@example.ch',
        `Subject: ${subject}`,
        `Message-ID: <${uniqueName('m')}@example.ch>`,
        'MIME-Version: 1.0',
        'Content-Type: multipart/mixed; boundary="b"',
        '',
        '--b',
        'Content-Type: text/plain; charset=utf-8',
        '',
        'Gesehen auf Facebook',
        '--b',
        'Content-Type: image/png',
        'Content-Disposition: attachment; filename="screenshot.png"',
        'Content-Transfer-Encoding: base64',
        '',
        PNG,
        '--b--',
        '',
    ].join('\r\n');
    const response = await request.post(`${API}/inbound`, {
        data: raw,
        headers: { 'X-Inbound-Secret': 'e2e-inbound', 'Content-Type': 'message/rfc822' },
    });
    expect(response.ok(), await response.text()).toBeTruthy();
    return response.json();
}

// In the dialog that plans a recipe from its page: on to the following week, once it's shown
export async function nextWeek(dialog: Locator): Promise<void> {
    const week = dialog.getByTestId('plan-dialog-week');
    const before = await week.textContent();
    await dialog.getByRole('button', { name: 'Next week' }).click();
    await expect(week).not.toHaveText(before ?? '');
}
