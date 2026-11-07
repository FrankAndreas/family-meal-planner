import api from './api';
import type { Schemas } from './apiTypes';

export { formatSpec } from './shoppingSpec';

// The shared shopping list (spec 2026-11-06): the parents' decisions, with the lines worked out from the plan
export type ShoppingMeal = Schemas['ShoppingMealOut'];
export type ShoppingNote = Schemas['ShoppingNoteOut'];
export type { ShoppingLine } from './shoppingSpec';
export type ShoppingExtra = Schemas['ShoppingExtraOut'];
export type ShoppingList = Schemas['ShoppingOut'];

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
    (await api.post<{ sent: number; kept: boolean }>('/api/shopping/send', { version, specs })).data;
