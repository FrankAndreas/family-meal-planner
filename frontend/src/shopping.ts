import api from './api';
import type { Slot } from './plan';

export { formatSpec } from './shoppingSpec';

// The shared shopping list (spec 2026-11-06): the parents' decisions, with the lines worked out from the plan
export interface ShoppingMeal {
    entry_id: number;
    date: string;
    slot: Slot;
    title: string;
    people: number | null;
    ticked: boolean;
}

export interface ShoppingNote {
    date: string;
    slot: Slot;
    note: string;
}

export type { ShoppingLine } from './shoppingSpec';
import type { ShoppingLine } from './shoppingSpec';

export interface ShoppingExtra {
    id: number;
    name: string;
    amount: string;
}

export interface ShoppingList {
    week_start: string;
    week_end: string;
    started_by: string | null;
    changed_by: string | null;
    changed_at: string;
    meals: ShoppingMeal[];
    notes: ShoppingNote[];
    lines: ShoppingLine[];
    extras: ShoppingExtra[];
    version: string;
}

export const fetchShopping = async () => (await api.get<{ list: ShoppingList | null }>('/api/shopping')).data.list;

export const startShopping = async (weekStart: string, replace = false) =>
    (await api.post<ShoppingList>('/api/shopping', { week_start: weekStart, replace })).data;

export const discardShopping = async () => {
    await api.delete('/api/shopping');
};

export const tickMeal = async (entryId: number, ticked: boolean) =>
    (await api.put<ShoppingList>(`/api/shopping/meals/${entryId}`, { ticked })).data;

export const chooseLine = async (key: string, buy: boolean | null) =>
    (await api.put<ShoppingList>('/api/shopping/lines', { key, buy })).data;

export const addExtra = async (name: string, amount: string) =>
    (await api.post<ShoppingList>('/api/shopping/extras', { name, amount })).data;

export const removeExtra = async (id: number) => (await api.delete<ShoppingList>(`/api/shopping/extras/${id}`)).data;

export const sendShopping = async (version: string, specs: Record<string, string>) =>
    (await api.post<{ sent: number }>('/api/shopping/send', { version, specs })).data.sent;
