import { expect, test } from '@playwright/test';
import { call, createRecipe, login, newPerson, sendMail, uniqueName } from './helpers';

test('a child shares a recipe by mail; it waits for a parent', async ({ page, request }) => {
    const address = `${uniqueName('k')}@example.ch`;
    const child = await newPerson(request, 'CHILD', address);
    await login(page, child.name);
    // The address the child confirmed in the family hub, shown (not changed) in the settings
    await page.goto('/einstellungen');
    await expect(page.getByText(`Your address: ${address}`)).toBeVisible();

    const subject = uniqueName('Kuchen ');
    await sendMail(request, address, subject);
    await page.getByRole('link', { name: /Inbox/ }).first().click();
    const card = page.getByRole('article').filter({ hasText: subject });
    await expect(card.getByText('Waiting for a parent')).toBeVisible();
    await expect(card.getByRole('button', { name: 'Process' })).toHaveCount(0);

    await page.getByLabel('Recipe link').fill('https://www.swissmilk.ch/de/rezepte-kochideen/rezepte/LM201601_54/');
    await page.getByRole('button', { name: 'Add link' }).click();
    await expect(page.getByRole('article').filter({ hasText: 'www.swissmilk.ch' }).getByText('Waiting for a parent')).toBeVisible();
});

test('a parent processes a mail, checks the draft and saves it', async ({ page, request }) => {
    const address = `${uniqueName('p')}@example.ch`;
    const parent = await newPerson(request, 'PARENT', address);
    const subject = uniqueName('Risotto ');
    await sendMail(request, address, subject);

    const errors = await login(page, parent.name);
    await page.goto('/posteingang');
    const card = page.getByRole('article').filter({ hasText: subject });
    await expect(card.getByRole('img', { name: 'screenshot.png' })).toBeVisible();
    await card.getByRole('button', { name: 'Process' }).click();
    await expect(card.getByText('Draft ready')).toBeVisible({ timeout: 15_000 });
    await card.getByRole('link', { name: 'Review draft' }).click();

    // The fake AI reads it in German; the browser tests' family speaks English (DEFAULT_LANGUAGE=en): translated
    await expect(page.getByLabel('Title')).toHaveValue('EN Fake-Risotto');
    await expect(page.getByRole('list', { name: 'Please check' })).toContainText('1 l oder 1,2 l Bouillon?');
    await page.getByLabel('Title').fill(subject);
    await page.getByRole('button', { name: 'Save recipe' }).click();
    await expect(page.getByRole('heading', { name: subject })).toBeVisible();
    await expect(page.getByText(new RegExp(`by mail from ${parent.name}, \\d+\\.\\d+\\.\\d{4}`))).toBeVisible();
    await page.getByRole('link', { name: 'View original' }).click();
    await expect(page.getByText(subject)).toBeVisible();
    expect(errors).toEqual([]);
});

test('a parent translates a German recipe into the family language, and can show the original', async ({ page, request }) => {
    const parent = await newPerson(request);
    const title = uniqueName('Pfannkuchen ');
    const recipe = await createRecipe(request, parent, { title, language: 'de', steps: ['Mischen.'] });
    await login(page, parent.name);
    await page.goto(`/rezepte/${recipe.id}`);
    await page.getByRole('button', { name: 'Translate into English' }).click();
    await expect(page.getByRole('heading', { name: `EN ${title}` })).toBeVisible();
    await page.getByRole('button', { name: 'Show original' }).click();
    await expect(page.getByRole('heading', { name: title, exact: true })).toBeVisible();

    await page.goto('/einstellungen');
    await expect(page.getByRole('region', { name: 'AI usage' })).toContainText(`${parent.name}: 1`);
});

test('a recipe link is pasted on the recipes page and lands in the inbox', async ({ page, request }) => {
    const child = await newPerson(request, 'CHILD');
    await login(page, child.name);
    await page.goto('/rezepte');
    await expect(page.getByLabel('Recipe link')).toHaveCount(0);
    await page.getByRole('button', { name: 'Add recipe' }).click();
    await page.getByRole('button', { name: 'Import from link' }).click();
    await page.getByLabel('Recipe link').fill('https://www.fooby.ch/de/rezepte/12345/risotto');
    await page.getByRole('button', { name: 'Add link' }).click();
    await expect(page).toHaveURL(/\/posteingang$/);
    await expect(page.getByRole('article').filter({ hasText: 'www.fooby.ch' }).getByText('Waiting for a parent')).toBeVisible();
});

test('an imported draft comes with its categories; an older draft without any still opens', async ({ page, request }) => {
    const address = `${uniqueName('p')}@example.ch`;
    const parent = await newPerson(request, 'PARENT', address);
    const subject = uniqueName('Risotto ');
    await sendMail(request, address, subject);
    const errors = await login(page, parent.name);
    await page.goto('/posteingang');
    const card = page.getByRole('article').filter({ hasText: subject });
    await card.getByRole('button', { name: 'Process' }).click();
    await expect(card.getByText('Draft ready')).toBeVisible({ timeout: 15_000 });
    await card.getByRole('link', { name: 'Review draft' }).click();
    const form = page.getByRole('group', { name: 'Categories' });
    await expect(form.getByRole('button', { name: 'Main dish' })).toHaveAttribute('aria-pressed', 'true');
    await expect(form.getByRole('button', { name: 'Dessert' })).toHaveAttribute('aria-pressed', 'false');

    // A draft made before categories existed has no such field
    const draftUrl = page.url();
    await page.route('**/api/inbox/*', async (route) => {
        const response = await route.fetch();
        const item = await response.json();
        if (item.draft) delete item.draft.categories;
        await route.fulfill({ response, json: item });
    });
    await page.goto(draftUrl);
    await expect(page.getByLabel('Title')).toHaveValue('EN Fake-Risotto');
    await expect(form.getByRole('button', { name: 'Main dish' })).toHaveAttribute('aria-pressed', 'false');
    expect(errors).toEqual([]);
});
