import { describe, expect, it } from 'vitest';
import type { Draft } from './inbox';
import { emptyRow } from './ingredientRows';
import type { Recipe } from './recipes';
import { EMPTY_FORM, formFromDraft, formFromRecipe, formInvalid, recipeInputFrom, type RecipeForm } from './recipeForm';

const recipe = {
    title: 'Risotto',
    servings: 4,
    servings_unit: null,
    prep_minutes: 10,
    cook_minutes: null,
    tags: ['Vegi', 'Schnell'],
    steps: ['Anbraten', 'Köcheln'],
    notes: 'Mit Parmesan',
    source_url: 'https://example.ch/risotto',
} as unknown as Recipe;

const filled: RecipeForm = { ...EMPTY_FORM, title: 'Risotto', servings: '4' };

describe('formFromRecipe and formFromDraft', () => {
    it('writes a recipe into the form’s text fields', () => {
        expect(formFromRecipe(recipe)).toEqual({
            title: 'Risotto',
            servings: '4',
            servingsUnit: '',
            prep: '10',
            cook: '',
            tags: 'Vegi, Schnell',
            steps: 'Anbraten\nKöcheln',
            notes: 'Mit Parmesan',
            source: 'https://example.ch/risotto',
        });
    });

    it('takes a draft whose times and notes may be missing', () => {
        const draft = { ...recipe, prep_minutes: undefined, notes: undefined, source_url: undefined } as unknown as Draft;
        expect(formFromDraft(draft)).toMatchObject({ prep: '', notes: '', source: '' });
    });
});

describe('formInvalid', () => {
    const rows = [emptyRow()];
    it('needs a title and servings between 0 and 100 (a comma counts as a point)', () => {
        expect(formInvalid(filled, rows, { kind: 'keep' })).toBe(false);
        expect(formInvalid({ ...filled, title: '  ' }, rows, { kind: 'keep' })).toBe(true);
        expect(formInvalid({ ...filled, servings: '0' }, rows, { kind: 'keep' })).toBe(true);
        expect(formInvalid({ ...filled, servings: '101' }, rows, { kind: 'keep' })).toBe(true);
        expect(formInvalid({ ...filled, servings: '1,5' }, rows, { kind: 'keep' })).toBe(false);
    });

    it('refuses an unreadable ingredient, a photo link that isn’t one, and a source that is another kind of link', () => {
        expect(formInvalid(filled, [{ ...emptyRow(), amountText: 'viel', name: 'Reis' }], { kind: 'keep' })).toBe(true);
        expect(formInvalid(filled, rows, { kind: 'link', url: 'nicht ein link' })).toBe(true);
        expect(formInvalid({ ...filled, source: 'javascript:alert(1)' }, rows, { kind: 'keep' })).toBe(true);
    });
});

describe('recipeInputFrom', () => {
    it('trims the text and splits steps by line and tags by comma, leaving out empty ones', () => {
        const form = {
            ...filled,
            title: ' Risotto ',
            servings: '2,5',
            servingsUnit: ' ',
            prep: '12.6',
            cook: '-5',
            tags: 'Vegi, , Schnell ',
            steps: ' Anbraten \n\nKöcheln',
            source: ' ',
        };
        expect(recipeInputFrom(form, [{ ...emptyRow(), name: 'Reis' }], ['main'])).toEqual({
            title: 'Risotto',
            servings: 2.5,
            servings_unit: null,
            prep_minutes: 13,
            cook_minutes: 0,
            ingredients: [{ group: null, amount: null, unit: null, name: 'Reis', note: '' }],
            steps: ['Anbraten', 'Köcheln'],
            tags: ['Vegi', 'Schnell'],
            categories: ['main'],
            notes: '',
            source_url: null,
        });
    });
});
