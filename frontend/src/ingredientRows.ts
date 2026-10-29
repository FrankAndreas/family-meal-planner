import { formatAmount, parseAmount } from './amounts';
import type { Language } from './i18n';
import type { Ingredient, RecipeInput } from './recipes';

// One line of the editor: an ingredient, or a heading ("Für den Teig") for the ingredients below it
export interface Row {
    key: number;
    kind: 'ingredient' | 'group';
    amountText: string;
    unit: string;
    name: string;
    note: string;
}

let nextKey = 1;
export const emptyRow = (kind: Row['kind'] = 'ingredient'): Row => ({
    key: nextKey++,
    kind,
    amountText: '',
    unit: '',
    name: '',
    note: '',
});

export function rowsFrom(ingredients: Ingredient[], lang: Language): Row[] {
    const rows: Row[] = [];
    let group: string | null = null;
    for (const i of ingredients) {
        if (i.group !== group && i.group) rows.push({ ...emptyRow('group'), name: i.group });
        group = i.group;
        rows.push({
            ...emptyRow(),
            amountText: i.amount === null ? '' : formatAmount(i.amount, lang),
            unit: i.unit ?? '',
            name: i.name,
            note: i.note,
        });
    }
    return rows.length ? rows : [emptyRow()];
}

// An amount nobody could read, or an amount without a name, keeps the recipe from being saved
export const rowInvalid = (row: Row) =>
    row.kind === 'ingredient' &&
    (parseAmount(row.amountText) === 'invalid' || (!row.name.trim() && (row.amountText.trim() || row.note.trim())));

export function ingredientsFrom(rows: Row[]): RecipeInput['ingredients'] {
    const result: RecipeInput['ingredients'] = [];
    let group: string | null = null;
    for (const row of rows) {
        if (row.kind === 'group') {
            group = row.name.trim() || null;
            continue;
        }
        if (!row.name.trim()) continue;
        const amount = parseAmount(row.amountText);
        result.push({
            group,
            amount: amount === 'invalid' ? null : amount,
            unit: row.unit || null,
            name: row.name.trim(),
            note: row.note.trim(),
        });
    }
    return result;
}
