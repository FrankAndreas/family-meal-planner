import { expect, test } from '@playwright/test';
import { FRONTEND, addToHub, hubLogin, login, newPerson, uniqueName } from './helpers';

test('a NAS that is restarting does not log the iPad out', async ({ page, request }) => {
    const parent = await newPerson(request);
    await login(page, parent.name);
    await page.route('**/api/me', (route) => route.fulfill({ status: 502, body: 'Bad Gateway' }));
    await page.reload();
    // Says so and offers to try again, instead of loading forever
    await expect(page.getByRole('button', { name: 'Try again' })).toBeVisible();
    await page.unroute('**/api/me');
    await page.getByRole('button', { name: 'Try again' }).click();
    await expect(page.getByRole('button', { name: 'Log out' })).toBeVisible();
});

test.describe('a French or Italian browser', () => {
    test.use({ locale: 'it-CH' });

    test('gets the app default language on the "no access" page', async ({ page, request }) => {
        const name = uniqueName('N');
        await addToHub(request, name, 'PARENT', false);
        await page.route('**/api/config', (route) => route.fulfill({ json: { default_language: 'de' } }));
        await page.context().addCookies([{ name: 'hub_session', value: (await hubLogin(name)).token, url: FRONTEND }]);
        await page.goto('/');
        await expect(page.getByRole('heading', { name: 'Kein Zugang' })).toBeVisible();
    });
});
