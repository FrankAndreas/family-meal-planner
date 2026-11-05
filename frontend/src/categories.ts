// The recipe categories, in the order they're listed; mirrors backend/app/categories.py (texts: recipes.category.*)
export const CATEGORIES = ['breakfast', 'apero', 'starter', 'soup', 'salad', 'main', 'side', 'dessert', 'baking', 'snack'] as const;
export type Category = (typeof CATEGORIES)[number];

// The given ones, each once, in the list's order (unknown ones left out)
export const inOrder = (categories: readonly string[]): Category[] => CATEGORIES.filter((c) => categories.includes(c));
