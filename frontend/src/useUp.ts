import api from './api';
import type { RecipeSummary } from './recipes';

// Mirrors backend/app/use_up_api.py (the matching: use_up.py)
export type UseUpMode = 'use_up' | 'cook_now';

export interface UseUpResult extends RecipeSummary {
    used: string[];
    missing: string[];
}

export const fetchUseUp = async (have: string[], mode: UseUpMode) =>
    (await api.get<UseUpResult[]>('/api/use-up', { params: { have, mode }, paramsSerializer: { indexes: null } })).data;

export const fetchIngredientNames = async (q: string) =>
    (await api.get<string[]>('/api/ingredient-names', { params: { q } })).data;

// What was typed stays on this device, so going to a recipe and back keeps it (never shared, may be unavailable)
export interface UseUpState {
    tab: 'search' | 'use_up';
    have: string[];
    mode: UseUpMode;
}

const KEY = 'meals.useUp';
// The most ingredients one search takes (backend/app/use_up_api.py)
export const MAX_HAVE = 20;
// "Jetzt kochen" shows recipes missing at most this many ingredients (MAX_MISSING in backend/app/use_up.py)
export const MAX_MISSING = 2;
const EMPTY: UseUpState = { tab: 'search', have: [], mode: 'use_up' };

export function loadUseUp(): UseUpState {
    try {
        const stored = JSON.parse(localStorage.getItem(KEY) ?? 'null') as Partial<UseUpState> | null;
        if (!stored) return EMPTY;
        return {
            tab: stored.tab === 'use_up' ? 'use_up' : 'search',
            have: Array.isArray(stored.have) ? stored.have.filter((h) => typeof h === 'string').slice(0, MAX_HAVE) : [],
            mode: stored.mode === 'cook_now' ? 'cook_now' : 'use_up',
        };
    } catch {
        return EMPTY;
    }
}

export function saveUseUp(state: UseUpState): void {
    try {
        localStorage.setItem(KEY, JSON.stringify(state));
    } catch {
        // Private mode or blocked storage: it just forgets
    }
}

// Mirrors backend/app/schemas.py SwissmilkResult; `photo` is an address on this app's own backend
export interface SwissmilkResult {
    title: string;
    url: string;
    photo: string | null;
    used: string[];
    missing: string[];
    recipe_id: number | null;
    waiting: boolean;
}

export const fetchSwissmilk = async (have: string[], mode: UseUpMode) =>
    (await api.get<SwissmilkResult[]>('/api/use-up/swissmilk', { params: { have, mode }, paramsSerializer: { indexes: null } }))
        .data;

// The backend takes one Swissmilk search per person in this time (backend/app/swissmilk_api.py)
export const SWISSMILK_GAP_MS = 5000;
