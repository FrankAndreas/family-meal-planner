import type { Category } from './categories';
import type { PhotoChoice } from './components/recipes/PhotoPicker';
import type { Draft } from './inbox';
import { ingredientsFrom, rowInvalid, type Row } from './ingredientRows';
import { isOtherLink, isWebLink } from './links';
import type { Recipe, RecipeInput } from './recipes';

// The recipe form's text fields, as typed (numbers too, so "1,5" or a half-typed one can be shown)
export interface RecipeForm {
    title: string;
    servings: string;
    servingsUnit: string;
    prep: string;
    cook: string;
    // Comma-separated
    tags: string;
    // One per line
    steps: string;
    notes: string;
    source: string;
}

export const EMPTY_FORM: RecipeForm = {
    title: '',
    servings: '4',
    servingsUnit: '',
    prep: '',
    cook: '',
    tags: '',
    steps: '',
    notes: '',
    source: '',
};

type FormSource = Pick<
    Recipe,
    'title' | 'servings' | 'servings_unit' | 'prep_minutes' | 'cook_minutes' | 'tags' | 'steps' | 'notes' | 'source_url'
>;

function formFrom(source: Partial<FormSource> & Pick<FormSource, 'title' | 'servings' | 'tags' | 'steps'>): RecipeForm {
    return {
        title: source.title,
        servings: String(source.servings),
        servingsUnit: source.servings_unit ?? '',
        prep: source.prep_minutes == null ? '' : String(source.prep_minutes),
        cook: source.cook_minutes == null ? '' : String(source.cook_minutes),
        tags: source.tags.join(', '),
        steps: source.steps.join('\n'),
        notes: source.notes ?? '',
        source: source.source_url ?? '',
    };
}

export const formFromRecipe = (recipe: Recipe): RecipeForm => formFrom(recipe);
// A draft from the inbox: its times, notes and source may be missing
export const formFromDraft = (draft: Draft): RecipeForm => formFrom(draft);

const servingsOf = (form: RecipeForm) => Number(form.servings.replace(',', '.'));
const minutes = (text: string) => (text.trim() === '' ? null : Math.max(0, Math.round(Number(text))));

// What keeps the recipe from being saved: no title, servings not between 0 and 100, an ingredient nobody can read, a
// photo link that isn't a web link, or a source that is another kind of link (javascript:, file:)
export function formInvalid(form: RecipeForm, rows: Row[], photo: PhotoChoice): boolean {
    const servings = servingsOf(form);
    return (
        !form.title.trim() ||
        !(servings > 0 && servings <= 100) ||
        rows.some(rowInvalid) ||
        (photo.kind === 'link' && !isWebLink(photo.url)) ||
        isOtherLink(form.source)
    );
}

// What is saved from the form; where it came from (source_kind, language, the inbox item) the caller adds
export function recipeInputFrom(
    form: RecipeForm,
    rows: Row[],
    categories: Category[],
): Omit<RecipeInput, 'source_kind' | 'language' | 'inbox_item_id'> {
    return {
        title: form.title.trim(),
        servings: servingsOf(form),
        servings_unit: form.servingsUnit.trim() || null,
        prep_minutes: minutes(form.prep),
        cook_minutes: minutes(form.cook),
        ingredients: ingredientsFrom(rows),
        steps: form.steps
            .split('\n')
            .map((s) => s.trim())
            .filter(Boolean),
        tags: form.tags
            .split(',')
            .map((s) => s.trim())
            .filter(Boolean),
        categories,
        notes: form.notes,
        source_url: form.source.trim() || null,
    };
}
