import { expect, test } from '@playwright/test';
import { API, addToHub, giveAccess, login, newPerson, uniqueName } from './helpers';

test('a parent sets the first day of the week and the family size', async ({ page, request }) => {
    const parent = await newPerson(request);
    const errors = await login(page, parent.name);
    await page.goto('/einstellungen');
    await page.getByLabel('First day of the week').selectOption({ label: 'Monday' });
    await page.getByLabel('People at the table').fill('5');
    await page.getByRole('button', { name: 'Save family settings' }).click();
    await expect(page.getByText('Saved')).toBeVisible();
    await page.reload();
    await expect(page.getByLabel('First day of the week')).toHaveValue('0');
    await expect(page.getByLabel('People at the table')).toHaveValue('5');
    // Back to the defaults, so other tests start from a fresh install's settings
    await request.patch(`${API}/settings`, {
        data: { family_size: 4, week_start: 5 },
        headers: { Authorization: `Bearer ${parent.token}` },
    });
    expect(errors).toEqual([]);
});

// The family comes from the hub (spec 2026-10-30): a child added there appears here, and sees only their own settings
test('a child added in the hub appears, and sees only their own settings', async ({ page, request }) => {
    const parent = await newPerson(request);
    const child = await newPerson(request, 'CHILD');
    await login(page, parent.name);
    await page.goto('/einstellungen');
    await expect(page.getByRole('listitem').filter({ hasText: child.name })).toContainText('Child');

    await login(page, child.name);
    await page.goto('/einstellungen');
    await expect(page.getByRole('heading', { name: 'My settings' })).toBeVisible();
    await expect(page.getByText('Your language, your PIN and logging out on every device are in the family hub.')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Family members' })).toHaveCount(0);
    await expect(page.getByLabel('First day of the week')).toHaveCount(0);
});

// Removed in the hub: hidden here with their stars, until a parent deletes their data
test('someone removed in the hub is deleted here by a parent', async ({ page, request }) => {
    const parent = await newPerson(request);
    const name = uniqueName('Gone');
    const hubId = await addToHub(request, name, 'CHILD');
    await login(page, name);
    await giveAccess(request, hubId, false);
    await login(page, parent.name);
    await page.goto('/einstellungen');
    await expect(page.getByRole('heading', { name: 'Removed in the family hub' })).toBeVisible();
    await page.getByRole('button', { name: `Delete data of ${name}` }).click();
    await expect(page.getByRole('button', { name: `Delete data of ${name}` })).toHaveCount(0);
});
