import type { Ingredient, Recipe } from './recipes';

// Ingredients under their headings, in order (a heading used again later starts a group of its own there)
export function ingredientGroups(ingredients: Ingredient[]): { name: string | null; items: Ingredient[] }[] {
    const groups: { name: string | null; items: Ingredient[] }[] = [];
    for (const ingredient of ingredients) {
        const last = groups[groups.length - 1];
        if (last && last.name === ingredient.group) last.items.push(ingredient);
        else groups.push({ name: ingredient.group, items: [ingredient] });
    }
    return groups;
}

// The text before the translation, with today's amounts (they never change in a translation)
export function withOriginal(recipe: Recipe): Recipe {
    const original = recipe.original;
    if (!original) return recipe;
    return {
        ...recipe,
        title: original.title,
        steps: original.steps,
        notes: original.notes,
        ingredients: recipe.ingredients.map((i, n) => ({ ...i, ...(original.ingredients[n] ?? {}) })),
    };
}
