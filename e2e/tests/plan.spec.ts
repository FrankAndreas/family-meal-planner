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

async function drag(page: import('@playwright/test').Page, from: import('@playwright/test').Locator, to: import('@playwright/test').Locator) {
    const a = (await from.boundingBox())!;
    const b = (await to.boundingBox())!;
    await page.mouse.move(a.x + a.width / 2, a.y + a.height / 2);
    await page.mouse.down();
    await page.mouse.move(a.x + a.width / 2 + 12, a.y + a.height / 2, { steps: 3 });
    await page.mouse.move(b.x + b.width / 2, b.y + b.height / 2, { steps: 10 });
    await page.mouse.up();
}

test('drag a suggestion into the week, and an entry to another day', async ({ page, request }) => {
    const parent = await newPerson(request);
    const recipe = await createRecipe(request, parent);
    await call(request, parent, 'PUT', `/recipes/${recipe.id}/favorite`, { favorite: true });
    await login(page, parent.name);
    await page.goto(`/?woche=${ownWeek()}`);
    const card = page.getByRole('complementary').getByRole('button', { name: recipe.title });
    await drag(page, card, page.getByTestId('cell-tue-dinner'));
    await expect(page.getByTestId('cell-tue-dinner')).toContainText(recipe.title);

    const chip = page.getByTestId('cell-tue-dinner').getByRole('button', { name: recipe.title });
    await drag(page, chip, page.getByTestId('cell-wed-lunch'));
    await expect(page.getByTestId('cell-wed-lunch')).toContainText(recipe.title);
    await expect(page.getByTestId('cell-tue-dinner')).not.toContainText(recipe.title);
    // A drag is not a tap: no menu opened, nothing picked
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await expect(card).toHaveAttribute('aria-pressed', 'false');
});

test('on a touch screen: tap a card, then tap a cell', async ({ page, request }) => {
    const parent = await newPerson(request);
    const recipe = await createRecipe(request, parent);
    await call(request, parent, 'PUT', `/recipes/${recipe.id}/favorite`, { favorite: true });
    await login(page, parent.name);
    await page.goto(`/?woche=${ownWeek()}`);
    const card = page.getByRole('complementary').getByRole('button', { name: recipe.title });
    await card.tap();
    await expect(card).toHaveAttribute('aria-pressed', 'true');
    await page.getByRole('button', { name: 'Plan on Thursday, Lunch' }).tap();
    await expect(page.getByTestId('cell-thu-lunch')).toContainText(recipe.title);
});

test('two quick taps on + count twice', async ({ page, request }) => {
    const parent = await newPerson(request);
    const recipe = await createRecipe(request, parent);
    const week = ownWeek();
    const start = (await call(request, parent, 'GET', `/plan?start=${week}`)).start;
    const entry = await call(request, parent, 'POST', '/plan/entries', { date: start, slot: 'dinner', recipe_id: recipe.id });
    await login(page, parent.name);
    await page.goto(`/?woche=${week}`);
    await page.getByTestId('cell-sat-dinner').getByRole('button', { name: recipe.title }).click();
    // A slow answer, as on a busy NAS: the second tap comes before the first is answered
    await page.route('**/api/plan/entries/*', async (route) => {
        if (route.request().method() === 'PATCH') await new Promise((resolve) => setTimeout(resolve, 800));
        await route.continue();
    });
    const more = page.getByRole('dialog', { name: recipe.title }).getByRole('button', { name: 'More people' });
    await more.click();
    await more.click();
    await expect(page.getByRole('dialog', { name: recipe.title }).getByText('6 people')).toBeVisible();
    await expect.poll(async () => (await call(request, parent, 'GET', `/plan?start=${week}`)).entries[0].people).toBe(6);
    expect(entry.people).toBe(4);
});

test('a meal another device removed: a clear message, and it disappears', async ({ page, request }) => {
    const parent = await newPerson(request);
    const week = ownWeek();
    const start = (await call(request, parent, 'GET', `/plan?start=${week}`)).start;
    const entry = await call(request, parent, 'POST', '/plan/entries', { date: start, slot: 'lunch', note: 'Weg' });
    await login(page, parent.name);
    await page.goto(`/?woche=${week}`);
    await expect(page.getByTestId('cell-sat-lunch')).toContainText('Weg');
    await call(request, parent, 'DELETE', `/plan/entries/${entry.id}`);
    await page.getByTestId('cell-sat-lunch').getByRole('button', { name: 'Weg' }).click();
    await page.getByRole('dialog', { name: 'Weg' }).getByRole('button', { name: 'Remove' }).click();
    await expect(page.getByText('This meal is no longer in the plan.')).toBeVisible();
    await expect(page.getByTestId('cell-sat-lunch')).not.toContainText('Weg');
});
