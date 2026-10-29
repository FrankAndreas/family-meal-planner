import { expect, test } from '@playwright/test';
import { createRecipe, login, newPerson, uniqueName } from './helpers';

test('a child types in a recipe with fractions and sees it scaled', async ({ page, request }) => {
    const child = await newPerson(request, 'CHILD');
    const errors = await login(page, child.name);
    const title = uniqueName('Testrisotto ');
    await page.goto('/rezepte');
    await page.getByRole('link', { name: 'New recipe' }).click();
    await page.getByLabel('Title').fill(title);
    await page.getByLabel('Amount 1').fill('1/2');
    await page.getByLabel('Unit 1').selectOption('l');
    await page.getByLabel('Ingredient 1').fill('Bouillon');
    await page.getByRole('button', { name: 'Add ingredient' }).click();
    await page.getByLabel('Amount 2').fill('3');
    await page.getByLabel('Ingredient 2').fill('Schalotten');
    await page.getByLabel('Steps').fill('Schalotten dünsten\n\nReis beigeben');
    await page.getByRole('button', { name: 'Save recipe' }).click();

    await expect(page.getByRole('heading', { name: title })).toBeVisible();
    const ingredients = page.getByRole('list', { name: 'Ingredients' });
    await expect(ingredients).toContainText('½ l Bouillon');
    await expect(ingredients).toContainText('3 Schalotten');
    await expect(page.getByRole('list', { name: 'Steps' }).getByRole('listitem')).toHaveCount(2);

    await page.getByRole('button', { name: 'Fewer people' }).click();
    await page.getByRole('button', { name: 'Fewer people' }).click();
    await expect(page.getByText('2 people')).toBeVisible();
    await expect(ingredients).toContainText('¼ l Bouillon');
    await expect(ingredients).toContainText('1½ Schalotten');
    expect(errors).toEqual([]);
});

test('an amount that is not a number blocks saving', async ({ page, request }) => {
    const child = await newPerson(request, 'CHILD');
    await login(page, child.name);
    await page.goto('/rezepte/neu');
    await page.getByLabel('Title').fill('Kaputt');
    await page.getByLabel('Amount 1').fill('abc');
    await page.getByLabel('Ingredient 1').fill('Mehl');
    await expect(page.getByLabel('Amount 1')).toHaveAttribute('aria-invalid', 'true');
    await expect(page.getByRole('button', { name: 'Save recipe' })).toBeDisabled();
});

test('ratings and favourites are per person', async ({ page, request }) => {
    const parent = await newPerson(request);
    const child = await newPerson(request, 'CHILD');
    const recipe = await createRecipe(request, parent);
    await login(page, parent.name);
    await page.goto(`/rezepte/${recipe.id}`);
    await page.getByRole('button', { name: 'Rate 4 stars' }).click();
    await page.getByRole('button', { name: 'Favourite' }).click();
    await expect(page.getByRole('button', { name: 'Favourite' })).toHaveAttribute('aria-pressed', 'true');
    await expect(page.getByText(`${parent.name}: 4`)).toBeVisible();

    await page.goto('/rezepte');
    await page.getByLabel('Only my favourites').check();
    await expect(page.getByRole('link', { name: recipe.title })).toBeVisible();

    await page.getByRole('button', { name: 'Log out' }).click();
    await login(page, child.name);
    await page.goto('/rezepte');
    await page.getByLabel('Only my favourites').check();
    await expect(page.getByRole('link', { name: recipe.title })).toHaveCount(0);
});

test('only parents delete, and a deleted recipe leaves the list', async ({ page, request }) => {
    const parent = await newPerson(request);
    const child = await newPerson(request, 'CHILD');
    const recipe = await createRecipe(request, parent);
    await login(page, child.name);
    await page.goto(`/rezepte/${recipe.id}`);
    await expect(page.getByRole('heading', { name: recipe.title })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Delete recipe' })).toHaveCount(0);

    await page.getByRole('button', { name: 'Log out' }).click();
    await login(page, parent.name);
    await page.goto(`/rezepte/${recipe.id}`);
    await page.getByRole('button', { name: 'Delete recipe' }).click();
    await expect(page).toHaveURL(/\/rezepte$/);
    await page.getByLabel('Search recipes').fill(recipe.title);
    await expect(page.getByRole('link', { name: recipe.title })).toHaveCount(0);
});

test('search finds recipes by ingredient', async ({ page, request }) => {
    const parent = await newPerson(request);
    const special = uniqueName('Safran');
    const recipe = await createRecipe(request, parent, { ingredients: [{ amount: 1, unit: 'pinch', name: special }] });
    await login(page, parent.name);
    await page.goto('/rezepte');
    await page.getByLabel('Search recipes').fill(special.toLowerCase());
    await expect(page.getByRole('link', { name: recipe.title })).toBeVisible();
});
