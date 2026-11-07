import { describe, expect, it } from 'vitest';
import type { Ingredient, Recipe } from './recipes';
import { ingredientGroups, withOriginal } from './recipeView';

const ingredient = (id: number, name: string, group: string | null = null): Ingredient => ({
    id,
    group,
    amount: 1,
    unit: null,
    name,
    note: '',
    scaled_amount: 2,
});

describe('ingredientGroups', () => {
    it('keeps the order and starts a group at each new heading', () => {
        const groups = ingredientGroups([
            ingredient(1, 'Mehl', 'Teig'),
            ingredient(2, 'Butter', 'Teig'),
            ingredient(3, 'Äpfel', 'Belag'),
            ingredient(4, 'Zimt'),
        ]);
        expect(groups.map((g) => [g.name, g.items.map((i) => i.name)])).toEqual([
            ['Teig', ['Mehl', 'Butter']],
            ['Belag', ['Äpfel']],
            [null, ['Zimt']],
        ]);
    });

    it('a heading used again later is a group of its own there', () => {
        const groups = ingredientGroups([ingredient(1, 'A', 'X'), ingredient(2, 'B', 'Y'), ingredient(3, 'C', 'X')]);
        expect(groups.map((g) => g.name)).toEqual(['X', 'Y', 'X']);
    });
});

describe('withOriginal', () => {
    const recipe = {
        title: 'Saftige Brownies',
        steps: ['Mixen.'],
        notes: 'Warm servieren',
        ingredients: [ingredient(1, 'Bananen'), ingredient(2, 'Kakao')],
        original: {
            title: 'Fudgy brownies',
            steps: ['Blend.'],
            notes: 'Serve warm',
            ingredients: [{ name: 'bananas', note: 'ripe' }],
            language: 'en',
        },
    } as unknown as Recipe;

    it('shows the text before the translation, with today’s amounts', () => {
        const shown = withOriginal(recipe);
        expect([shown.title, shown.steps, shown.notes]).toEqual(['Fudgy brownies', ['Blend.'], 'Serve warm']);
        expect(shown.ingredients[0]).toMatchObject({ name: 'bananas', note: 'ripe', scaled_amount: 2 });
        // An ingredient the original doesn't have keeps its own text
        expect(shown.ingredients[1].name).toBe('Kakao');
    });

    it('a recipe without an original stays as it is', () => {
        const plain = { ...recipe, original: null } as Recipe;
        expect(withOriginal(plain)).toBe(plain);
    });
});
