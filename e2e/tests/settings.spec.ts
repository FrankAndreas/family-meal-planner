import { expect, test } from '@playwright/test';
import { API, addToHub, call, giveAccess, login, newPerson, uniqueName } from './helpers';

test('a parent sets the first day of the week and the family size', async ({ page, request }) => {
    const parent = await newPerson(request);
    const errors = await login(page, parent.name);
    await page.goto('/einstellungen');
    await page.getByLabel('First day of the week').selectOption({ label: 'Monday' });
    await page.getByLabel('People at the table').fill('5');
    // Saved as soon as it changes, like the mail addresses and Bring! (UX review 2026-11-06)
    await expect(page.getByRole('button', { name: /Save/ })).toHaveCount(0);
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

// UX review (2026-11-06): the owner of a new mail address defaults to the parent adding it, and says so
test('a new mail address belongs to me unless I choose someone', async ({ page, request }) => {
    const parent = await newPerson(request);
    await login(page, parent.name);
    await page.goto('/einstellungen');
    const owner = page.getByRole('combobox', { name: 'Belongs to' });
    await expect(owner.locator('option:checked')).toHaveText('Me');
});

// Review of round 3: saving on change must never save a half-typed size, nor lose a change whose save failed
test('a size typed out of range is not saved, not even the half typed before it', async ({ page, request }) => {
    const parent = await newPerson(request);
    const before = (await call(request, parent, 'GET', '/settings')).family_size;
    const errors = await login(page, parent.name);
    await page.goto('/einstellungen');
    const size = page.getByLabel('People at the table');
    await size.fill('');
    await size.pressSequentially('25');
    await size.blur();
    await expect(size).toHaveValue(String(before));
    await page.waitForTimeout(1000);
    expect((await call(request, parent, 'GET', '/settings')).family_size).toBe(before);
    expect(errors).toEqual([]);
});

test('a change whose save failed is saved with the next one', async ({ page, request }) => {
    const parent = await newPerson(request);
    const before = await call(request, parent, 'GET', '/settings');
    await login(page, parent.name);
    await page.goto('/einstellungen');
    let failed = false;
    await page.route('**/api/settings', (route) => {
        if (route.request().method() !== 'PATCH' || failed) return route.continue();
        failed = true;
        return route.fulfill({ status: 500, json: { detail: 'Kaputt' } });
    });
    try {
        await page.getByLabel('First day of the week').selectOption({ label: before.week_start === 0 ? 'Tuesday' : 'Monday' });
        await expect(page.getByRole('alert')).toBeVisible();
        await expect(page.getByText('Saved')).toHaveCount(0);
        await page.getByLabel('People at the table').fill(String(before.family_size === 5 ? 6 : 5));
        await expect(page.getByText('Saved')).toBeVisible();
        await expect(page.getByRole('alert')).toHaveCount(0);
        const after = await call(request, parent, 'GET', '/settings');
        expect(after.week_start).toBe(before.week_start === 0 ? 1 : 0);
        expect(after.family_size).toBe(before.family_size === 5 ? 6 : 5);
    } finally {
        await call(request, parent, 'PATCH', '/settings', { family_size: before.family_size, week_start: before.week_start });
    }
});
