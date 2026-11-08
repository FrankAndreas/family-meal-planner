import { expect, test } from '@playwright/test';
import { API, createRecipe, login, newPerson, uniqueName } from './helpers';

test('a photo that cannot be read does not lead to a second copy of the recipe', async ({ page, request }) => {
    const parent = await newPerson(request);
    await login(page, parent.name);
    const title = uniqueName('Fotofehler ');
    await page.goto('/rezepte/neu');
    await page.getByLabel('Title').fill(title);
    await page.getByLabel('Ingredient 1').fill('Mehl');
    await page.getByLabel('Choose photo').setInputFiles({ name: 'x.jpg', mimeType: 'image/jpeg', buffer: Buffer.from('nope') });
    await page.getByRole('button', { name: 'Save recipe' }).click();
    await expect(page.getByText('The photo couldn’t be read.')).toBeVisible();
    // Saving again (as anyone would) must not make a second recipe
    const save = page.getByRole('button', { name: 'Save recipe' });
    if (await save.isVisible()) await save.click();
    const found = await request.get(`${API}/recipes?q=${encodeURIComponent(title)}`, {
        headers: { Authorization: `Bearer ${parent.token}` },
    });
    expect((await found.json()).length).toBe(1);
});

test('a rating that answers late does not bring back old amounts', async ({ page, request }) => {
    const parent = await newPerson(request);
    const recipe = await createRecipe(request, parent);
    await login(page, parent.name);
    await page.goto(`/rezepte/${recipe.id}`);
    await expect(page.getByText('400 g Hörnli')).toBeVisible();
    await page.route('**/rating', async (route) => {
        await new Promise((resolve) => setTimeout(resolve, 1500));
        await route.continue();
    });
    await page.getByRole('button', { name: 'Rate 5 stars' }).click();
    await page.getByRole('button', { name: 'Fewer people' }).click();
    await page.getByRole('button', { name: 'Fewer people' }).click();
    await expect(page.getByText('200 g Hörnli')).toBeVisible();
    await page.waitForTimeout(2000);
    await expect(page.getByText('2 people')).toBeVisible();
    await expect(page.getByText('200 g Hörnli')).toBeVisible();
});

test('the editor of a recipe that did not load cannot save over it', async ({ page, request }) => {
    const parent = await newPerson(request);
    const recipe = await createRecipe(request, parent);
    await login(page, parent.name);
    await page.route(`**/api/recipes/${recipe.id}`, (route) =>
        route.request().method() === 'GET' ? route.fulfill({ status: 502 }) : route.continue(),
    );
    await page.goto(`/rezepte/${recipe.id}/bearbeiten`);
    await expect(page.getByText('Something went wrong')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Save recipe' })).toHaveCount(0);
});

// Test gaps (2026-11-08): changing the people while the AI translates must not bring back the old amounts afterwards
test('the people chosen during a translation stay, with their amounts', async ({ page, request }) => {
    const parent = await newPerson(request);
    const title = uniqueName('Teig ');
    const recipe = await createRecipe(request, parent, {
        title, language: 'de', servings: 4, ingredients: [{ amount: 400, unit: 'g', name: 'Mehl', note: '', group: null }],
    });
    await login(page, parent.name);
    let release = () => {};
    const held = new Promise<void>((resolve) => { release = resolve; });
    await page.route('**/api/recipes/*/translate', async (route) => {
        await held;
        await route.continue();
    });
    await page.goto(`/rezepte/${recipe.id}`);
    const ingredients = page.getByRole('list', { name: 'Ingredients' });
    await expect(ingredients).toContainText('400 g');
    await page.getByRole('button', { name: 'Translate into English' }).click();
    await page.getByRole('button', { name: 'More people' }).click();
    await expect(ingredients).toContainText('500 g');
    release();
    await expect(page.getByRole('heading', { name: `EN ${title}` })).toBeVisible();
    await expect(ingredients).toContainText('500 g');
});

// Review of the test gaps: the load for the new people, sent before the translation was done, comes back last; it must
// not replace the translated recipe
test('a load for new people that comes back after the translation does not undo it', async ({ page, request }) => {
    const parent = await newPerson(request);
    const title = uniqueName('Teig ');
    const recipe = await createRecipe(request, parent, {
        title, language: 'de', servings: 4, ingredients: [{ amount: 400, unit: 'g', name: 'Mehl', note: '', group: null }],
    });
    await login(page, parent.name);
    let releaseTranslation = () => {};
    const translation = new Promise<void>((resolve) => { releaseTranslation = resolve; });
    await page.route('**/api/recipes/*/translate', async (route) => {
        await translation;
        await route.continue();
    });
    // The first load for 5 people: answered now (untranslated), handed to the page only when released
    let releaseOldLoad = () => {};
    const oldLoad = new Promise<void>((resolve) => { releaseOldLoad = resolve; });
    let loadsFor5 = 0;
    await page.route(/\/api\/recipes\/\d+\?people=5$/, async (route) => {
        loadsFor5 += 1;
        if (loadsFor5 > 1) return route.continue();
        const response = await route.fetch();
        await oldLoad;
        await route.fulfill({ response });
    });
    await page.goto(`/rezepte/${recipe.id}`);
    await page.getByRole('button', { name: 'Translate into English' }).click();
    await page.getByRole('button', { name: 'More people' }).click();
    await expect.poll(() => loadsFor5).toBe(1);
    releaseTranslation();
    await expect(page.getByRole('heading', { name: `EN ${title}` })).toBeVisible();
    releaseOldLoad();
    // Give the old answer time to arrive, then the translation is still there, with the amounts for 5
    await page.waitForTimeout(500);
    await expect(page.getByRole('heading', { name: `EN ${title}` })).toBeVisible();
    await expect(page.getByRole('list', { name: 'Ingredients' })).toContainText('500 g');
});
