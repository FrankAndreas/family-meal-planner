import { expect, test } from '@playwright/test';
import { login, newPerson } from './helpers';

test('a parent who makes themself a child loses the family sections at once, without an error', async ({ page, request }) => {
    const parent = await newPerson(request);
    await login(page, parent.name);
    await page.goto('/einstellungen');
    await page.getByLabel(`Role of ${parent.name}`).selectOption('CHILD');
    await expect(page.getByRole('heading', { name: 'Family members' })).toHaveCount(0);
    await expect(page.getByText('Only parents can do this.')).toHaveCount(0);
});

test('parents reset their own PIN under My settings, not in the members list', async ({ page, request }) => {
    const parent = await newPerson(request);
    const child = await newPerson(request, 'CHILD');
    await login(page, parent.name);
    await page.goto('/einstellungen');
    const own = page.getByRole('listitem').filter({ hasText: parent.name });
    await expect(own.getByRole('button', { name: 'Rename' })).toBeVisible();
    await expect(own.getByRole('button', { name: 'Reset PIN' })).toHaveCount(0);
    const other = page.getByRole('listitem').filter({ hasText: child.name });
    await expect(other.getByRole('button', { name: 'Reset PIN' })).toBeVisible();
});

test('a NAS that is restarting does not log the iPad out', async ({ page, request }) => {
    const parent = await newPerson(request);
    await login(page, parent.name);
    await page.route('**/api/me', (route) => route.fulfill({ status: 502, body: 'Bad Gateway' }));
    await page.reload();
    await page.unroute('**/api/me');
    await page.reload();
    await expect(page.getByRole('button', { name: 'Log out' })).toBeVisible();
});

test.describe('a French or Italian browser', () => {
    test.use({ locale: 'it-CH' });

    test('gets the app default language on the login page', async ({ page }) => {
        await page.route('**/api/config', (route) => route.fulfill({ json: { default_language: 'de' } }));
        await page.goto('/login');
        await expect(page.getByText('Wähle deinen Namen')).toBeVisible();
    });
});
