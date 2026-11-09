import { describe, expect, it } from 'vitest';
import de from './locales/de';
import en from './locales/en';
import { formatSpec, type ShoppingLine } from './shoppingSpec';

const line = (amounts: [number, string | null][], extras: string[] = [], details: string[] = []): ShoppingLine => ({
    key: 'x',
    name: 'X',
    amounts: amounts.map(([amount, unit]) => ({ amount, unit })),
    extras,
    meals: [],
    staple: false,
    details,
    buy: true,
});

const german = (unit: string) => de.units[unit as keyof typeof de.units];
const english = (unit: string) => en.units[unit as keyof typeof en.units];

describe('formatSpec', () => {
    it('writes an amount with its unit', () => {
        expect(formatSpec(line([[500, 'g']]), german, 'de')).toBe('500 g');
    });

    it('adds the describing words after the amounts', () => {
        expect(formatSpec(line([[800, 'g']], [], ['mehligkochende']), german, 'de')).toBe('800 g, mehligkochende');
        expect(formatSpec(line([], [], ['glatter']), german, 'de')).toBe('glatter');
    });

    it('joins amounts that do not add up', () => {
        expect(formatSpec(line([[1, 'bunch'], [50, 'g']]), german, 'de')).toBe('1 Bund + 50 g');
    });

    it('writes decimals the way each language does', () => {
        expect(formatSpec(line([[1.2, 'l']]), german, 'de')).toBe('1,2 l');
        expect(formatSpec(line([[1.2, 'l']]), english, 'en')).toBe('1.2 l');
        // Halves as the recipe view writes them
        expect(formatSpec(line([[1.5, 'l']]), german, 'de')).toBe('1½ l');
    });

    it('writes a count without a unit', () => {
        expect(formatSpec(line([[5, null]]), german, 'de')).toBe('5');
    });

    it('adds the texts of free items', () => {
        expect(formatSpec(line([], ['2 Pack']), german, 'de')).toBe('2 Pack');
        expect(formatSpec(line([[500, 'g']], ['1 Pack']), german, 'de')).toBe('500 g + 1 Pack');
        expect(formatSpec(line([], ['']), german, 'de')).toBe('');
    });

    it('is empty without anything', () => {
        expect(formatSpec(line([]), german, 'de')).toBe('');
    });
});
