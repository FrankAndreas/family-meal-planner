import { expect, test, type APIRequestContext, type Page } from '@playwright/test';
import { addDays, call, createRecipe, login, newPerson, ownWeek, type Person } from './helpers';

// The shopping list and the Bring! login are one per family: each test starts without them
async function clean(request: APIRequestContext, parent: Person) {
    await call(request, parent, 'DELETE', '/shopping');
    await call(request, parent, 'DELETE', '/bring');
}

test('bring settings', async ({ page, request }) => {
    const parent = await newPerson(request);
    await clean(request, parent);
    const errors = await login(page, parent.name);
    await page.goto('/einstellungen');
    const section = page.getByRole('region', { name: 'Bring!' });
    await section.getByLabel('Email').fill('family@example.ch');
    await section.getByLabel('Password').fill('wrong');
    await section.getByRole('button', { name: 'Sign in' }).click();
    await expect(section.getByText('Bring! didn’t accept the email or the password.')).toBeVisible();

    await section.getByLabel('Password').fill('secret');
    await section.getByRole('button', { name: 'Sign in' }).click();
    const picker = section.getByLabel('List');
    await expect(picker.locator('option')).toHaveText(['Choose a list', 'Zuhause', 'Büro']);
    await picker.selectOption({ label: 'Zuhause' });
    await expect(section.getByText('Signed in as family@example.ch · list Zuhause')).toBeVisible();

    await page.reload();
    await expect(section.getByText('Signed in as family@example.ch · list Zuhause')).toBeVisible();
    await expect(section.getByLabel('Password')).toHaveCount(0);

    await section.getByRole('button', { name: 'Sign out of Bring!' }).click();
    await expect(section.getByLabel('Password')).toHaveValue('');
    await expect(section.getByText(/Signed in as/)).toHaveCount(0);
    // Only the refused wrong password
    expect(errors.filter((e) => !e.includes('400'))).toEqual([]);
});

test('children see no Bring! settings', async ({ page, request }) => {
    const child = await newPerson(request, 'CHILD');
    await login(page, child.name);
    await page.goto('/einstellungen');
    await expect(page.getByRole('heading', { name: 'My settings' })).toBeVisible();
    await expect(page.getByRole('region', { name: 'Bring!' })).toHaveCount(0);
});

// A week with a pasta dish for 6 on Saturday, a soup on Monday and a note on Sunday; Bring! set up
async function week(request: APIRequestContext, parent: Person) {
    await clean(request, parent);
    await call(request, parent, 'POST', '/bring/login', { email: 'family@example.ch', password: 'secret' });
    await call(request, parent, 'PUT', '/bring/list', { uuid: 'fake-home' });
    // ownWeek() is a Wednesday; the default week starts on the Saturday before
    const start = addDays(ownWeek(), -4);
    const pasta = await createRecipe(request, parent, {
        title: 'Älplermagronen',
        ingredients: [
            { amount: 200, unit: 'g', name: 'Hörnli' },
            { amount: 1, unit: 'tsp', name: 'Salz' },
        ],
    });
    const soup = await createRecipe(request, parent, {
        title: 'Gemüsesuppe',
        ingredients: [{ amount: 2, unit: null, name: 'Rüebli' }],
    });
    await call(request, parent, 'POST', '/plan/entries', { date: start, slot: 'dinner', recipe_id: pasta.id, people: 6 });
    await call(request, parent, 'POST', '/plan/entries', { date: addDays(start, 1), slot: 'dinner', note: 'Leftovers' });
    await call(request, parent, 'POST', '/plan/entries', { date: addDays(start, 2), slot: 'dinner', recipe_id: soup.id });
    return start;
}

async function openList(page: Page, start: string) {
    await page.goto(`/?woche=${start}`);
    await page.getByRole('link', { name: '🛒 Shopping list' }).click();
    await page.getByRole('button', { name: /Start the list/ }).click();
}

test('list from the week', async ({ page, request }) => {
    const parent = await newPerson(request);
    const start = await week(request, parent);
    const errors = await login(page, parent.name);
    await openList(page, start);
    const meals = page.getByRole('region', { name: /Which meals/ });
    await expect(meals.getByRole('checkbox', { name: /Älplermagronen/ })).toBeChecked();
    await expect(meals.getByRole('checkbox', { name: /Gemüsesuppe/ })).toBeChecked();
    await expect(meals.getByText('Leftovers')).toBeVisible();
    await expect(meals.getByRole('checkbox', { name: /Leftovers/ })).toHaveCount(0);
    const items = page.getByRole('region', { name: /What do we need/ });
    await expect(items.getByRole('checkbox', { name: /300 g Hörnli/ })).toBeChecked();
    await expect(items.getByRole('listitem').filter({ hasText: 'Hörnli' })).toContainText('for Älplermagronen');
    const salz = items.getByRole('checkbox', { name: /Salz/ });
    await expect(salz).not.toBeChecked();
    await expect(items.getByText('usually at home')).toBeVisible();
    await meals.getByRole('checkbox', { name: /Gemüsesuppe/ }).uncheck();
    await expect(items.getByRole('checkbox', { name: /Rüebli/ })).toHaveCount(0);
    await expect(page.getByText(`Started by ${parent.name}`)).toBeVisible();
    expect(errors).toEqual([]);
});

