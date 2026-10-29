import { expect, test } from '@playwright/test';
import { call, createRecipe, login, newPerson, ownWeek } from './helpers';

test('the planner opens on the week of tomorrow', async ({ page, request }) => {
    const parent = await newPerson(request);
    const week = await call(request, parent, 'GET', '/plan');
    await login(page, parent.name);
    await expect(page.getByTestId('week-range')).toHaveAttribute('data-start', week.start);
});

test('tap a suggestion, then a cell, to plan it', async ({ page, request }) => {
    const parent = await newPerson(request);
    const recipe = await createRecipe(request, parent);
    await call(request, parent, 'PUT', `/recipes/${recipe.id}/favorite`, { favorite: true });
    const errors = await login(page, parent.name);
    await page.goto(`/?woche=${ownWeek()}`);
    await expect(page.getByText('0 of 28 planned')).toBeVisible();

    await page.getByRole('tab', { name: 'Favourites' }).click();
    const card = page.getByRole('complementary').getByRole('button', { name: recipe.title });
    await card.click();
    await expect(card).toHaveAttribute('aria-pressed', 'true');
    await page.getByRole('button', { name: 'Plan on Saturday, Dinner' }).click();
    await expect(page.getByTestId('cell-sat-dinner')).toContainText(recipe.title);
    await expect(page.getByText('1 of 28 planned')).toBeVisible();

    // Tapping the card again lets go of it
    await card.click();
    await expect(card).toHaveAttribute('aria-pressed', 'false');
    await expect(page.getByRole('button', { name: /^Plan on / })).toHaveCount(0);
    expect(errors).toEqual([]);
});

test('a note, moving and the number of people', async ({ page, request }) => {
    const parent = await newPerson(request);
    const recipe = await createRecipe(request, parent);
    const week = ownWeek();
    await login(page, parent.name);
    await page.goto(`/?woche=${week}`);
    const start = (await call(request, parent, 'GET', `/plan?start=${week}`)).start;
    await call(request, parent, 'POST', '/plan/entries', { date: start, slot: 'dinner', recipe_id: recipe.id });
    await page.reload();

    await page.getByRole('button', { name: 'Add to Sunday, Lunch' }).click();
    const dialog = page.getByRole('dialog', { name: 'Add a note' });
    await dialog.getByRole('button', { name: 'Pizza night' }).click();
    await expect(page.getByTestId('cell-sun-lunch')).toContainText('Pizza night');
    await expect(page.getByText('2 of 28 planned')).toBeVisible();

    await page.getByTestId('cell-sat-dinner').getByRole('button', { name: recipe.title }).click();
    const menu = page.getByRole('dialog', { name: recipe.title });
    await menu.getByRole('button', { name: 'More people' }).click();
    await expect(menu.getByText('5 people')).toBeVisible();
    await menu.getByRole('button', { name: 'Move', exact: true }).click();
    await page.getByRole('button', { name: 'Move to Monday, Dinner' }).click();
    await expect(page.getByTestId('cell-mon-dinner')).toContainText(recipe.title);
    await expect(page.getByTestId('cell-sat-dinner')).not.toContainText(recipe.title);
    await page.reload();
    await expect(page.getByTestId('cell-mon-dinner')).toContainText('5 P.');

    await page.getByTestId('cell-mon-dinner').getByRole('button', { name: recipe.title }).click();
    await page.getByRole('dialog', { name: recipe.title }).getByRole('button', { name: 'Remove' }).click();
    await expect(page.getByTestId('cell-mon-dinner')).not.toContainText(recipe.title);
});

test('a child sees what a parent planned', async ({ page, request }) => {
    const parent = await newPerson(request);
    const child = await newPerson(request, 'CHILD');
    const week = ownWeek();
    const start = (await call(request, parent, 'GET', `/plan?start=${week}`)).start;
    await call(request, parent, 'POST', '/plan/entries', { date: start, slot: 'breakfast', note: 'Zopf' });
    await login(page, child.name);
    await page.goto(`/?woche=${week}`);
    await expect(page.getByTestId('cell-sat-breakfast')).toContainText('Zopf');
});
