import { expect, test } from '@playwright/test';
import { FRONTEND, HUB, addToHub, hubLogin, login, newPerson, uniqueName } from './helpers';

// Logging in goes through the family hub (spec 2026-10-30): without its login the planner sends the browser there
test('not logged in → sent to the family hub', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveURL(new RegExp(`^${HUB}/\\?next=`));
});

test('a parent logs in and sees the app', async ({ page, request }) => {
    const parent = await newPerson(request);
    const errors = await login(page, parent.name);
    await expect(page.getByText('Meal planner').first()).toBeVisible();
    await expect(page.getByRole('link', { name: 'Recipes' })).toBeVisible();
    expect(errors).toEqual([]);
});

test('someone the hub doesn\'t give the planner sees "No access"', async ({ page, request }) => {
    const name = uniqueName('N');
    await addToHub(request, name, 'PARENT', false);
    const { token } = await hubLogin(name);
    await page.context().addCookies([{ name: 'hub_session', value: token, url: FRONTEND }]);
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'No access' })).toBeVisible();
    await page.getByRole('button', { name: 'Log in as someone else' }).click();
    await expect(page).toHaveURL(new RegExp(`^${HUB}/logout\\?next=${encodeURIComponent(FRONTEND)}`));
});

test('the language follows the person in the hub', async ({ page, request }) => {
    const parent = await newPerson(request);
    const changed = await request.fetch(`${HUB}/api/me`, {
        method: 'PATCH', data: { language: 'de' }, headers: { 'X-Requested-With': 'hub', Cookie: parent.hubCookies },
    });
    expect(changed.ok(), await changed.text()).toBeTruthy();
    await login(page, parent.name);
    await expect(page.getByRole('link', { name: 'Wochenplan' })).toBeVisible();
});

test('"Log out" ends the login in the hub, which leads back here', async ({ page, request }) => {
    const parent = await newPerson(request);
    await login(page, parent.name);
    await page.getByRole('button', { name: 'Log out' }).click();
    await expect(page).toHaveURL(new RegExp(`^${HUB}/logout\\?next=${encodeURIComponent(FRONTEND)}`));
});

test.describe('a browser in neither German nor English', () => {
    test.use({ locale: 'fr-FR' });

    test('gets the default language after login, never raw keys', async ({ page, request }) => {
        const parent = await newPerson(request);
        await login(page, parent.name);
        // DEFAULT_LANGUAGE=en in the test hub and backend
        await expect(page.getByRole('link', { name: 'Week plan' })).toBeVisible();
        await expect(page.locator('body')).not.toContainText(/\b(errors|access|nav|common|settings)\.[a-z]/);
    });
});
