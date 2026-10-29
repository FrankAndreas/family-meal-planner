import { expect, test } from '@playwright/test';
import { call, createRecipe, login, newPerson } from './helpers';

const shift = (day: string, days: number) => {
    const d = new Date(`${day}T12:00:00Z`);
    d.setUTCDate(d.getUTCDate() + days);
    return d.toISOString().slice(0, 10);
};

test('close a week, then find it in the history', async ({ page, request }) => {
    const parent = await newPerson(request);
    const eaten = await createRecipe(request, parent);
    const skipped = await createRecipe(request, parent);
    // Two weeks back is always over (the week before the default one may end today)
    const shown = shift((await call(request, parent, 'GET', '/plan')).start, -7);
    const past = shift(shown, -7);
    await call(request, parent, 'POST', '/plan/entries', { date: past, slot: 'dinner', recipe_id: eaten.id });
    await call(request, parent, 'POST', '/plan/entries', { date: shift(past, 1), slot: 'dinner', recipe_id: skipped.id });

    const errors = await login(page, parent.name);
    await page.goto(`/?woche=${shown}`);
    await page.getByRole('link', { name: 'Close the week' }).click();
    await expect(page).toHaveURL(new RegExp(`/woche-abschliessen\\?start=${past}`));

    await page.getByRole('checkbox', { name: `Eaten: ${skipped.title}` }).uncheck();
    const eatenRow = page.getByRole('listitem').filter({ hasText: eaten.title });
    await eatenRow.getByRole('button', { name: 'Rate 5 stars' }).click();
    await page.getByRole('listitem').filter({ hasText: skipped.title }).getByRole('button', { name: 'Instead…' }).click();
    await page.getByRole('dialog', { name: 'Add a note' }).getByLabel('Note').fill('Pizza bestellt');
    await page.getByRole('dialog', { name: 'Add a note' }).getByRole('button', { name: 'Add' }).click();
    await expect(page.getByText('Pizza bestellt')).toBeVisible();
    await page.getByRole('button', { name: 'Close the week' }).click();
    await expect(page).toHaveURL(/\/$/);

    await page.goto(`/?woche=${shown}`);
    await expect(page.getByTestId('week-range')).toBeVisible();
    await expect(page.getByRole('link', { name: 'Close the week' })).toHaveCount(0);

    await page.getByRole('tab', { name: 'Plan again?' }).click();
    await expect(page.getByRole('complementary').getByRole('button', { name: skipped.title })).toBeVisible();

    await page.getByRole('link', { name: 'History' }).first().click();
    const week = page.getByRole('region', { name: new RegExp(past.slice(8, 10).replace(/^0/, '') + '\\.') }).first();
    await expect(page.getByRole('deletion').filter({ hasText: skipped.title })).toBeVisible();
    await expect(page.getByText('Pizza bestellt')).toBeVisible();
    await expect(week).toBeVisible();

    await page.getByRole('link', { name: eaten.title }).first().click();
    await expect(page.getByText(/Last eaten on/)).toBeVisible();
    expect(errors).toEqual([]);
});
