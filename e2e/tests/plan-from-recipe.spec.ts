import { expect, test } from '@playwright/test';
import { createRecipe, login, newPerson, nextWeek } from './helpers';

const startsWith = (text: string) => new RegExp(`^${text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`);

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
    const label = (await dialog.getByRole('button', { name: /, Dinner: / }).last().getAttribute('aria-label'))!;
    const place = label.split(': ')[0];
    const cell = dialog.getByRole('button', { name: label, exact: true });
    await cell.click();
    await expect(cell).toHaveAttribute('aria-pressed', 'true');
    await expect(dialog.getByTestId('plan-dialog-taken')).toBeVisible();
    await dialog.getByRole('button', { name: 'More people' }).click();
    await dialog.getByRole('button', { name: `Plan on ${place}` }).click();

    await expect(dialog).toHaveCount(0);
    await expect(page.getByRole('button', { name: '📅 Plan' })).toBeFocused();
    await expect(page.getByRole('status')).toContainText(`Planned: ${place}`);
    await expect(page.getByTestId('planned-ahead')).toContainText(place);
    await page.getByRole('link', { name: 'Show the week' }).click();
    await expect(page.getByText(recipe.title)).toBeVisible();

    // Opened again, the grid shows it in its place, also to screen readers
    await page.goto(`/rezepte/${recipe.id}`);
    await page.getByRole('button', { name: '📅 Plan' }).click();
    await nextWeek(dialog);
    const again = dialog.getByRole('button', { name: startsWith(place) });
    await expect(again).toContainText(recipe.title);
    await expect(again).toHaveAttribute('aria-label', new RegExp(`Already planned: .*${recipe.title}`));
    await page.keyboard.press('Escape');
    await expect(dialog).toHaveCount(0);
    expect(errors).toEqual([]);
});

test('days already gone cannot be picked', async ({ page, request }) => {
    const parent = await newPerson(request);
    const recipe = await createRecipe(request, parent);
    await login(page, parent.name);
    await page.goto(`/rezepte/${recipe.id}`);
    await page.getByRole('button', { name: '📅 Plan' }).click();
    const dialog = page.getByRole('dialog', { name: `Plan “${recipe.title}”` });
    const week = dialog.getByTestId('plan-dialog-week');
    const before = await week.textContent();
    // Two weeks back: the opening week holds tomorrow, the one before may hold today
    await dialog.getByRole('button', { name: 'Previous week' }).click();
    await dialog.getByRole('button', { name: 'Previous week' }).click();
    await expect(week).not.toHaveText(before ?? '');
    const cells = dialog.getByRole('button', { name: /, Dinner: / });
    await expect(cells).toHaveCount(7);
    for (const cell of await cells.all()) await expect(cell).toBeDisabled();
});
