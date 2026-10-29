import { describe, expect, it } from 'vitest';
import { ingredientsFrom, rowsFrom } from './ingredientRows';
import type { Ingredient } from './recipes';

const ingredient = (name: string, group: string | null): Ingredient => ({
    id: 0,
    group,
    amount: 1,
    unit: null,
    name,
    note: '',
    scaled_amount: 1,
});

describe('rowsFrom and back', () => {
    it('keeps ungrouped ingredients after a group out of it', () => {
        const original = [ingredient('Mehl', 'Teig'), ingredient('Salz', null)];
        const again = ingredientsFrom(rowsFrom(original, 'de'));
        expect(again.map((i) => [i.name, i.group])).toEqual([
            ['Mehl', 'Teig'],
            ['Salz', null],
        ]);
    });

    it('keeps groups that follow each other', () => {
        const original = [ingredient('Mehl', 'Teig'), ingredient('Rahm', 'Sauce'), ingredient('Käse', 'Sauce')];
        expect(ingredientsFrom(rowsFrom(original, 'de')).map((i) => i.group)).toEqual(['Teig', 'Sauce', 'Sauce']);
    });
});
