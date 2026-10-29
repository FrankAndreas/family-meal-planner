import { expect, test } from '@playwright/test';
import { ADMIN_PIN, login, newPerson } from './helpers';

test('Admin logs in and sees the app', async ({ page }) => {
    const errors = await login(page, 'Admin', ADMIN_PIN);
    await expect(page.getByText('Meal planner').first()).toBeVisible();
    await expect(page.getByRole('link', { name: 'Recipes' })).toBeVisible();
    expect(errors).toEqual([]);
});

test('a wrong PIN shows a message in words', async ({ page }) => {
    await page.goto('/login');
    await page.getByRole('button', { name: 'Admin', exact: true }).click();
    await page.locator('#pin').fill('0000');
    await page.locator('button[type=submit]').click();
    await expect(page.getByText('Wrong name or PIN.')).toBeVisible();
});

test('the chosen language follows the person, not the browser', async ({ page, request }) => {
    const parent = await newPerson(request);
    await login(page, parent.name);
    await page.goto('/einstellungen');
    await page.getByLabel('Language').selectOption('de');
    await expect(page.getByRole('link', { name: 'Wochenplan' })).toBeVisible();
    await page.reload();
    await expect(page.getByRole('link', { name: 'Wochenplan' })).toBeVisible();
    await page.getByRole('button', { name: 'Abmelden' }).click();
    // Logged out, the browser's language (English here) is back
    await expect(page.getByRole('button', { name: 'Log in' }).or(page.getByText('Pick your name'))).toBeVisible();
});

test.describe('a browser in neither German nor English', () => {
    test.use({ locale: 'fr-FR' });

    test('gets English, and the default language after login, never raw keys', async ({ page, request }) => {
        await page.goto('/login');
        await expect(page.getByText('Pick your name')).toBeVisible();
        const parent = await newPerson(request);
        await login(page, parent.name);
        // DEFAULT_LANGUAGE=en in the test backend
        await expect(page.getByRole('link', { name: 'Week plan' })).toBeVisible();
        await expect(page.locator('body')).not.toContainText(/\b(errors|login|nav|common|settings)\.[a-z]/);
    });
});
