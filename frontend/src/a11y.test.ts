import { describe, expect, it } from 'vitest';

// Accessibility review (2026-11-08), with the theme's roles (themes 2026-11-28): text is text-ink or text-muted, both
// readable on the page. The theme's state and accent colours are light, so on a fill of them that is (nearly) solid,
// light text drops below the 4.5:1 text needs: it uses text-page (dark) there
const SOLID_FILL = /(?<![\w:/-])bg-(danger|success|warning|accent|accent-2|accent-3)(\/([7-9]\d|100))?(?![\w/-])/;
const LIGHT_TEXT = /(?<![\w:-])text-ink(?![\w-])/;

// Every source file's text (Vite reads them; ui.ts defines ICON_OFF and is left out)
const SOURCES = import.meta.glob(['./**/*.{ts,tsx}', '!./**/*.test.ts', '!./ui.ts'], {
    query: '?raw',
    import: 'default',
    eager: true,
}) as Record<string, string>;

describe('contrast', () => {
    it('reads the sources', () => {
        expect(Object.keys(SOURCES)).toContain('./components/recipes/Stars.tsx');
    });

    it('no light text on a (nearly) solid state or accent fill', () => {
        const light = Object.entries(SOURCES).flatMap(([path, text]) =>
            text
                .split('\n')
                .map((line, n) => (SOLID_FILL.test(line) && LIGHT_TEXT.test(line) ? `${path}:${n + 1}` : null))
                .filter(Boolean),
        );
        expect(light).toEqual([]);
    });
});

describe('errors', () => {
    it('every error paragraph is announced when it appears (role="alert"), not only shown', () => {
        const silent = Object.entries(SOURCES).flatMap(([path, text]) =>
            text
                .split('\n')
                .map((line, n) => (line.includes('className={ERROR}') && !/role="(alert|status)"/.test(line) ? `${path}:${n + 1}` : null))
                .filter(Boolean),
        );
        expect(silent).toEqual([]);
    });
});
