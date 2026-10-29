import { parseISO } from 'date-fns';
import api from './api';
import type { RecipeSummary } from './recipes';
import { WEEKDAYS } from './types';

// Mirrors backend/app/schemas.py (EntryOut, WeekOut); slots in the order of a day
export const SLOTS = ['breakfast', 'snack', 'lunch', 'dinner'] as const;
export type Slot = (typeof SLOTS)[number];
export type SuggestionTab = 'favorites' | 'long_ago' | 'new' | 'again';

export interface PlanEntry {
    id: number;
    date: string;
    slot: Slot;
    position: number;
    recipe: RecipeSummary | null;
    recipe_deleted: boolean;
    note: string | null;
    people: number | null;
    eaten: boolean;
}

export interface Week {
    start: string;
    end: string;
    days: string[];
    today: string;
    entries: PlanEntry[];
    closed: boolean;
    previous_needs_closing: boolean;
    planned_slots: number;
    total_slots: number;
}

export interface NewEntry {
    date: string;
    slot: Slot;
    recipe_id?: number;
    note?: string;
    people?: number;
}

export const fetchWeek = async (start?: string | null) =>
    (await api.get<Week>('/api/plan', { params: start ? { start } : {} })).data;
export const addEntry = async (body: NewEntry) => (await api.post<PlanEntry>('/api/plan/entries', body)).data;
export const updateEntry = async (id: number, patch: Partial<Omit<PlanEntry, 'id' | 'recipe'>>) =>
    (await api.patch<PlanEntry>(`/api/plan/entries/${id}`, patch)).data;
export const removeEntry = (id: number) => api.delete(`/api/plan/entries/${id}`);
export const fetchSuggestions = async (tab: SuggestionTab, q: string) =>
    (await api.get<RecipeSummary[]>('/api/suggestions', { params: { tab, ...(q ? { q } : {}) } })).data;

// "2026-10-31" → its locale key under weekdays.* (Python numbering, 0 = Monday)
export const weekdayKey = (day: string) => WEEKDAYS[(parseISO(day).getDay() + 6) % 7];
export const addDays = (day: string, days: number) => {
    const d = parseISO(day);
    d.setDate(d.getDate() + days);
    return [d.getFullYear(), String(d.getMonth() + 1).padStart(2, '0'), String(d.getDate()).padStart(2, '0')].join('-');
};
