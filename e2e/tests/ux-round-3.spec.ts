import { expect, test } from '@playwright/test';
import { call, createRecipe, login, newPerson, ownWeek } from './helpers';

// Round 3 of the UX review (2026-11-06), on the iPad: findings 9 to 15

test('the suggestion panel keeps the "For" chips on one row and the tabs on one line each', async ({ page, request }) => {
    const parent = await newPerson(request);
    const errors = await login(page, parent.name);
    await page.goto(`/?woche=${ownWeek()}`);
    const panel = page.getByRole('complementary');
    const forRow = (await panel.getByRole('group', { name: 'For' }).boundingBox())!;
    const chip = (await panel.getByRole('group', { name: 'For' }).getByRole('button', { name: 'All' }).boundingBox())!;
    // One row: no taller than one chip (the row may scroll sideways instead)
    expect(forRow.height).toBeLessThan(chip.height * 1.5);
    // Each tab's label is one line of text (the tabs' boxes stretch with their row, so they can't tell)
    for (const tab of await panel.getByRole('tab').all()) {
        const lines = await tab.evaluate((el) => {
            const range = document.createRange();
            range.selectNodeContents(el);
            return new Set([...range.getClientRects()].map((rect) => Math.round(rect.top))).size;
        });
        expect(lines, await tab.textContent()).toBe(1);
    }
    expect(errors).toEqual([]);
});

test('the stars on a recipe card say they are the family average', async ({ page, request }) => {
    const parent = await newPerson(request);
    const other = await newPerson(request);
    const recipe = await createRecipe(request, parent);
    await call(request, parent, 'PUT', `/recipes/${recipe.id}/rating`, { stars: 5 });
    await call(request, other, 'PUT', `/recipes/${recipe.id}/rating`, { stars: 3 });
    const errors = await login(page, parent.name);
    await page.goto('/rezepte');
    await page.getByRole('searchbox').fill(recipe.title);
    const card = page.getByRole('link', { name: new RegExp(recipe.title) });
    await expect(card).toContainText('avg of 2');
    // A role, so VoiceOver on the iPad reads the label
    await expect(card.getByRole('img', { name: 'Family average: 4 of 5 stars, 2 ratings' })).toBeVisible();
    expect(errors).toEqual([]);
});

test('the pages that are no grid share one width', async ({ page, request }) => {
    const parent = await newPerson(request);
    const recipe = await createRecipe(request, parent);
    const errors = await login(page, parent.name);
    const widths: Record<string, number> = {};
    for (const path of ['/verlauf', '/einstellungen', '/einkaufsliste', '/posteingang', `/rezepte/${recipe.id}`]) {
        await page.goto(path);
        await expect(page.getByRole('heading', { level: 1 }).first()).toBeVisible();
        widths[path] = (await page.locator('main > *').first().boundingBox())!.width;
    }
    expect(new Set(Object.values(widths)).size, JSON.stringify(widths)).toBe(1);
    expect(errors).toEqual([]);
});

test('an empty history says how weeks get there', async ({ page, request }) => {
    const parent = await newPerson(request);
    const errors = await login(page, parent.name);
    // The family's history is shared by all tests, so this one fakes an empty one
    await page.route('**/api/plan/history**', (route) => route.fulfill({ json: [] }));
    await page.goto('/verlauf');
    await expect(page.getByText('Weeks you planned show up here once they are over')).toBeVisible();
    expect(errors).toEqual([]);
});

test('"What do I have?" says what "Use up" and "Cook now" do', async ({ page, request }) => {
    const parent = await newPerson(request);
    const errors = await login(page, parent.name);
    await page.goto('/rezepte');
    await page.getByRole('tab', { name: /What do I have/ }).click();
    const useUp = page.getByRole('button', { name: 'Use up' });
    const cookNow = page.getByRole('button', { name: 'Cook now' });
    await expect(useUp).toHaveAccessibleDescription(/as much of it as possible/);
    await expect(page.getByText(/as much of it as possible/)).toBeVisible();
    await cookNow.click();
    await expect(cookNow).toHaveAccessibleDescription(/at most 2/);
    await expect(page.getByText(/at most 2/)).toBeVisible();
    expect(errors).toEqual([]);
});

test('deleting a recipe sits apart from editing it', async ({ page, request }) => {
    const parent = await newPerson(request);
    const recipe = await createRecipe(request, parent);
    const errors = await login(page, parent.name);
    await page.goto(`/rezepte/${recipe.id}`);
    const edit = (await page.getByRole('link', { name: 'Edit' }).boundingBox())!;
    const remove = (await page.getByRole('button', { name: 'Delete recipe' }).boundingBox())!;
    // Not in the row of everyday actions, but well below it
    expect(remove.y).toBeGreaterThan(edit.y + edit.height + 24);
    expect(errors).toEqual([]);
});
