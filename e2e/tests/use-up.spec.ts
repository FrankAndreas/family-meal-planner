import { expect, test } from '@playwright/test';
import { API, createRecipe, login, newPerson, uniqueName } from './helpers';

const ingredient = (name: string) => ({ amount: null, unit: null, name });

// At the drawer: potatoes and a leek need using up (runs on the tablet and the phone)
test('find recipes by what is at home', async ({ page, request }) => {
    const parent = await newPerson(request);
    const title = uniqueName('Gratin ');
    const recipe = await createRecipe(request, parent, {
        title,
        ingredients: ['Kartoffeln', 'Lauch', 'Halbrahm', 'Salz'].map(ingredient),
    });
    const errors = await login(page, parent.name);
    await page.goto('/rezepte');
    await page.getByRole('tab', { name: '🧺 What do I have?' }).click();
    const input = page.getByLabel('What’s at home?');
    await input.fill('Kartoffeln');
    await input.press('Enter');
    await input.fill('Lauch');
    await input.press('Enter');

    const result = page.getByRole('link', { name: new RegExp(title) });
    await expect(result).toContainText('✓ Kartoffeln, Lauch');
    await expect(result).toContainText('missing: Halbrahm');
    await page.getByRole('button', { name: 'Cook now' }).click();
    await expect(result).toBeVisible();

    await result.click();
    await expect(page).toHaveURL(new RegExp(`/rezepte/${recipe.id}$`));
    await page.goBack();
    await expect(page.getByRole('button', { name: 'Remove Kartoffeln' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Remove Lauch' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Cook now' })).toHaveAttribute('aria-pressed', 'true');

    await page.getByRole('button', { name: 'Clear' }).click();
    await expect(page.getByRole('button', { name: /^Remove / })).toHaveCount(0);
    await expect(page.getByText('Type what’s at home, e.g. what needs using soon.')).toBeVisible();
    expect(errors).toEqual([]);
});

test('a parent edits the basics and a missing one disappears', async ({ page, request }) => {
    const parent = await newPerson(request);
    // A spice of the test's own, so no other recipe or test is affected
    const spice = uniqueName('Gewuerz');
    const title = uniqueName('Ofenkartoffeln ');
    await createRecipe(request, parent, { title, ingredients: ['Kartoffeln', spice].map(ingredient) });
    const errors = await login(page, parent.name);
    try {
        await page.goto('/rezepte');
        await page.getByRole('tab', { name: '🧺 What do I have?' }).click();
        const clear = page.getByRole('button', { name: 'Clear' });
        if (await clear.isVisible()) await clear.click();
        await page.getByLabel('What’s at home?').fill('Kartoffeln');
        await page.getByLabel('What’s at home?').press('Enter');
        const result = page.getByRole('link', { name: new RegExp(title) });
        await expect(result).toContainText(`missing: ${spice}`);

        await page.goto('/einstellungen');
        const basics = page.getByLabel('Always at home');
        await basics.fill(spice);
        await basics.press('Enter');
        await page.getByRole('button', { name: 'Save family settings' }).click();
        await expect(page.getByText('Saved')).toBeVisible();

        await page.goto('/rezepte');
        await expect(result).toBeVisible();
        await expect(result).not.toContainText('missing');
        expect(errors).toEqual([]);
    } finally {
        // Back to the defaults: the basics are the whole family's
        await request.patch(`${API}/settings`, {
            data: { staples: ['Salz', 'Pfeffer', 'Öl', 'Wasser', 'Zucker', 'Mehl', 'Bouillon'] },
            headers: { Authorization: `Bearer ${parent.token}` },
        });
    }
});

