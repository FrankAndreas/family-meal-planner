import { parseISO } from 'date-fns';
import api from './api';
import type { Schemas } from './apiTypes';
import type { RecipeSummary } from './recipes';
import { WEEKDAYS } from './types';

// Slots in the order of a day (the backend's Slot)
export const SLOTS = ['breakfast', 'snack', 'lunch', 'dinner'] as const;
export type Slot = (typeof SLOTS)[number];
export type SuggestionTab = 'favorites' | 'long_ago' | 'new' | 'again';

export type PlanEntry = Schemas['EntryOut'];
export type Week = Schemas['WeekOut'];
export type NewEntry = Schemas['EntryIn'];

export const fetchWeek = async (start?: string | null) =>
    (await api.get<Week>('/api/plan', { params: start ? { start } : {} })).data;
export const addEntry = async (body: NewEntry) => (await api.post<PlanEntry>('/api/plan/entries', body)).data;
export const updateEntry = async (id: number, patch: Partial<Omit<PlanEntry, 'id' | 'recipe'>>) =>
    (await api.patch<PlanEntry>(`/api/plan/entries/${id}`, patch)).data;
export const removeEntry = (id: number) => api.delete(`/api/plan/entries/${id}`);
// The week is over: what wasn't eaten is kept as skipped
export const closeWeek = (start: string) => api.post('/api/plan/close', { start });
// Closed weeks, newest first; `before`: older than that week
export const fetchHistory = async (weeks: number, before?: string) =>
    (await api.get<Week[]>('/api/plan/history', { params: { weeks, ...(before ? { before } : {}) } })).data;
// slot: the slot being planned, so what fits it comes first (null: the usual order)
export const fetchSuggestions = async (tab: SuggestionTab, q: string, slot: Slot | null) =>
    (await api.get<RecipeSummary[]>('/api/suggestions', { params: { tab, ...(q ? { q } : {}), ...(slot ? { slot } : {}) } }))
        .data;

// The planning screen's "Für" choice, kept on this device (a Friday session is many dinners in a row)
const SLOT_KEY = 'meals.suggestionSlot';

export function loadSuggestionSlot(): Slot | null {
    try {
        const stored = localStorage.getItem(SLOT_KEY);
        return SLOTS.find((slot) => slot === stored) ?? null;
    } catch {
        return null;
    }
}

export function saveSuggestionSlot(slot: Slot | null): void {
    try {
        if (slot) localStorage.setItem(SLOT_KEY, slot);
        else localStorage.removeItem(SLOT_KEY);
    } catch {
        // Private mode or blocked storage: it just forgets
    }
}

// "2026-10-31" → its locale key under weekdays.* (Python numbering, 0 = Monday)
export const weekdayKey = (day: string) => WEEKDAYS[(parseISO(day).getDay() + 6) % 7];
export const addDays = (day: string, days: number) => {
    const d = parseISO(day);
    d.setDate(d.getDate() + days);
    return [d.getFullYear(), String(d.getMonth() + 1).padStart(2, '0'), String(d.getDate()).padStart(2, '0')].join('-');
};
