import { expect, test } from '@playwright/test';
import { createRecipe, login, newPerson, nextWeek } from './helpers';

// Friday planning while browsing the recipes: the recipe goes into the week straight from its page
test('plan a recipe from its page, in the small week grid', async ({ page, request }) => {
    const parent = await newPerson(request);
    const recipe = await createRecipe(request, parent);
    const errors = await login(page, parent.name);
    await page.goto(`/rezepte/${recipe.id}`);
    await page.getByRole('button', { name: '📅 Plan' }).click();
    const dialog = page.getByRole('dialog', { name: `Plan “${recipe.title}”` });
    // The week after the one it opens on: every day is still ahead
    await nextWeek(dialog);
    const place = (await dialog.getByRole('button', { name: /, Dinner$/ }).last().getAttribute('aria-label'))!;
    const cell = dialog.getByRole('button', { name: place, exact: true });
    await cell.click();
    await expect(cell).toHaveAttribute('aria-pressed', 'true');
    await dialog.getByRole('button', { name: 'More people' }).click();
    await dialog.getByRole('button', { name: `Plan on ${place}` }).click();

    await expect(dialog).toHaveCount(0);
    await expect(page.getByRole('status')).toContainText(`Planned: ${place}`);
    await expect(page.getByTestId('planned-ahead')).toContainText(place);
    await page.getByRole('link', { name: 'Show the week' }).click();
    await expect(page.getByText(recipe.title)).toBeVisible();

    // Opened again, the grid shows it in its place
    await page.goto(`/rezepte/${recipe.id}`);
    await page.getByRole('button', { name: '📅 Plan' }).click();
    await nextWeek(dialog);
    await expect(dialog.getByRole('button', { name: place, exact: true })).toContainText(recipe.title);
    expect(errors).toEqual([]);
});