test('at most 20 ingredients, as many as the search takes', async ({ page, request }) => {
    const parent = await newPerson(request);
    const have = Array.from({ length: 20 }, (_, n) => `Zutat${String.fromCharCode(97 + n)}`);
    await page.addInitScript((stored) => localStorage.setItem('meals.useUp', stored), JSON.stringify({ tab: 'use_up', have, mode: 'use_up' }));
    const errors = await login(page, parent.name);
    await page.goto('/rezepte');
    await expect(page.getByRole('button', { name: /^Remove / })).toHaveCount(20);
    await expect(page.getByLabel('What’s at home?')).toHaveCount(0);
    await expect(page.getByText('That’s the most: 20 ingredients.')).toBeVisible();
    await expect(page.getByText('No recipe fits.')).toBeVisible();
    await page.getByRole('button', { name: 'Remove Zutata' }).click();
    await expect(page.getByLabel('What’s at home?')).toBeVisible();
    expect(errors).toEqual([]);
});

test('no old results or errors once the ingredients change', async ({ page, request }) => {
    const parent = await newPerson(request);
    const title = uniqueName('Rösti ');
    await createRecipe(request, parent, { title, ingredients: ['Kartoffeln', 'Butter'].map(ingredient) });
    const errors = await login(page, parent.name);
    await page.goto('/rezepte');
    await page.getByRole('tab', { name: '🧺 What do I have?' }).click();
    const clear = page.getByRole('button', { name: 'Clear' });
    if (await clear.isVisible()) await clear.click();
    const input = page.getByLabel('What’s at home?');
    await input.fill('Kartoffeln');
    await input.press('Enter');
    await input.fill('Butter');
    await input.press('Enter');
    const result = page.getByRole('link', { name: new RegExp(title) });
    await expect(result).toContainText('✓ Kartoffeln, Butter');

    // The next answers are held back: until they come, old results must not show for the new ingredients
    let release = () => {};
    let held = new Promise<void>((resolve) => (release = resolve));
    await page.route('**/api/use-up?*', async (route) => {
        await held;
        await route.continue();
    });
    await page.getByRole('button', { name: 'Remove Butter' }).click();
    await page.waitForTimeout(500);
    await expect(page.getByText('✓ Kartoffeln, Butter')).toHaveCount(0);
    release();
    await expect(result).toContainText('✓ Kartoffeln');
    held = new Promise<void>((resolve) => (release = resolve));
    await clear.click();
    await input.fill(uniqueName('Zutat'));
    await input.press('Enter');
    await expect(result).toHaveCount(0);
    release();
    await expect(page.getByText('No recipe fits.')).toBeVisible();

    // A failing search shows its error, and clearing the ingredients takes it away
    await page.unroute('**/api/use-up?*');
    await page.route('**/api/use-up?*', (route) => route.fulfill({ status: 500, body: '{}' }));
    await input.fill('Lauch');
    await input.press('Enter');
    const failure = page.locator('.border-red-400\\/30');
    await expect(failure).toBeVisible();
    await clear.click();
    await expect(failure).toHaveCount(0);
    expect(errors.filter((e) => !e.includes('500'))).toEqual([]);
});

test('the search tabs and chips work for every hand', async ({ page, request }) => {
    const parent = await newPerson(request);
    await login(page, parent.name);
    await page.goto('/rezepte');
    const search = page.getByRole('tab', { name: 'Search' });
    await search.click();
    await search.press('ArrowRight');
    const useUp = page.getByRole('tab', { name: '🧺 What do I have?' });
    await expect(useUp).toHaveAttribute('aria-selected', 'true');
    await expect(useUp).toBeFocused();
    await expect(page.getByRole('tabpanel', { name: '🧺 What do I have?' })).toBeVisible();
    const clear = page.getByRole('button', { name: 'Clear' });
    if (await clear.isVisible()) await clear.click();
    // A visible label, not only a placeholder
    await expect(page.locator('label', { hasText: 'What’s at home?' })).toBeVisible();
    await page.getByLabel('What’s at home?').fill('Lauch');
    await page.getByLabel('What’s at home?').press('Enter');
    const remove = await page.getByRole('button', { name: 'Remove Lauch' }).boundingBox();
    expect(remove!.width).toBeGreaterThanOrEqual(32);
    expect(remove!.height).toBeGreaterThanOrEqual(32);
    await useUp.press('ArrowLeft');
    await expect(search).toHaveAttribute('aria-selected', 'true');
});
