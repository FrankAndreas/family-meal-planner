import { describe, expect, it } from 'vitest';
import { formatAmount, parseAmount } from './amounts';

describe('parseAmount', () => {
    it.each([
        ['0,5', 0.5],
        ['0.5', 0.5],
        ['1/2', 0.5],
        ['1 1/2', 1.5],
        ['½', 0.5],
        ['1½', 1.5],
        ['¾', 0.75],
        ['⅓', 1 / 3],
        [' 250 ', 250],
        ['2,25', 2.25],
    ])('reads %s', (text, expected) => {
        expect(parseAmount(text)).toBeCloseTo(expected as number);
    });

    it('treats an empty field as no amount', () => {
        expect(parseAmount('')).toBeNull();
        expect(parseAmount('   ')).toBeNull();
    });

    it.each(['abc', '0', '-1', '1/0', '1,2,3', '2 x'])('refuses %s', (text) => {
        expect(parseAmount(text)).toBe('invalid');
    });
});

describe('formatAmount', () => {
    it.each([
        [347.5, 'de', '347½'],
        [0.5, 'de', '½'],
        [1.5, 'en', '1½'],
        [0.25, 'de', '¼'],
        [2.75, 'de', '2¾'],
        [0.45, 'de', '0,45'],
        [0.45, 'en', '0.45'],
        [2, 'de', '2'],
        [1.2, 'de', '1,2'],
        [1 / 3, 'en', '0.33'],
    ] as const)('shows %s in %s as %s', (amount, lang, expected) => {
        expect(formatAmount(amount, lang)).toBe(expected);
    });
});

describe('parseAmount and thousands', () => {
    it.each(['1.000', '1.500', '12.250'])('refuses %s, which could mean a thousand or one', (text) => {
        expect(parseAmount(text)).toBe('invalid');
    });

    it('still reads short decimals with a point', () => {
        expect(parseAmount('1.5')).toBe(1.5);
        expect(parseAmount('0.25')).toBe(0.25);
    });
});
