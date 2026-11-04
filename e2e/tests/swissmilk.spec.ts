import { expect, test } from '@playwright/test';
import { createRecipe, login, newPerson } from './helpers';

// The app's own Swissmilk answers are stood in for: the backend's way to Swissmilk is covered by pytest, and no
// test switch may point the real backend anywhere else (plan 2026-11-01-swissmilk-search, Global Constraints)
const GRATIN = 'https://www.swissmilk.ch/de/rezepte-kochideen/rezepte/LM_div_0812_03/kartoffelgratin/';
const SALAT = 'https://www.swissmilk.ch/de/rezepte-kochideen/rezepte/LM_div_1013_01/kartoffelsalat/';

test('find and take over a Swissmilk recipe from What do I have?', async ({ page, request }) => {
    const parent = await newPerson(request);
    const mine = await createRecipe(request, parent, { source_url: SALAT });
    let searches = 0;
    await page.route('**/api/use-up/swissmilk?*', (route) => {
        searches += 1;
        return route.fulfill({
            json: [
                { title: 'Kartoffelgratin', url: GRATIN, photo: null, used: ['Kartoffeln'], missing: ['Milch'], recipe_id: null, waiting: false },
                { title: 'Kartoffelsalat', url: SALAT, photo: null, used: ['Kartoffeln'], missing: [], recipe_id: mine.id, waiting: false },
            ],
        });
    });
    const taken: unknown[] = [];
    await page.route('**/api/inbox/urls', async (route) => {
        taken.push(route.request().postDataJSON());
        // A slow answer: a second tap meanwhile must not take it over again
        await new Promise((resolve) => setTimeout(resolve, 500));
        await route.fulfill({ status: 201, json: { id: 1, kind: 'url', status: 'processing' } });
    });
    const errors = await login(page, parent.name);
    await page.goto('/rezepte');
    await page.getByRole('tab', { name: '🧺 What do I have?' }).click();
    const clear = page.getByRole('button', { name: 'Clear' });
    if (await clear.isVisible()) await clear.click();
    await page.getByLabel('What’s at home?').fill('Kartoffeln');
    await page.getByLabel('What’s at home?').press('Enter');
    expect(searches).toBe(0);
    await page.getByRole('button', { name: 'Also search Swissmilk' }).click();

    const section = page.getByRole('region', { name: 'Swissmilk' });
    const gratin = section.getByRole('listitem').filter({ hasText: 'Kartoffelgratin' });
    await expect(gratin).toContainText('✓ Kartoffeln');
    await expect(gratin).toContainText('missing: Milch');
    const view = gratin.getByRole('link', { name: 'View ↗' });
    await expect(view).toHaveAttribute('href', GRATIN);
    await expect(view).toHaveAttribute('target', '_blank');
    const salat = section.getByRole('listitem').filter({ hasText: 'Kartoffelsalat' });
    await expect(salat.getByRole('link', { name: 'already in your recipes' })).toHaveAttribute('href', `/rezepte/${mine.id}`);
    await expect(salat.getByRole('button', { name: 'Take over' })).toHaveCount(0);

    await gratin.getByRole('button', { name: 'Take over' }).dblclick();
    // The plain text shows while it is being sent; the link to the inbox only once the inbox has answered, so by then
    // the request has surely reached the route above
    await expect(gratin.getByRole('link', { name: 'waiting in the inbox' })).toHaveAttribute('href', '/posteingang');
    await expect(gratin.getByRole('button', { name: 'Take over' })).toHaveCount(0);
    expect(taken).toEqual([{ url: GRATIN }]);

    await clear.click();
    await expect(section).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Also search Swissmilk' })).toHaveCount(0);
    expect(errors).toEqual([]);
});
