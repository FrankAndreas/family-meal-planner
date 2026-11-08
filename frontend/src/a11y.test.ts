import { describe, expect, it } from 'vitest';

// Accessibility review (2026-11-08): on the app's dark background (slate-900) slate-500 text reaches 3.75:1 and
// slate-600 2.36:1, below the 4.5:1 text needs (WCAG AA). Text uses slate-400 or brighter; an icon that is "off" (an
// empty star) uses ICON_OFF from ui.ts, 3:1 as an icon needs
const DIM = /\btext-slate-(500|600|700|800|900)\b/;

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

    it('no text in a colour too dim to read on the dark background', () => {
        const dim = Object.entries(SOURCES).flatMap(([path, text]) =>
            text
                .split('\n')
                .map((line, n) => (DIM.test(line) ? `${path}:${n + 1}` : null))
                .filter(Boolean),
        );
        expect(dim).toEqual([]);
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