test('drop, add and send', async ({ page, request }) => {
    const parent = await newPerson(request);
    const start = await week(request, parent);
    const errors = await login(page, parent.name);
    await openList(page, start);
    const items = page.getByRole('region', { name: /What do we need/ });
    await items.getByRole('checkbox', { name: /Rüebli/ }).uncheck();
    await expect(items.getByRole('checkbox', { name: /Rüebli/ })).not.toBeChecked();
    await items.getByLabel('Add something').fill('Toilet paper');
    await items.getByLabel('Amount').fill('2 packs');
    await items.getByRole('button', { name: 'Add', exact: true }).click();
    await expect(items.getByRole('checkbox', { name: /2 packs Toilet paper/ })).toBeChecked();
    await page.getByRole('button', { name: 'Send to Bring! (2)' }).click();
    await expect(page.getByText('2 items in Bring!')).toBeVisible();
    await page.reload();
    await expect(page.getByRole('button', { name: /Start the list/ })).toBeVisible();
    expect(errors).toEqual([]);
});

test('changed meanwhile', async ({ page, request }) => {
    const parent = await newPerson(request);
    const start = await week(request, parent);
    const errors = await login(page, parent.name);
    await openList(page, start);
    const items = page.getByRole('region', { name: /What do we need/ });
    await expect(items.getByRole('checkbox', { name: /Hörnli/ })).toBeChecked();
    // The other parent drops a line while this page is open
    const list = await call(request, parent, 'GET', '/shopping');
    const hoernli = list.list.lines.find((l: { name: string }) => l.name === 'Hörnli');
    await call(request, parent, 'PUT', '/shopping/lines', { key: hoernli.key, buy: false });
    await page.getByRole('button', { name: 'Send to Bring! (2)' }).click();
    await expect(page.getByText('The list changed in the meantime. Please check it again.')).toBeVisible();
    await expect(items.getByRole('checkbox', { name: /Hörnli/ })).not.toBeChecked();
    await page.getByRole('button', { name: 'Send to Bring! (1)' }).click();
    await expect(page.getByText('1 item in Bring!')).toBeVisible();
    expect(errors.filter((e) => !e.includes('409'))).toEqual([]);
});

test('bring fails', async ({ page, request }) => {
    const parent = await newPerson(request);
    const start = await week(request, parent);
    const errors = await login(page, parent.name);
    await openList(page, start);
    const items = page.getByRole('region', { name: /What do we need/ });
    await items.getByLabel('Add something').fill('FAIL');
    await items.getByRole('button', { name: 'Add', exact: true }).click();
    await page.getByRole('button', { name: 'Send to Bring! (3)' }).click();
    await expect(page.getByText(/Bring! can’t be reached right now/)).toBeVisible();
    await page.reload();
    await expect(items.getByRole('checkbox', { name: /FAIL/ })).toBeChecked();
    expect(errors.filter((e) => !e.includes('502'))).toEqual([]);
});

test('without Bring! the list points to the settings', async ({ page, request }) => {
    const parent = await newPerson(request);
    const start = await week(request, parent);
    await call(request, parent, 'DELETE', '/bring');
    await login(page, parent.name);
    await openList(page, start);
    await expect(page.getByRole('button', { name: /Send to Bring!/ })).toHaveCount(0);
    await page.getByRole('link', { name: 'Set up Bring! in the settings to send the list.' }).click();
    await expect(page.getByRole('region', { name: 'Bring!' })).toBeVisible();
});

test('a list for another week', async ({ page, request }) => {
    const parent = await newPerson(request);
    const start = await week(request, parent);
    await call(request, parent, 'POST', '/shopping', { week_start: addDays(start, 7) });
    await login(page, parent.name);
    await page.goto(`/?woche=${start}`);
    await page.getByRole('link', { name: '🛒 Shopping list' }).click();
    await expect(page.getByText(/There’s a list for/)).toBeVisible();
    await page.getByRole('button', { name: 'Discard it and start this week' }).click();
    await expect(page.getByRole('region', { name: /Which meals/ }).getByRole('checkbox', { name: /Älplermagronen/ })).toBeChecked();
});

test('children don’t see the shopping list', async ({ page, request }) => {
    const child = await newPerson(request, 'CHILD');
    await login(page, child.name);
    await expect(page.getByTestId('week-range')).toBeVisible();
    await expect(page.getByRole('link', { name: '🛒 Shopping list' })).toHaveCount(0);
});

// The list keeps its week when the first day of the week changes (spec 2026-11-06)
test('the open list after the first day of the week changed', async ({ page, request }) => {
    const parent = await newPerson(request);
    const start = await week(request, parent);
    await call(request, parent, 'POST', '/shopping', { week_start: start });
    await call(request, parent, 'PATCH', '/settings', { week_start: 0 });
    try {
        await login(page, parent.name);
        await page.goto(`/?woche=${start}`);
        await page.getByRole('link', { name: '🛒 Shopping list' }).click();
        await expect(page.getByText(/There’s a list for/)).toBeVisible();
        await page.getByRole('button', { name: 'Open it' }).click();
        await expect(page.getByRole('region', { name: /Which meals/ }).getByRole('checkbox', { name: /Älplermagronen/ })).toBeChecked();
    } finally {
        await call(request, parent, 'PATCH', '/settings', { week_start: 5 });
    }
});
