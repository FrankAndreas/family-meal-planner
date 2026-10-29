import { expect, test } from '@playwright/test';
import { call, createRecipe, login, newPerson, sendMail, uniqueName } from './helpers';

test('a child shares a recipe by mail; it waits for a parent', async ({ page, request }) => {
    const child = await newPerson(request, 'CHILD');
    const address = `${uniqueName('k')}@example.ch`;
    await login(page, child.name);
    await page.goto('/einstellungen');
    await page.getByLabel('New mail address').fill(address);
    await page.getByRole('button', { name: 'Add address' }).click();
    await expect(page.getByText(address)).toBeVisible();

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
    const parent = await newPerson(request);
    const address = `${uniqueName('p')}@example.ch`;
    await call(request, parent, 'POST', '/emails', { address });
    const subject = uniqueName('Risotto ');
    await sendMail(request, address, subject);

    const errors = await login(page, parent.name);
    await page.goto('/posteingang');
    const card = page.getByRole('article').filter({ hasText: subject });
    await expect(card.getByRole('img', { name: 'screenshot.png' })).toBeVisible();
    await card.getByRole('button', { name: 'Process' }).click();
    await expect(card.getByText('Draft ready')).toBeVisible({ timeout: 15_000 });
    await card.getByRole('link', { name: 'Review draft' }).click();

    await expect(page.getByLabel('Title')).toHaveValue('Fake-Risotto');
    await expect(page.getByRole('list', { name: 'Please check' })).toContainText('1 l oder 1,2 l Bouillon?');
    await page.getByLabel('Title').fill(subject);
    await page.getByRole('button', { name: 'Save recipe' }).click();
    await expect(page.getByRole('heading', { name: subject })).toBeVisible();
    await expect(page.getByText(new RegExp(`by mail from ${parent.name}, \\d+\\.\\d+\\.\\d{4}`))).toBeVisible();
    await page.getByRole('link', { name: 'View original' }).click();
    await expect(page.getByText(subject)).toBeVisible();
    expect(errors).toEqual([]);
});

test('a parent translates an English recipe, and can show the original', async ({ page, request }) => {
    const parent = await newPerson(request);
    const title = uniqueName('Pancakes ');
    const recipe = await createRecipe(request, parent, { title, language: 'en', steps: ['Mix.'] });
    await login(page, parent.name);
    await page.goto(`/rezepte/${recipe.id}`);
    await page.getByRole('button', { name: 'Translate into German' }).click();
    await expect(page.getByRole('heading', { name: `DE ${title}` })).toBeVisible();
    await page.getByRole('button', { name: 'Show original' }).click();
    await expect(page.getByRole('heading', { name: title, exact: true })).toBeVisible();

    await page.goto('/einstellungen');
    await expect(page.getByRole('region', { name: 'AI usage' })).toContainText(`${parent.name}: 1`);
});
