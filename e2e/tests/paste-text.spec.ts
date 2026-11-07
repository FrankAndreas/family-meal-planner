import { expect, test } from '@playwright/test';
import { login, newPerson, uniqueName } from './helpers';

const REEL = 'https://www.facebook.com/reel/2350975632311568';

test('a parent pastes a Facebook post with its link; the AI reads the text, the link stays the source', async ({ page, request }) => {
    const parent = await newPerson(request);
    const errors = await login(page, parent.name);
    const title = uniqueName('Brownies ');
    await page.goto('/posteingang');
    await page.getByRole('button', { name: 'Paste recipe text' }).click();
    await page.getByLabel('Recipe text').fill(`${title}\n• 3 ripe bananas\n• 3 tbsp cocoa powder\nBake: 180°C for 18–20 mins.`);
    await page.getByLabel('Source (link, optional)').fill(REEL);
    await page.getByRole('button', { name: 'Make a recipe of it' }).click();

    const card = page.getByRole('article').filter({ hasText: title });
    await expect(card.getByText('Draft ready')).toBeVisible({ timeout: 15_000 });
    await expect(card.getByRole('link', { name: 'Open link' })).toHaveAttribute('href', REEL);
    await card.getByRole('link', { name: 'Original' }).click();
    await expect(page.getByText('3 tbsp cocoa powder')).toBeVisible();
    await page.goBack();

    await card.getByRole('link', { name: 'Review draft' }).click();
    await page.getByRole('button', { name: 'Save recipe' }).click();
    await expect(page.getByText(new RegExp(`as text from ${parent.name}, \\d+\\.\\d+\\.\\d{4}`))).toBeVisible();
    expect(errors).toEqual([]);
});

test('a child pastes a text from the recipes page; it waits for a parent', async ({ page, request }) => {
    const child = await newPerson(request, 'CHILD');
    await login(page, child.name);
    const title = uniqueName('Pancakes ');
    await page.goto('/rezepte');
    await page.getByRole('button', { name: 'Add recipe' }).click();
    await page.getByRole('button', { name: 'Paste recipe text' }).click();
    // Too long: said so, not silently cut off
    await page.getByLabel('Recipe text').fill('x'.repeat(20_001));
    await expect(page.getByText('The text is too long (at most 20,000 characters).')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Make a recipe of it' })).toBeDisabled();
    await page.getByLabel('Recipe text').fill(`${title}\n2 eggs, 1 banana`);
    await page.getByRole('button', { name: 'Make a recipe of it' }).click();
    await expect(page).toHaveURL(/\/posteingang$/);
    await expect(page.getByRole('article').filter({ hasText: title }).getByText('Waiting for a parent')).toBeVisible();
});

test('a post in another language is translated while imported; the original can still be shown', async ({ page, request }) => {
    // The fake AI reads every recipe as German; the browser tests' family speaks English (DEFAULT_LANGUAGE=en)
    const parent = await newPerson(request);
    const errors = await login(page, parent.name);
    const title = uniqueName('Risotto ');
    await page.goto('/posteingang');
    await page.getByRole('button', { name: 'Paste recipe text' }).click();
    await page.getByLabel('Recipe text').fill(`${title}\n300 g Risottoreis`);
    await page.getByRole('button', { name: 'Make a recipe of it' }).click();

    const card = page.getByRole('article').filter({ hasText: title });
    await expect(card.getByText('Draft ready')).toBeVisible({ timeout: 15_000 });
    await card.getByRole('link', { name: 'Review draft' }).click();
    await expect(page.getByLabel('Title')).toHaveValue('EN Fake-Risotto');
    await page.getByRole('button', { name: 'Save recipe' }).click();
    await expect(page.getByRole('heading', { name: 'EN Fake-Risotto' }).first()).toBeVisible();
    // Already in the family's language: no translate button, but the original
    await expect(page.getByRole('button', { name: /^Translate into/ })).toHaveCount(0);
    await page.getByRole('button', { name: 'Show original' }).click();
    await expect(page.getByRole('heading', { name: 'Fake-Risotto', exact: true })).toBeVisible();
    expect(errors).toEqual([]);
});
