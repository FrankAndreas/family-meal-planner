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
