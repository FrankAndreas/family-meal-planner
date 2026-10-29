import { expect, test } from '@playwright/test';
import { createRecipe, login, newPerson } from './helpers';

test('a recipe shows where it comes from, as a link that opens the page', async ({ page, request }) => {
    const parent = await newPerson(request);
    const url = 'https://www.swissmilk.ch/de/rezepte-kochideen/rezepte/LM201401_57/';
    const recipe = await createRecipe(request, parent, { source_url: url, source_kind: 'url' });
    await login(page, parent.name);
    await page.goto(`/rezepte/${recipe.id}`);
    const link = page.getByRole('link', { name: 'swissmilk.ch' });
    await expect(link).toHaveAttribute('href', url);
    await expect(link).toHaveAttribute('target', '_blank');
});

test('the source is a link or a text, changed in the editor', async ({ page, request }) => {
    const child = await newPerson(request, 'CHILD');
    const recipe = await createRecipe(request, child);
    await login(page, child.name);
    await page.goto(`/rezepte/${recipe.id}`);
    await expect(page.getByText('Source:')).toHaveCount(0);
    await page.goto(`/rezepte/${recipe.id}/bearbeiten`);
    const field = page.getByLabel('Source', { exact: true });
    await field.fill('javascript:alert(1)');
    await expect(page.getByText('That isn’t a web address (http/https).')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Save recipe' })).toBeDisabled();
    await field.fill('Betty Bossi cookbook, p. 42');
    await page.getByRole('button', { name: 'Save recipe' }).click();
    await expect(page.getByText('Source: Betty Bossi cookbook, p. 42')).toBeVisible();
    await expect(page.getByRole('link', { name: /Betty Bossi/ })).toHaveCount(0);
    await page.goto(`/rezepte/${recipe.id}/bearbeiten`);
    await field.fill('https://fooby.ch/de/rezepte/12345/risotto');
    await page.getByRole('button', { name: 'Save recipe' }).click();
    await expect(page.getByRole('link', { name: 'fooby.ch' })).toHaveAttribute('href', 'https://fooby.ch/de/rezepte/12345/risotto');
});
