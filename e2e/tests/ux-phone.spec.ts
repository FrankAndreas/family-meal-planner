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
