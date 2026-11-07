import api from './api';
import type { Schemas } from './apiTypes';
import type { Category } from './categories';
import type { Slot } from './plan';

// The backend's bodies (backend/app/schemas.py), generated
export type RecipeSummary = Schemas['RecipeSummary'];
export type Ingredient = Schemas['IngredientOut'];
export type Recipe = Schemas['RecipeOut'];
export type RecipeInput = Schemas['RecipeIn'];
export type TagCount = Schemas['TagCount'];

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

// A stored photo's address, by its name (a draft's photo before it belongs to a recipe)
export const photoPath = (name: string) => `/api/photos/${name}`;

export const fetchTags = async () => (await api.get<TagCount[]>('/api/tags')).data;
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
