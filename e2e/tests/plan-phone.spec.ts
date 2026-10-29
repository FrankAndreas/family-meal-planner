import { expect, test } from '@playwright/test';
import { createRecipe, login, newPerson, ownWeek } from './helpers';

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
