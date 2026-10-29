import { expect, test } from '@playwright/test';
import { login, newPerson } from './helpers';

// A real (small) picture, standing in for a photo of the back of a pack
const PNG = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAACgAAAAeCAIAAADRv8uKAAAALElEQVR4nO3NMQEAAAQAMATRP4pYKvg8W4HldMeHelnFYrFYLBaLxWKxWHyyHdwBQE1gaCAAAAAASUVORK5CYII=', 'base64');
const photo = (name: string) => ({ name, mimeType: 'image/png', buffer: PNG });

test('a child photographs a recipe in the app; it waits in the inbox for a parent', async ({ page, request }) => {
    const child = await newPerson(request, 'CHILD');
    const errors = await login(page, child.name);
    await page.goto('/rezepte');
    await page.getByRole('button', { name: 'Photograph a recipe' }).click();
    await page.getByLabel('Choose from photos').setInputFiles([photo('front.png'), photo('back.png')]);
    await expect(page.getByRole('img', { name: /^Photo \d$/ })).toHaveCount(2);
    await page.getByRole('button', { name: 'Remove photo 1' }).click();
    await expect(page.getByRole('img', { name: /^Photo \d$/ })).toHaveCount(1);
    await page.getByLabel('Take a photo').setInputFiles(photo('more.png'));
    await expect(page.getByRole('img', { name: /^Photo \d$/ })).toHaveCount(2);
    await page.getByRole('button', { name: 'Make a recipe of it (2 photos)' }).click();

    await expect(page).toHaveURL(/\/posteingang$/);
    const card = page.getByRole('article').filter({ hasText: 'Scan ' }).first();
    await expect(card.getByText('Waiting for a parent')).toBeVisible();
    await expect(card.getByRole('img')).toHaveCount(2);
    expect(errors).toEqual([]);
});

test('a parent photographs a recipe; the AI reads it at once and it is saved as a photo', async ({ page, request }) => {
    const parent = await newPerson(request);
    await login(page, parent.name);
    await page.goto('/rezepte');
    await page.getByRole('button', { name: 'Photograph a recipe' }).click();
    await page.getByLabel('Take a photo').setInputFiles(photo('back.png'));
    await page.getByRole('button', { name: 'Make a recipe of it (1 photo)' }).click();

    await expect(page).toHaveURL(/\/posteingang$/);
    const card = page.getByRole('article').filter({ hasText: 'Scan ' }).filter({ hasText: parent.name });
    await expect(card.getByText('Draft ready')).toBeVisible({ timeout: 15_000 });
    await card.getByRole('link', { name: 'Review draft' }).click();
    await page.getByRole('button', { name: 'Save recipe' }).click();
    await expect(page.getByText(new RegExp(`as a photo from ${parent.name}, \\d+\\.\\d+\\.\\d{4}`))).toBeVisible();
});
