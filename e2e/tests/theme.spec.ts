import { expect, test } from '@playwright/test';
import { FRONTEND, login, newPerson } from './helpers';

// Themes (family-hub design 2026-11-28): the family look from family-hub-theme, with the person's theme from the hub
test('the page loads theme-init.js', async ({ request }) => {
    const response = await request.get(`${FRONTEND}/theme-init.js`);
    expect(response.status()).toBe(200);
    expect(response.headers()['content-type']).toContain('javascript');
    expect(await response.text()).toContain('family-theme');
});

test('the person theme is applied after login', async ({ page, request }) => {
    const person = await newPerson(request);
    // A static file of the app's origin: '/' without a login goes on to the hub's login at once
    await page.goto('/theme-init.js');
    await page.evaluate(() => localStorage.removeItem('family-theme'));
    const errors = await login(page, person.name);
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'aurora');
    // Applied from who is logged in (written to storage), not only from the last page load
    await expect.poll(() => page.evaluate(() => localStorage.getItem('family-theme'))).toBe('aurora');
    // Asked again until it holds: a card being replaced while the page loads has no style
    await expect.poll(() => page.locator('.glass-card').first().evaluate(e => getComputedStyle(e).backdropFilter)).toContain('blur');
    expect(errors).toEqual([]);
});
