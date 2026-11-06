import { expect, test, type APIRequestContext } from '@playwright/test';
import { call, login, newPerson, type Person } from './helpers';

// The shopping list and the Bring! login are one per family: each test starts without them
async function clean(request: APIRequestContext, parent: Person) {
    await call(request, parent, 'DELETE', '/shopping');
    await call(request, parent, 'DELETE', '/bring');
}

test('bring settings', async ({ page, request }) => {
    const parent = await newPerson(request);
    await clean(request, parent);
    const errors = await login(page, parent.name);
    await page.goto('/einstellungen');
    const section = page.getByRole('region', { name: 'Bring!' });
    await section.getByLabel('Email').fill('family@example.ch');
    await section.getByLabel('Password').fill('wrong');
    await section.getByRole('button', { name: 'Sign in' }).click();
    await expect(section.getByText('Bring! didn’t accept the email or the password.')).toBeVisible();

    await section.getByLabel('Password').fill('secret');
    await section.getByRole('button', { name: 'Sign in' }).click();
    const picker = section.getByLabel('List');
    await expect(picker.locator('option')).toHaveText(['Choose a list', 'Zuhause', 'Büro']);
    await picker.selectOption({ label: 'Zuhause' });
    await expect(section.getByText('Signed in as family@example.ch · list Zuhause')).toBeVisible();

    await page.reload();
    await expect(section.getByText('Signed in as family@example.ch · list Zuhause')).toBeVisible();
    await expect(section.getByLabel('Password')).toHaveCount(0);

    await section.getByRole('button', { name: 'Sign out of Bring!' }).click();
    await expect(section.getByLabel('Password')).toHaveValue('');
    await expect(section.getByText(/Signed in as/)).toHaveCount(0);
    // Only the refused wrong password
    expect(errors.filter((e) => !e.includes('400'))).toEqual([]);
});

test('children see no Bring! settings', async ({ page, request }) => {
    const child = await newPerson(request, 'CHILD');
    await login(page, child.name);
    await page.goto('/einstellungen');
    await expect(page.getByRole('heading', { name: 'My settings' })).toBeVisible();
    await expect(page.getByRole('region', { name: 'Bring!' })).toHaveCount(0);
});
