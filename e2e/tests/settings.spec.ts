import { expect, test } from '@playwright/test';
import { API, login, newPerson, PIN, uniqueName } from './helpers';

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

test('a parent adds a child, who sees only their own settings', async ({ page, request }) => {
    const parent = await newPerson(request);
    await login(page, parent.name);
    await page.goto('/einstellungen');
    const child = uniqueName('K');
    await page.getByLabel('Name of the new person').fill(child);
    await page.getByLabel('PIN of the new person').fill(PIN);
    await page.getByLabel('Role of the new person').selectOption('CHILD');
    await page.getByRole('button', { name: 'Add person' }).click();
    await expect(page.getByRole('listitem').filter({ hasText: child })).toContainText('Child');

    await page.getByRole('button', { name: 'Log out' }).click();
    await login(page, child);
    await page.goto('/einstellungen');
    await expect(page.getByRole('heading', { name: 'My settings' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Family members' })).toHaveCount(0);
    await expect(page.getByLabel('First day of the week')).toHaveCount(0);
});

test('renaming to a name that exists shows the error in words', async ({ page, request }) => {
    const parent = await newPerson(request);
    const other = await newPerson(request, 'CHILD');
    const child = await newPerson(request, 'CHILD');
    await login(page, parent.name);
    await page.goto('/einstellungen');
    const row = page.getByRole('listitem').filter({ hasText: child.name });
    await row.getByRole('button', { name: 'Rename' }).click();
    await row.getByLabel('New name').fill(other.name.toLowerCase());
    await row.getByRole('button', { name: 'Save' }).click();
    await expect(page.getByText('This name is already taken.')).toBeVisible();
});

test('changing your own PIN keeps you logged in on this device', async ({ page, request }) => {
    const parent = await newPerson(request);
    await login(page, parent.name);
    await page.goto('/einstellungen');
    await page.getByLabel('Current PIN').fill(PIN);
    await page.getByLabel('New PIN').fill('1357');
    await page.getByRole('button', { name: 'Change PIN' }).click();
    await expect(page.getByText('PIN changed')).toBeVisible();
    await page.reload();
    await expect(page.getByRole('heading', { name: 'My settings' })).toBeVisible();
});
