import api from './api';

// Mirrors backend/app/schemas.py (RecipeSummary, RecipeOut)
export interface RecipeSummary {
    id: number;
    title: string;
    photo_url: string | null;
    tags: string[];
    servings: number;
    servings_unit: string | null;
    total_minutes: number | null;
    rating_avg: number | null;
    rating_count: number;
    my_rating: number | null;
    my_favorite: boolean;
    favorite_count: number;
    last_eaten: string | null;
    times_eaten: number;
}

export interface Ingredient {
    id: number;
    group: string | null;
    amount: number | null;
    unit: string | null;
    name: string;
    note: string;
    scaled_amount: number | null;
}

export interface Recipe extends RecipeSummary {
    prep_minutes: number | null;
    cook_minutes: number | null;
    steps: string[];
    notes: string;
    source_kind: 'manual' | 'url' | 'mail';
    source_url: string | null;
    language: 'de' | 'en' | null;
    created_by_name: string | null;
    deleted: boolean;
    ingredients: Ingredient[];
    ratings: { user_id: number; name: string; stars: number }[];
    people: number | null;
    factor: number;
    inbox_item_id: number | null;
    // The text before an AI translation
    original: {
        title: string;
        ingredients: { name: string; note: string }[];
        steps: string[];
        notes: string;
        language: Recipe['language'];
    } | null;
}

export interface RecipeInput {
    title: string;
    servings: number;
    servings_unit: string | null;
    prep_minutes: number | null;
    cook_minutes: number | null;
    ingredients: { group: string | null; amount: number | null; unit: string | null; name: string; note: string }[];
    steps: string[];
    tags: string[];
    notes: string;
    source_kind?: Recipe['source_kind'];
    source_url?: string | null;
    language?: Recipe['language'];
    inbox_item_id?: number;
}

export interface RecipeFilter {
    q?: string;
    tag?: string;
    favorites?: '' | 'mine' | 'any';
}

export async function fetchRecipes(filter: RecipeFilter = {}): Promise<RecipeSummary[]> {
    const params = Object.fromEntries(Object.entries(filter).filter(([, value]) => value));
    return (await api.get<RecipeSummary[]>('/api/recipes', { params })).data;
}

export async function fetchRecipe(id: number | string, people?: number | null): Promise<Recipe> {
    return (await api.get<Recipe>(`/api/recipes/${id}`, { params: people ? { people } : {} })).data;
}

// How many people a recipe is for when nobody said otherwise: its own yield, or the family for "1 Blech"
export const defaultPeople = (recipe: RecipeSummary, familySize: number) =>
    recipe.servings_unit === null ? recipe.servings : familySize;
