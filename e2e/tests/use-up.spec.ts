import { expect, test } from '@playwright/test';
import { createRecipe, login, newPerson, uniqueName } from './helpers';

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
    const input = page.getByRole('combobox', { name: 'Ingredient' });
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
