import { useEffect, useState } from 'react';
import { errorMessage } from '../api';
import { inOrder, type Category } from '../categories';
import i18next, { type Language } from '../i18n';
import { fetchItem, type InboxItemDetail } from '../inbox';
import { emptyRow, rowsFrom, type Row } from '../ingredientRows';
import { EMPTY_FORM, formFromDraft, formFromRecipe, type RecipeForm } from '../recipeForm';
import { fetchRecipe, type Recipe } from '../recipes';

// The recipe form's state, filled from the recipe being edited (`id`) or an inbox draft (`draftId`), or empty for a
// new recipe. A late answer must not overwrite what someone already typed
export function useRecipeToEdit(id: string | undefined, draftId: string | null) {
    const [original, setOriginal] = useState<Recipe | null>(null);
    const [draftItem, setDraftItem] = useState<InboxItemDetail | null>(null);
    const [form, setForm] = useState<RecipeForm>(EMPTY_FORM);
    const [rows, setRows] = useState<Row[]>(() => [emptyRow()]);
    const [categories, setCategories] = useState<Category[]>([]);
    const [error, setError] = useState('');

    useEffect(() => {
        if (!id) return;
        let current = true;
        fetchRecipe(id)
            .then((recipe) => {
                if (!current) return;
                setOriginal(recipe);
                setForm(formFromRecipe(recipe));
                setRows(rowsFrom(recipe.ingredients, i18next.language as Language));
                setCategories(inOrder(recipe.categories));
            })
            .catch((err) => current && setError(errorMessage(err)));
        return () => {
            current = false;
        };
    }, [id]);

    useEffect(() => {
        if (!draftId) return;
        let current = true;
        fetchItem(draftId)
            .then((item) => {
                const draft = item.draft;
                if (!draft || !current) return;
                setDraftItem(item);
                setForm(formFromDraft(draft));
                setCategories(inOrder(draft.categories ?? []));
                setRows(
                    rowsFrom(
                        draft.ingredients.map((i, n) => ({ ...i, id: n, group: null, scaled_amount: i.amount })),
                        i18next.language as Language,
                    ),
                );
            })
            .catch((err) => current && setError(errorMessage(err)));
        return () => {
            current = false;
        };
    }, [draftId]);

    return { original, draftItem, form, setForm, rows, setRows, categories, setCategories, error, setError };
}
