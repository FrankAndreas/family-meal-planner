import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { call, createRecipe, login, newPerson, ownWeek } from './helpers';

// Accessibility review 2026-11-08: axe finds nothing on any page, on the tablet and a phone (playwright.config.ts runs
// this file in both). Contrast on the glass cards axe can't measure: src/a11y.test.ts checks the colours
async function noViolations(page: Page, state: string) {
    const { violations } = await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice'])
        .analyze();
    expect(violations.map(v => `${v.id}: ${v.nodes.map(n => n.target.join(' ')).join(', ')}`), state).toEqual([]);
}

test('no accessibility violations on any page', async ({ page, request }) => {
    test.setTimeout(120_000);
    const parent = await newPerson(request);
    const recipe = await createRecipe(request, parent);
    const week = ownWeek();
    const errors = await login(page, parent.name);
    const start = (await call(request, parent, 'GET', `/plan?start=${week}`)).start;
    await call(request, parent, 'POST', '/plan/entries', { date: start, slot: 'dinner', recipe_id: recipe.id });
    const pages = [
        `/?woche=${week}`, '/rezepte', `/rezepte/${recipe.id}`, '/rezepte/neu', `/rezepte/${recipe.id}/bearbeiten`,
        '/woche-abschliessen', '/verlauf', '/einkaufsliste', '/posteingang', '/einstellungen',
    ];
    for (const path of pages) {
        await page.goto(path);
        // Loaded: the page's own title (a11y.spec.ts checks which) and its heading
        await expect(page).toHaveTitle(/ · Meal planner$/);
        await expect(page.getByRole('heading').first()).toBeVisible();
        await noViolations(page, path);
    }
    expect(errors).toEqual([]);
});

// On a phone the week plan shows one day: its tabs are named by weekday and date, and the arrow keys move between them
test('the day tabs on a phone', async ({ page, request }, info) => {
    test.skip(info.project.name !== 'phone', 'the tablet shows the whole week');
    const parent = await newPerson(request);
    await login(page, parent.name);
    await page.goto(`/?woche=${ownWeek()}`);
    const saturday = page.getByRole('tab', { name: /^Saturday \d+\.\d+\.$/ });
    await saturday.click();
    await expect(saturday).toHaveAttribute('aria-selected', 'true');
    await page.keyboard.press('ArrowRight');
    const sunday = page.getByRole('tab', { name: /^Sunday / });
    await expect(sunday).toBeFocused();
    await expect(sunday).toHaveAttribute('aria-selected', 'true');
    await expect(saturday).toHaveAttribute('tabindex', '-1');
});
