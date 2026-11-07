import api from './api';
import type { Category } from './categories';
import type { Language } from './i18n';
import type { Slot } from './plan';

// Mirrors backend/app/schemas.py (RecipeSummary, RecipeOut)
export interface RecipeSummary {
    id: number;
    title: string;
    photo_url: string | null;
    tags: string[];
    categories: Category[];
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
    source_kind: 'manual' | 'url' | 'mail' | 'scan' | 'text';
    source_url: string | null;
    language: 'de' | 'en' | null;
    created_by_name: string | null;
    deleted: boolean;
    ingredients: Ingredient[];
    ratings: { user_id: number; name: string; stars: number }[];
    people: number | null;
    factor: number;
    inbox_item_id: number | null;
    // The mail or pasted link it was saved from
    source_mail: { id: number; kind: 'mail' | 'url' | 'scan' | 'text'; user_name: string | null; received_at: string } | null;
    // The text before an AI translation
    original: {
        title: string;
        ingredients: { name: string; note: string }[];
        steps: string[];
        notes: string;
        language: Recipe['language'];
    } | null;
    // Not in the family's language: into which a parent can have it translated
    translate_into: Language | null;
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
    categories: Category[];
    notes: string;
    source_kind?: Recipe['source_kind'];
    source_url?: string | null;
    language?: Recipe['language'];
    inbox_item_id?: number;
}

export interface RecipeFilter {
    q?: string;
    tag?: string;
    category?: Category | 'none' | '';
    favorites?: '' | 'mine' | 'any';
}

export async function fetchRecipes(filter: RecipeFilter = {}): Promise<RecipeSummary[]> {
    const params = Object.fromEntries(Object.entries(filter).filter(([, value]) => value));
    return (await api.get<RecipeSummary[]>('/api/recipes', { params })).data;
}

export async function fetchRecipe(id: number | string, people?: number | null): Promise<Recipe> {
    return (await api.get<Recipe>(`/api/recipes/${id}`, { params: people ? { people } : {} })).data;
}

// A new recipe, or (id) the changed one
export const saveRecipe = async (id: number | string | null, body: RecipeInput) =>
    id ? (await api.put<Recipe>(`/api/recipes/${id}`, body)).data : (await api.post<Recipe>('/api/recipes', body)).data;
export const deleteRecipe = (id: number) => api.delete(`/api/recipes/${id}`);
// stars null: the person's rating taken back
export const rateRecipe = (id: number, stars: number | null) => api.put<Recipe>(`/api/recipes/${id}/rating`, { stars });
export const favoriteRecipe = (id: number, favorite: boolean) => api.put<Recipe>(`/api/recipes/${id}/favorite`, { favorite });
// Into the family's language, by the AI (parents)
export const translateRecipe = (id: number) => api.post<Recipe>(`/api/recipes/${id}/translate`);

export const uploadPhoto = (id: number, file: File) => {
    const body = new FormData();
    body.append('file', file);
    return api.post<Recipe>(`/api/recipes/${id}/photo`, body);
};
// A picture's link, or a page's: then the picture it shows when shared
export const photoFromLink = (id: number, url: string) => api.post<Recipe>(`/api/recipes/${id}/photo-url`, { url });
export const removePhoto = (id: number) => api.delete(`/api/recipes/${id}/photo`);

// The days it was eaten, newest first, and where it is planned from today on
export const fetchEatenOn = async (id: number | string) => (await api.get<string[]>(`/api/recipes/${id}/history`)).data;
export const fetchPlannedFor = async (id: number | string) =>
    (await api.get<{ date: string; slot: Slot }[]>(`/api/recipes/${id}/planned`)).data;

export const fetchTags = async () => (await api.get<{ name: string; count: number }[]>('/api/tags')).data;
export const fetchUnits = async () => (await api.get<string[]>('/api/units')).data;

// How many people a recipe is for when nobody said otherwise: its own yield, or the family for "1 Blech"
export const defaultPeople = (recipe: RecipeSummary, familySize: number) =>
    recipe.servings_unit === null ? recipe.servings : familySize;

// How many recipes without categories the AI hasn't sorted yet (parents)
export const fetchUncategorized = async () =>
    (await api.get<{ remaining: number }>('/api/recipes/categorize')).data.remaining;

// The AI sorts one recipe, or the next batch of recipes without categories (parents)
export const categorize = async (recipeId?: number) =>
    (await api.post<{ categorized: number; remaining: number }>('/api/recipes/categorize', { recipe_id: recipeId ?? null }))
        .data;
