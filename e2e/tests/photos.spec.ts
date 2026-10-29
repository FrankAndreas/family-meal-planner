import { expect, test, type APIRequestContext, type Page } from '@playwright/test';
import { API, createRecipe, login, newPerson, type Person } from './helpers';

// A real (tiny) picture: 2×2 red PNG
const PNG = Buffer.from(
    'iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFklEQVR4nGM8ISfHwMDAxMDAwMDAAAANBAEIfXHKZgAAAABJRU5ErkJggg==',
    'base64',
);

async function photoUrl(request: APIRequestContext, person: Person, id: number): Promise<string | null> {
    const response = await request.get(`${API}/recipes/${id}`, { headers: { Authorization: `Bearer ${person.token}` } });
    return (await response.json()).photo_url;
}

async function saveAndWait(page: Page, id: number) {
    await page.getByRole('button', { name: 'Save recipe' }).click();
    await expect(page).toHaveURL(new RegExp(`/rezepte/${id}$`));
}

test('a photo is chosen, shown before saving, changed and removed', async ({ page, request }) => {
    const child = await newPerson(request, 'CHILD');
    const recipe = await createRecipe(request, child);
    await login(page, child.name);
    await page.goto(`/rezepte/${recipe.id}/bearbeiten`);
    await expect(page.getByText('No photo yet')).toBeVisible();
    await page.getByLabel('Choose photo').setInputFiles({ name: 'a.png', mimeType: 'image/png', buffer: PNG });
    await expect(page.getByRole('img', { name: 'Photo preview' })).toBeVisible();
    await saveAndWait(page, recipe.id);
    const first = await photoUrl(request, child, recipe.id);
    expect(first).toBeTruthy();

    await page.goto(`/rezepte/${recipe.id}/bearbeiten`);
    await expect(page.getByRole('img', { name: 'Photo preview' })).toHaveAttribute('src', new RegExp(first!));
    await page.getByLabel('Change photo').setInputFiles({ name: 'b.png', mimeType: 'image/png', buffer: PNG });
    await saveAndWait(page, recipe.id);
    const second = await photoUrl(request, child, recipe.id);
    expect(second).toBeTruthy();
    expect(second).not.toBe(first);

    await page.goto(`/rezepte/${recipe.id}/bearbeiten`);
    await page.getByRole('button', { name: 'Remove photo' }).click();
    await expect(page.getByText('No photo yet')).toBeVisible();
    await saveAndWait(page, recipe.id);
    expect(await photoUrl(request, child, recipe.id)).toBeNull();
});

test('a copied picture is pasted as the photo', async ({ page, request }) => {
    const parent = await newPerson(request);
    const recipe = await createRecipe(request, parent);
    await login(page, parent.name);
    await page.goto(`/rezepte/${recipe.id}/bearbeiten`);
    await page.getByLabel('Or a link to the picture').click();
    await page.evaluate((bytes) => {
        const data = new DataTransfer();
        data.items.add(new File([new Uint8Array(bytes)], 'image.png', { type: 'image/png' }));
        document.activeElement!.dispatchEvent(new ClipboardEvent('paste', { clipboardData: data, bubbles: true, cancelable: true }));
    }, [...PNG]);
    await expect(page.getByRole('img', { name: 'Photo preview' })).toBeVisible();
    await expect(page.getByLabel('Or a link to the picture')).toHaveValue('');
    await saveAndWait(page, recipe.id);
    expect(await photoUrl(request, parent, recipe.id)).toBeTruthy();
});

test('a link without a picture says so and keeps the recipe', async ({ page, request }) => {
    const parent = await newPerson(request);
    const recipe = await createRecipe(request, parent);
    await login(page, parent.name);
    await page.goto(`/rezepte/${recipe.id}/bearbeiten`);
    await page.getByLabel('Or a link to the picture').fill('http://127.0.0.1/bild.jpg');
    await page.getByRole('button', { name: 'Save recipe' }).click();
    await expect(page.getByText('No picture was found at this link.')).toBeVisible();
    expect(await photoUrl(request, parent, recipe.id)).toBeNull();
});
