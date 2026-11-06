import { expect, test } from '@playwright/test';
import { createRecipe, login, newPerson, nextWeek, ownWeek } from './helpers';

test('plan a dinner on the phone, day by day', async ({ page, request }) => {
    const parent = await newPerson(request);
    const recipe = await createRecipe(request, parent);
    const errors = await login(page, parent.name);
    await page.goto(`/?woche=${ownWeek()}`);
    await page.getByRole('tab', { name: 'Sunday' }).click();
    await page.getByRole('button', { name: 'Add to Sunday, Dinner' }).click();
    const sheet = page.getByRole('dialog', { name: 'Sunday, Dinner' });
    await sheet.getByRole('tab', { name: 'New' }).click();
    await sheet.getByRole('button', { name: recipe.title }).click();
    await expect(sheet).toHaveCount(0);
    await expect(page.getByTestId('day-dinner')).toContainText(recipe.title);
    await expect(page.getByText('1 of 28 planned')).toBeVisible();

    await page.getByRole('button', { name: 'Add to Sunday, Lunch' }).click();
    await page.getByRole('dialog', { name: 'Sunday, Lunch' }).getByRole('button', { name: 'Add a note' }).click();
    await page.getByRole('dialog', { name: 'Add a note' }).getByRole('button', { name: 'Leftovers' }).click();
    await expect(page.getByTestId('day-lunch')).toContainText('Leftovers');
    expect(errors).toEqual([]);
});

test('move a meal to another slot on the phone', async ({ page, request }) => {
    const parent = await newPerson(request);
    const week = ownWeek();
    await login(page, parent.name);
    await page.goto(`/?woche=${week}`);
    await page.getByRole('tab', { name: 'Saturday' }).click();
    await page.getByRole('button', { name: 'Add to Saturday, Lunch' }).click();
    await page.getByRole('dialog', { name: 'Saturday, Lunch' }).getByRole('button', { name: 'Add a note' }).click();
    await page.getByRole('dialog', { name: 'Add a note' }).getByRole('button', { name: 'Leftovers' }).click();
    await page.getByTestId('day-lunch').getByRole('button', { name: 'Leftovers' }).click();
    await page.getByRole('dialog', { name: 'Leftovers' }).getByRole('button', { name: 'Move', exact: true }).click();
    await page.getByRole('tab', { name: 'Monday' }).click();
    await page.getByRole('button', { name: 'Move to Monday, Dinner' }).click();
    await expect(page.getByTestId('day-dinner')).toContainText('Leftovers');
    await page.getByRole('tab', { name: 'Saturday' }).click();
    await expect(page.getByTestId('day-lunch')).not.toContainText('Leftovers');
});

test('plan a recipe from its page on the phone, with day and meal buttons', async ({ page, request }) => {
    const parent = await newPerson(request);
    const recipe = await createRecipe(request, parent);
    const errors = await login(page, parent.name);
    await page.goto(`/rezepte/${recipe.id}`);
    await page.getByRole('button', { name: '📅 Plan' }).click();
    const dialog = page.getByRole('dialog', { name: `Plan “${recipe.title}”` });
    await nextWeek(dialog);
    await expect(dialog.getByRole('button', { name: 'Pick a day and a meal' })).toBeDisabled();
    const day = dialog.getByRole('button', { name: /day \d+\.\d+\.$/ }).last();
    const dayName = (await day.getAttribute('aria-label'))!;
    await day.click();
    await dialog.getByRole('button', { name: 'Lunch', exact: true }).click();
    await expect(dialog.getByTestId('plan-dialog-taken')).toBeVisible();
    await dialog.getByRole('button', { name: `Plan on ${dayName}, Lunch` }).click();
    await expect(page.getByRole('status')).toContainText(`Planned: ${dayName}, Lunch`);

    // The same place again: the dialog says what's there already
    await page.getByRole('button', { name: '📅 Plan' }).click();
    await nextWeek(dialog);
    await dialog.getByRole('button', { name: dayName, exact: true }).click();
    await dialog.getByRole('button', { name: 'Lunch', exact: true }).click();
    await expect(dialog.getByTestId('plan-dialog-taken')).toContainText(`Already planned: `);
    await expect(dialog.getByTestId('plan-dialog-taken')).toContainText(recipe.title);
    expect(errors).toEqual([]);
});

test('the sheet opens for the tapped slot and leaves the remembered choice alone', async ({ page, request }) => {
    const parent = await newPerson(request);
    const errors = await login(page, parent.name);
    await page.goto(`/?woche=${ownWeek()}`);
    await page.evaluate(() => localStorage.setItem('meals.suggestionSlot', 'dinner'));
    await page.getByRole('tab', { name: 'Sunday' }).click();
    await page.getByRole('button', { name: 'Add to Sunday, Breakfast' }).click();
    const forRow = page.getByRole('dialog', { name: 'Sunday, Breakfast' }).getByRole('group', { name: 'For' });
    await expect(forRow.getByRole('button', { name: 'Breakfast' })).toHaveAttribute('aria-pressed', 'true');
    await forRow.getByRole('button', { name: 'Lunch' }).click();
    await expect(forRow.getByRole('button', { name: 'Lunch' })).toHaveAttribute('aria-pressed', 'true');
    expect(await page.evaluate(() => localStorage.getItem('meals.suggestionSlot'))).toBe('dinner');
    expect(errors).toEqual([]);
});
