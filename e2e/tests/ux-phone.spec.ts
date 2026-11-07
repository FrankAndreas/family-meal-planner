import { expect, test } from '@playwright/test';
import { addDays, call, createRecipe, login, newPerson, ownWeek } from './helpers';

// Phone layouts found in the UX review (2026-11-06): nothing wider than the screen, item names never broken
const sideways = () => document.documentElement.scrollWidth - document.documentElement.clientWidth;

test('the recipe editor fits the phone', async ({ page, request }) => {
    const parent = await newPerson(request);
    const recipe = await createRecipe(request, parent, {
        ingredients: [{ amount: 150, unit: 'g', name: 'Bergkäse', note: 'gerieben' }],
    });
    const errors = await login(page, parent.name);
    await page.goto(`/rezepte/${recipe.id}/bearbeiten`);
    await expect(page.getByRole('textbox', { name: 'Ingredient 1' }).first()).toHaveValue('Bergkäse');
    expect(await page.evaluate(sideways)).toBeLessThanOrEqual(0);
    const field = await page.getByRole('textbox', { name: 'Ingredient 1' }).first().boundingBox();
    expect(field!.x + field!.width).toBeLessThanOrEqual(page.viewportSize()!.width);
    expect(errors).toEqual([]);
});

test('shopping items are never broken mid-word on the phone', async ({ page, request }) => {
    const parent = await newPerson(request);
    await call(request, parent, 'DELETE', '/shopping');
    const start = addDays(ownWeek(), -4);
    const recipe = await createRecipe(request, parent, {
        title: 'Apfelwähe mit einem ziemlich langen Namen vom Grosi',
        ingredients: [
            { amount: 2, unit: 'dl', name: 'Rahm' },
            { amount: 1, unit: 'pack', name: 'Kuchenteig' },
        ],
    });
    await call(request, parent, 'POST', '/plan/entries', { date: start, slot: 'dinner', recipe_id: recipe.id });
    await login(page, parent.name);
    await page.goto(`/einkaufsliste?start=${start}`);
    await page.getByRole('button', { name: /Start the list/ }).click();
    for (const item of ['2 dl Rahm', '1 pack Kuchenteig']) {
        const text = page.getByText(item, { exact: true });
        await expect(text).toBeVisible();
        // One line: the item's own height is a single line of text
        const box = await text.boundingBox();
        expect(box!.height, item).toBeLessThan(32);
    }
    expect(await page.evaluate(sideways)).toBeLessThanOrEqual(0);
});

test('the recipes page starts with recipes on the phone', async ({ page, request }) => {
    const parent = await newPerson(request);
    await createRecipe(request, parent, { tags: ['schnell', 'vegi', 'Kinder', 'Sonntag', 'Zmorge'] });
    const errors = await login(page, parent.name);
    await page.goto('/rezepte');
    // The first card's title is on the first screen, above the bottom bar
    const first = page.locator('main a[href^="/rezepte/"]:not([href="/rezepte/neu"])').first();
    await expect(first).toBeVisible();
    const title = (await first.locator('.font-semibold').first().boundingBox())!;
    const bar = (await page.getByRole('navigation').last().boundingBox())!;
    expect(title.y + title.height).toBeLessThan(bar.y);
    // Every way of adding a recipe is one tap away
    await page.getByRole('button', { name: 'Add recipe' }).click();
    for (const name of ['Photograph a recipe', 'Import from link', 'Paste recipe text']) {
        await expect(page.getByRole('button', { name })).toBeVisible();
    }
    await expect(page.getByRole('link', { name: 'New recipe' })).toBeVisible();
    expect(await page.evaluate(sideways)).toBeLessThanOrEqual(0);
    expect(errors).toEqual([]);
});

test('a long shopping list keeps what to buy first and the send button in reach', async ({ page, request }) => {
    const parent = await newPerson(request);
    await call(request, parent, 'DELETE', '/shopping');
    const start = addDays(ownWeek(), -4);
    const names = ['Salz', ...Array.from({ length: 20 }, (_, n) => `Zutat ${n + 1}`), 'Pfeffer'];
    const recipe = await createRecipe(request, parent, {
        ingredients: names.map((name) => ({ amount: 1, unit: 'piece', name })),
    });
    await call(request, parent, 'POST', '/bring/login', { email: 'family@example.ch', password: 'secret' });
    await call(request, parent, 'PUT', '/bring/list', { uuid: 'fake-home' });
    await call(request, parent, 'POST', '/plan/entries', { date: start, slot: 'dinner', recipe_id: recipe.id });
    await login(page, parent.name);
    await page.goto(`/einkaufsliste?start=${start}`);
    await page.getByRole('button', { name: /Start the list/ }).click();
    const items = page.getByRole('region', { name: /What do we need/ }).getByRole('checkbox');
    await expect(items).toHaveCount(22);
    // What is usually at home goes to the end, after everything to buy
    const order = await items.evaluateAll((boxes) => boxes.map((box) => (box as HTMLInputElement).checked));
    expect(order).toEqual([...Array(20).fill(true), false, false]);
    // Dropping a line keeps it in its place, so nothing jumps away under the finger
    await page.getByRole('checkbox', { name: /Zutat 3 / }).uncheck();
    await expect(items.nth(2)).not.toBeChecked();
    // and ticking one at the end on keeps it there
    await expect(page.getByText('Not buying')).toBeVisible();
    await items.nth(21).check();
    await expect(items.nth(21)).toBeChecked();
    // The send button stays on the screen, above the bottom bar, at the top of the list too
    await page.evaluate(() => window.scrollTo(0, 0));
    const send = page.getByRole('button', { name: /Send to Bring!/ });
    const box = (await send.boundingBox())!;
    const bar = (await page.getByRole('navigation').last().boundingBox())!;
    expect(box.y + box.height).toBeLessThanOrEqual(bar.y);
    expect(box.y).toBeGreaterThan(0);
});

test('the add-recipe menu closes on a tap elsewhere', async ({ page, request }) => {
    const parent = await newPerson(request);
    await login(page, parent.name);
    await page.goto('/rezepte');
    await page.getByRole('button', { name: 'Add recipe' }).click();
    await expect(page.getByRole('link', { name: 'New recipe' })).toBeVisible();
    await page.getByRole('searchbox', { name: 'Search recipes' }).click({ position: { x: 10, y: 10 } });
    await expect(page.getByRole('link', { name: 'New recipe' })).toHaveCount(0);
    await page.getByRole('button', { name: 'Add recipe' }).click();
    await page.keyboard.press('Escape');
    await expect(page.getByRole('link', { name: 'New recipe' })).toHaveCount(0);
    // A panel opened from the menu has its own way to close
    await page.getByRole('button', { name: 'Add recipe' }).click();
    await page.getByRole('button', { name: 'Import from link' }).click();
    await expect(page.getByLabel('Recipe link')).toBeVisible();
    await page.getByRole('button', { name: 'Close' }).click();
    await expect(page.getByLabel('Recipe link')).toHaveCount(0);
});
