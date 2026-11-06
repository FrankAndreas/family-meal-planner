import { expect, test } from '@playwright/test';
import { addDays, call, createRecipe, login, newPerson, ownWeek } from './helpers';

// On the phone: the same list, readable without scrolling sideways
test('shopping list on the phone', async ({ page, request }) => {
    const parent = await newPerson(request);
    await call(request, parent, 'DELETE', '/shopping');
    const start = addDays(ownWeek(), -4);
    const recipe = await createRecipe(request, parent, { title: 'Älplermagronen mit einem langen Namen' });
    await call(request, parent, 'POST', '/plan/entries', { date: start, slot: 'dinner', recipe_id: recipe.id });
    const errors = await login(page, parent.name);
    await page.goto(`/einkaufsliste?start=${start}`);
    await page.getByRole('button', { name: /Start the list/ }).click();
    await expect(page.getByRole('region', { name: /Which meals/ }).getByRole('checkbox', { name: /Älplermagronen/ })).toBeChecked();
    await expect(page.getByRole('checkbox', { name: /400 g Hörnli/ })).toBeVisible();
    const wide = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(wide).toBeLessThanOrEqual(0);
    expect(errors).toEqual([]);
});
