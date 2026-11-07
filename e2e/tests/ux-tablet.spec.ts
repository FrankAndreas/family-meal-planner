import { expect, test } from '@playwright/test';
import { call, createRecipe, login, newPerson, ownWeek } from './helpers';

// The iPad week grid found in the UX review (2026-11-06): it used half the screen and broke titles mid-word

test('the week grid fills the iPad and has room for titles', async ({ page, request }) => {
    const parent = await newPerson(request);
    const week = ownWeek();
    const start = (await call(request, parent, 'GET', `/plan?start=${week}`)).start;
    const recipe = await createRecipe(request, parent, { title: 'Älplermagronen' });
    await call(request, parent, 'POST', '/plan/entries', { date: start, slot: 'dinner', recipe_id: recipe.id });
    const errors = await login(page, parent.name);
    await page.goto(`/?woche=${week}`);
    // Room for a title like Älplermagronen on one line of text-xs: it was 77px. Measured as room rather than as the
    // rendered title, since how wide a word is depends on the fonts of the machine
    const chip = page.getByTestId('cell-sat-dinner').getByRole('button', { name: 'Älplermagronen' });
    await expect(chip).toBeVisible();
    const room = await chip.evaluate((el) => {
        const style = getComputedStyle(el);
        return el.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
    });
    expect(room).toBeGreaterThanOrEqual(88);
    // The grid reaches down to the bottom of the screen instead of stopping halfway
    const grid = (await page.getByTestId('week-grid').boundingBox())!;
    expect(grid.y + grid.height).toBeGreaterThan(page.viewportSize()!.height - 48);
    expect(errors).toEqual([]);
});

test.describe('the iPad held upright', () => {
    test.use({ viewport: { width: 820, height: 1180 } });

    test('shows the suggestions on the first screen, below the grid', async ({ page, request }) => {
        const parent = await newPerson(request);
        const errors = await login(page, parent.name);
        await page.goto(`/?woche=${ownWeek()}`);
        const search = (await page.getByRole('complementary').getByRole('searchbox').boundingBox())!;
        expect(search.y + search.height).toBeLessThan(page.viewportSize()!.height);
        expect(errors).toEqual([]);
    });
});
