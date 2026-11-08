import { expect, test } from '@playwright/test';
import { call, createRecipe, login, newPerson, ownWeek } from './helpers';

// Accessibility review (2026-11-08)

test('a dialog is modal: Escape closes it, Tab stays in it, and focus goes back where it was', async ({ page, request }) => {
    const parent = await newPerson(request);
    const recipe = await createRecipe(request, parent);
    const week = ownWeek();
    await login(page, parent.name);
    const start = (await call(request, parent, 'GET', `/plan?start=${week}`)).start;
    await call(request, parent, 'POST', '/plan/entries', { date: start, slot: 'dinner', recipe_id: recipe.id });
    await page.goto(`/?woche=${week}`);

    const chip = page.getByTestId('cell-sat-dinner').getByRole('button', { name: recipe.title });
    await chip.click();
    const menu = page.getByRole('dialog', { name: recipe.title });
    await expect(menu).toHaveAttribute('aria-modal', 'true');
    // Focus is in the dialog, and tabbing past its last control comes back to its first
    await expect.poll(() => menu.evaluate((d) => d.contains(document.activeElement))).toBe(true);
    for (let n = 0; n < 12; n++) {
        await page.keyboard.press('Tab');
        expect(await menu.evaluate((d) => d.contains(document.activeElement))).toBe(true);
    }
    await page.keyboard.press('Escape');
    await expect(menu).toHaveCount(0);
    await expect(chip).toBeFocused();

    await page.getByRole('button', { name: 'Add to Sunday, Lunch' }).click();
    const note = page.getByRole('dialog', { name: 'Add a note' });
    await expect(note).toHaveAttribute('aria-modal', 'true');
    await page.keyboard.press('Escape');
    await expect(note).toHaveCount(0);
});

test('each page has its own title', async ({ page, request }) => {
    const parent = await newPerson(request);
    await login(page, parent.name);
    await expect(page).toHaveTitle('Week plan · Meal planner');
    await page.goto('/rezepte');
    await expect(page).toHaveTitle('Recipes · Meal planner');
    await page.goto('/einstellungen');
    await expect(page).toHaveTitle('Settings · Meal planner');
});

test('a skip link leads past the navigation to the page', async ({ page, request }) => {
    const parent = await newPerson(request);
    await login(page, parent.name);
    await page.goto('/rezepte');
    await expect(page.getByRole('heading', { name: 'Recipes' })).toBeVisible();
    await page.keyboard.press('Tab');
    const skip = page.getByRole('link', { name: 'Skip to content' });
    await expect(skip).toBeFocused();
    await page.keyboard.press('Enter');
    await expect(page.locator('main')).toBeFocused();
});
